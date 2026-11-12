// Readers of a shared BMI cache: in the owned cache a reader is given the published generation
// under a lease of its own and no copy is made; on the portable path each reader's copy is
// protected while it lives and reclaimed after its engine is killed. And what a request reads of
// a file's imports is the buffer the request has, not the disk.
import std;
import engine.harness;
import mcpplibs.os;

using namespace mcpplibs::mtest;
using namespace engine;
namespace os = mcpplibs::os;

namespace {

std::vector<std::string> base_flags(std::string_view mode) {
    std::vector<std::string> flags { "--experimental-modules-support", "--background-index=false", "--modules-builder-versioned-gc-threshold-seconds=0", "-j=2" };
    if (mode == "legacy") flags.push_back("--modules-builder-owned-cache-payload-mib=0");
    return flags;
}

// The file is opened, its AST is there, and completion offers the module's function.
void ready(Client& client, const fs::path& root) {
    const fs::path source { root / "Use.cpp" };
    client.open_project(source);
    const json symbols = client.request("textDocument/documentSymbol", document(source));
    expect(fatal(symbols.is_array() && std::ranges::any_of(symbols, [](const json& s) { return s.value("name", std::string {}) == "marker"; }))) << "AST barrier lacks marker";
    json params = document(source);
    params["position"] = position(1, 15);
    json items = client.request("textDocument/completion", params);
    if (items.is_object()) items = items.value("items", json::array());
    expect(fatal(items.is_array() && std::ranges::any_of(items, [](const json& i) { return i.value("filterText", std::string {}) == "fn1" && i.value("kind", 0) == 3; })))
        << "missing semantic module function";
}

// The engines among `pids` (and what they started) that hold the lease's file open; nothing where the system
// cannot say.
std::optional<std::vector<std::uint64_t>> lease_holders(const fs::path& lease, std::vector<std::uint64_t> pids) {
    std::error_code failed;
    const fs::path resolved { fs::canonical(lease, failed) };
    if (os::host() == os::platform::linux) {
        std::set<std::uint64_t> family { pids.begin(), pids.end() };
        // A process's parent is the word after its state, which follows the name's closing parenthesis.
        for (fs::directory_iterator entry { "/proc", failed }, end; !failed && entry != end; entry.increment(failed)) {
            const std::string name { entry->path().filename().string() };
            if (name.empty() || !std::ranges::all_of(name, [](unsigned char c) { return std::isdigit(c); })) continue;
            const std::string stat { contents(entry->path() / "stat") };
            const auto close = stat.rfind(')');
            if (close == std::string::npos) continue;
            std::istringstream rest { stat.substr(close + 1) };
            std::string state;
            std::uint64_t parent { 0 };
            if (rest >> state >> parent && family.contains(parent)) family.insert(std::stoull(name));
        }
        std::vector<std::uint64_t> held;
        for (const auto pid : family) {
            std::error_code unreadable;
            for (fs::directory_iterator fd { fs::path { "/proc" } / std::to_string(pid) / "fd", unreadable }, end; !unreadable && fd != end; fd.increment(unreadable)) {
                std::error_code gone;
                if (fs::read_symlink(fd->path(), gone) == resolved && !gone) {
                    held.push_back(pid);
                    break;
                }
            }
        }
        return held;
    }
    // Windows: no program of the system names the processes that have a file open; the lease is observed through
    // what it protects (the published generation survives collection).
    if (os::host() == os::platform::windows) return std::nullopt;
    // macOS: the system's lsof names the processes that have the file open.
    const Ran found { tool({ "lsof", "-t", str(resolved) }) };
    std::vector<std::uint64_t> held;
    std::istringstream words { found.out };
    for (std::string word; words >> word;)
        if (std::ranges::all_of(word, [](unsigned char c) { return std::isdigit(c); })) held.push_back(std::stoull(word));
    std::ranges::sort(held);
    return held;
}

bool holds(const std::vector<std::uint64_t>& holders, std::uint64_t pid) { return std::ranges::find(holders, pid) != holders.end(); }

// `mode`: auto, the cache the engine reports it uses for this directory ("Module cache <root>: owned" or "...: a
// copy of each BMI for each reader"); legacy turns the owned cache off.
void cache_lease(std::string mode) {
    const fs::path root { work() };
    write(root / "A.cppm", "export module A;\nexport int fn1(){return 1;}\n");
    write(root / "Use.cpp", "import A;\nint marker = fn1();\n");
    write_database_for(root, { root / "A.cppm", root / "Use.cpp" });
    const fs::path cache { root / ".cache/clangd/modules" };
    const auto flags = base_flags(mode);
    auto verbose = flags;
    verbose.push_back("--log=verbose");

    std::string seedLog;
    {
        Client seed { root, flags };
        ready(seed, root);
        seed.stop();
        seedLog = seed.log();
    }
    if (mode == "auto") {
        static const std::regex REPORTED { R"(Module cache .+: (owned|a copy of each BMI for each reader))" };
        std::smatch selected;
        mode = std::regex_search(seedLog, selected, REPORTED) && selected[1] == "owned" ? "owned" : "legacy";
        std::println("the engine reports: {}", selected.empty() ? std::string { "nothing about its module cache" } : selected[0].str());
    }
    fs::path published;
    if (mode == "owned") {
        static const std::regex BUILT { R"(Built module A to ([^\r\n]+))" };
        std::smatch match;
        expect(fatal(std::regex_search(seedLog, match, BUILT))) << "missing fresh owned publication event";
        std::string name { match[1] };
        while (!name.empty() && std::isspace(static_cast<unsigned char>(name.back()))) name.pop_back();
        published = fs::path { os::fs::from_utf8(os::fs::generic(os::fs::from_utf8(name))) };
        expect(fatal(str(published).contains("/.owned-payload-v1/") && published.filename() == "payload.pcm"))
            << "default owned admission did not publish its managed generation: " << str(published);
    } else {
        const auto found = files_under(cache, [](const fs::directory_entry& e) { return e.path().filename() == "A.pcm"; });
        expect(fatal(eq(found.size(), std::size_t { 1 }))) << "expected one legacy A publication";
        published = found.front();
    }
    // An ancient time of access shows that collection does not trust timestamps.
    const auto identity = os::fs::identity_of(published);
    const auto stamp = os::fs::stamp_of(published);
    expect(fatal(identity.has_value() && stamp.has_value())) << "the published BMI cannot be examined";
    age_access_time(published);
    const auto unchanged = [&] {
        const auto now = os::fs::identity_of(published);
        const auto at = os::fs::stamp_of(published);
        return now && at && *now == *identity && at->modified_ns == stamp->modified_ns;
    };

    if (mode == "owned") {
        // A reader is given the stable generation where it was published, under a lease of its own (`lease-<slot>`,
        // an OFD lock beside the generations); no copy is made.
        const std::string generation { published.parent_path().filename().string() };   // generation-<slot>-<n>
        const auto first = generation.find('-');
        const std::string slot { generation.substr(first + 1, generation.find('-', first + 1) - first - 1) };
        const fs::path lease { published.parent_path().parent_path() / ("lease-" + slot) };
        const auto payloads = [&] {
            auto found = files_under(cache / ".owned-payload-v1", [](const fs::directory_entry& e) {
                return e.path().filename() == "payload.pcm" && e.path().parent_path().filename().string().starts_with("generation-");
            });
            std::ranges::sort(found);
            return found;
        };
        const auto only_published = [&] { return payloads() == std::vector<fs::path> { published }; };
        Client reader { root, flags };
        ready(reader, root);
        expect(unchanged()) << "the published BMI changed when it was reused";
        expect(contains(reader.log(), "Reusing owned module A from " + str(published))) << "the reader did not reuse the generation where it was published";
        expect(only_published()) << "a copy was made";
        if (const auto holders = lease_holders(lease, { reader.pid() })) expect(holds(*holders, reader.pid())) << "the reader does not hold its lease";
        Client peer { root, flags };
        ready(peer, root);
        expect(only_published()) << "the peer does not read the same generation";
        reader.stop(true);
        Client collector { root, verbose };
        ready(collector, root);
        // Owned maintenance visits bounded batches of slots independently of AST work: it is given the time it
        // takes, never forced.
        std::this_thread::sleep_for(std::chrono::seconds { 6 });
        if (const auto holders = lease_holders(lease, { peer.pid(), collector.pid() })) expect(holds(*holders, peer.pid())) << "a live reader does not hold the lease";
        expect(fs::exists(published) && unchanged()) << "the published generation did not survive collection";
        expect(only_published()) << "a copy was made during collection";
        collector.stop();
        peer.stop();
    } else {
        // Each lease names its copy: `<copy>.pcm.lease`.
        const auto live_copies = [&] {
            std::map<fs::path, fs::path> copies;
            for (const auto& lease : files_under(cache, [](const fs::directory_entry& e) { return e.path().filename().string().ends_with(".pcm.lease"); })) {
                const std::string name { str(lease) };
                copies[lease] = fs::path { os::fs::from_utf8(name.substr(0, name.size() - std::string_view { ".lease" }.size())) };
            }
            return copies;
        };
        Client reader { root, flags };
        ready(reader, root);
        expect(unchanged()) << "the published BMI changed when it was reused";
        const auto copies = live_copies();
        expect(fatal(!copies.empty())) << "reused BMIs lack owner leases";
        for (const auto& [lease, copy] : copies) age_access_time(copy);
        Client peer { root, flags };
        ready(peer, root);
        expect(fatal(std::ranges::all_of(copies, [](const auto& item) { return fs::exists(item.second); }))) << "collection removed a live copy";
        expect(fatal(unchanged())) << "the published BMI was rebuilt";
        std::map<fs::path, fs::path> peerCopies;
        for (const auto& [lease, copy] : live_copies())
            if (!copies.contains(lease)) peerCopies[lease] = copy;
        reader.stop(true);
        Client collector { root, verbose };
        ready(collector, root);
        for (const auto& [lease, copy] : copies) expect(!fs::exists(lease) && !fs::exists(copy)) << "a killed reader's copy was not reclaimed: " << str(copy);
        expect(!peerCopies.empty() && std::ranges::all_of(peerCopies, [](const auto& item) { return fs::exists(item.first) && fs::exists(item.second); }))
            << "the other live reader's copy was not kept";
        const auto now = os::fs::identity_of(published);
        expect(fs::exists(published) && now && *now == *identity) << "the published BMI did not survive reclamation";
        collector.stop();
        peer.stop();
    }
}

CTS lease{"module-cache-lease", [] { against_subject([] {
    "readers of the cache the engine chooses here"_test = [] { cache_lease("auto"); };
}); }};

CTS lease_legacy{"module-cache-lease-legacy", [] { against_subject([] {
    "readers with a copy each"_test[cts::needs { "linux" }] = [] { cache_lease("legacy"); };
}); }};

// Unsaved imports are scanned from the exact request buffer, not disk.
CTS request_inputs{"module-request-inputs", [] { against_subject([] {
    "each draft's imports are the ones its answers come from"_test = [] {
        const fs::path root { work() };
        const fs::path source { root / "Use.cpp" };
        const std::string disk { "int disk_value;\n" };
        write(source, disk);
        const fs::path m { root / "M.cppm" }, n { root / "N.cppm" };
        write(m, "export module M;\nexport int draft_value() { return 1; }\n");
        write(n, "export module N;\nexport int next_value() { return 1; }\n");
        write_database_for(root, { m, n, source });
        Session session { .id = "module-request-inputs", .project = root, .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose" },
                          .timeout_seconds = 30 };
        session.sequence = json::array({ initialize(root), initialized() });
        const std::string drafts[] { "import M;\nint probe() { return draft_value(); }\n", "int request_value;\n", "import N;\nint probe() { return next_value(); }\n" };
        for (int version { 1 }; version <= 3; ++version) {
            const std::string& text { drafts[version - 1] };
            session.sequence.push_back(version == 1 ? did_open(source, text, version) : did_change(source, version, text));
            session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(source) },
                                              { "expect", json { { "/result/0/name", version == 2 ? "request_value" : "probe" } } } });
            if (version != 2) {
                json params = document(source);
                params["position"] = position(1, 28);
                session.sequence.push_back(json { { "method", "textDocument/completion" }, { "params", params },
                                                  { "expected_symbols", json::array({ version == 1 ? "draft_value" : "next_value" }) } });
            }
        }
        const json result = replay(session);
        passed(result, root);
        expect(eq(read(source), disk)) << "the file on disk changed";
        // A superseded AST or the shutdown can cancel a module's build after the names asked for were answered:
        // that end is accepted, a build that failed is not.
        for (const auto& line : log_lines(result))
            expect(!(line.contains("Failed to build module prerequisites") && !line.ends_with("; due to Task was cancelled."))) << "valid unsaved imports failed: " << line;
    };
}); }};

}  // namespace
