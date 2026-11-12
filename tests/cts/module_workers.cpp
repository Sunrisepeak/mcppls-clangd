// The supervised workers that build modules on Linux: what a default session starts and how it is
// bounded, a worker that fails under a small address space, and a worker that writes more
// diagnostics than its parent keeps.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

json completion_at(const fs::path& file, int line, int character, std::vector<std::string> required) {
    json params = document(file);
    params["position"] = position(line, character);
    return json { { "method", "textDocument/completion" }, { "params", std::move(params) }, { "expected_symbols", std::move(required) } };
}

std::string file_text(const fs::path& file) { return contents(file); }

std::vector<std::string> words(std::string_view text, char separator) {
    std::vector<std::string> out;
    for (const auto part : std::views::split(text, separator)) out.emplace_back(part.begin(), part.end());
    return out;
}

// Every process below `pid`. Pool children belong to the thread that started them, not necessarily the leader:
// each task's list is read, and below them -- a runner may stand between the engine and its worker.
std::vector<std::string> descendants(std::uint64_t pid) {
    std::vector<std::string> pending { std::to_string(pid) }, seen;
    while (!pending.empty()) {
        const std::string parent { std::move(pending.back()) };
        pending.pop_back();
        std::error_code failed;
        for (fs::directory_iterator task { fs::path { "/proc" } / parent / "task", failed }, end; !failed && task != end; task.increment(failed)) {
            for (const auto part : std::views::split(file_text(task->path() / "children"), ' ')) {
                std::string child { part.begin(), part.end() };
                while (!child.empty() && std::isspace(static_cast<unsigned char>(child.back()))) child.pop_back();
                if (child.empty() || std::ranges::find(seen, child) != seen.end()) continue;
                seen.push_back(child);
                pending.push_back(child);
            }
        }
    }
    return seen;
}

struct Worker {
    std::vector<std::string> command;
    std::size_t argument { 0 };   // where `--module-build-worker` is in it
    std::vector<std::string> addressSpace;
    std::string cgroup;
};

// A default session through real LSP and a dirty header: the header the editor holds is the one the module is
// built with, a worker is started and bounded, a dependency file the command names is neither written nor
// touched, and nothing of the worker is left when the session ends.
void default_worker(std::vector<std::string> engineFlags, std::string_view dependencyMode) {
    const Subject& s { subject() };
    const fs::path project { work("default-worker") };
    const fs::path module { project / "M.cppm" }, source { project / "Use.cpp" }, header { project / "header.h" };
    write(header, "inline constexpr int Captured = 41;\n");
    write(module, "module;\n#include \"header.h\"\nexport module M;\n"
                  "constexpr int work() { int v=0; for(int i=0;i<200000;++i) v+=i%7; return v; }\n"
                  "static_assert(work()>0);\nstatic_assert(Captured == 42);\n"
                  "export int fn_m() { return Captured; }\n");
    const std::string text { "import M;\nvoid probe() { fn; }\n" };
    write(source, text);
    std::map<fs::path, std::string> originals;
    for (const auto& file : { module, source, header }) originals[file] = read(file);
    const fs::path dependency { project / "M.d" };
    const bool dependencies { dependencyMode != "none" };
    if (dependencies) {
        write(dependency, "existing dependency output must survive\n");
        originals[dependency] = read(dependency);
    }
    json commands = json::array();
    for (const auto& file : { module, source }) {
        std::vector<std::string> arguments { "-std=c++20", "-fconstexpr-steps=0", "-c", file.filename().string() };
        if (dependencies) {
            arguments.push_back("-" + std::string { dependencyMode });
            arguments.insert(arguments.end(), { "-MF", file.stem().string() + ".d", "-MT", "ordinary-target" });
        }
        commands.push_back(compile_command(project, file, std::move(arguments)));
    }
    write_database(project, commands);

    Session session { .id = "default-module-worker", .project = project,
                      .flags = { "--experimental-modules-support", "--use-dirty-headers", "--background-index=false", "--log=verbose" }, .timeout_seconds = 40 };
    for (const auto& flag : engineFlags) session.flags.push_back(flag);
    session.sequence = json::array({ initialize(project), initialized(), did_open(header, "inline constexpr int Captured = 42;\n"), did_open(source, text),
                                     completion_at(source, 1, 17, { "fn_m" }) });

    // clangd.okb starts each worker through the loader that started it, and openkal states no address-space
    // ceiling: the parent's memory budget is an image worker's bound (openkal/patches, FEATURE-45).
    const bool image { s.image() };
    std::mutex mutex;
    std::map<std::string, Worker> observations;
    std::map<std::string, json> captured;
    std::atomic<bool> stopped { false };
    std::thread observer;
    session.started = [&](std::uint64_t pid) {
        observer = std::thread { [&, pid] {
            while (!stopped.load()) {
                for (const auto& child : descendants(pid)) {
                    const fs::path process { fs::path { "/proc" } / child };
                    std::vector<std::string> command { words(file_text(process / "cmdline"), '\0') };
                    const auto found = std::ranges::find(command, std::string { "--module-build-worker" });
                    if (found == command.end()) continue;
                    const std::size_t at { static_cast<std::size_t>(found - command.begin()) };
                    const std::lock_guard lock { mutex };
                    if (dependencies && !captured.contains(child) && at + 1 < command.size()) {
                        const json request = json::parse(file_text(command[at + 1]), nullptr, false);
                        if (request.is_object()) captured[child] = request;
                    }
                    std::vector<std::string> columns;
                    for (const auto& line : words(file_text(process / "limits"), '\n')) {
                        if (!line.starts_with("Max address space")) continue;
                        std::istringstream rest { line.substr(std::string_view { "Max address space" }.size()) };
                        for (std::string word; columns.size() < 2 && rest >> word;) columns.push_back(word);
                    }
                    if (columns.size() < 2) continue;
                    // Its start may still be applying the bound: what is kept is the state that was checked.
                    if (image || columns != std::vector<std::string> { "unlimited", "unlimited" }) {
                        std::erase(command, std::string {});
                        observations[child] = Worker { std::move(command), at, columns, file_text(process / "cgroup") };
                    }
                }
                std::this_thread::sleep_for(std::chrono::milliseconds { 1 });
            }
        } };
    };
    const json result = replay(session);
    stopped.store(true);
    if (observer.joinable()) observer.join();

    passed(result, project);
    for (const auto& [file, contents] : originals) expect(eq(file_text(file), contents)) << str(file) << " changed on disk";
    for (const auto& line : log_lines(result)) {
        expect(!(line.contains("Failed to build module prerequisites") && !line.ends_with("; due to Task was cancelled."))) << line;
    }
    expect(fatal(!observations.empty())) << "default server did not launch a checked module worker";
    if (dependencies) {
        expect(!captured.empty()) << "no real owned-default worker request captured";
        for (const auto& [child, request] : captured) {
            expect(eq(request.value("version", 0), 4)) << "dependency canary requires owned-default admission";
            const auto arguments = request.value("cc1Arguments", json::array());
            expect(std::ranges::find(arguments, json("-dependency-file")) == arguments.end()) << request.dump();
        }
        expect(!fs::exists(project / "Use.d")) << "Use.d dependency output escaped";
        expect(eq(file_text(dependency), originals[dependency])) << "existing M.d was modified";
    }
    std::println("default-module-worker: {} worker(s) observed, dependency mode {}", observations.size(), dependencyMode);
    for (const auto& [child, item] : observations) {
        if (image) {
            expect(eq(fs::path { item.command.front() }.filename().string(), s.runner.filename().string())) << json(item.command).dump();
        } else {
            const auto soft = std::stoull(item.addressSpace[0]), hard = std::stoull(item.addressSpace[1]);
            expect(soft == hard && hard > 0 && hard <= 4096ull * 1024 * 1024) << "address space " << soft << " " << hard;
        }
        // The request file is found by where the flag was before the empty words were dropped.
        const auto flag = std::ranges::find(item.command, std::string { "--module-build-worker" });
        if (flag == item.command.end() || flag + 1 == item.command.end()) continue;
        const fs::path request { *(flag + 1) };
        expect(!fs::exists(request.parent_path())) << "worker unit survives normal shutdown: " << str(request.parent_path());
        if (std::ranges::any_of(engineFlags, [](const std::string& f) { return f.starts_with("--modules-builder-worker-cgroup-root="); })) {
            expect(contains(item.cgroup, std::string { "/clangd-module-workers-" })) << item.cgroup;
            if (flag + 3 < item.command.end()) {
                const auto parts = words(*(flag + 3), ':');
                if (parts.size() >= 4) {
                    std::string group { parts[3] };
                    for (std::size_t i { 4 }; i < parts.size(); ++i) group += ":" + parts[i];
                    expect(!fs::exists(group)) << "owned memory group survives normal shutdown: " << group;
                }
            }
        }
    }
}

CTS worker_default{"module-worker-default", [] { against_subject([] {
    "a worker is started and bounded, and a dependency file is left alone"_test[cts::needs { "linux" }] = [] { default_worker({}, "MMD"); };
}); }};

CTS worker_payloads{"module-worker-payloads", [] { against_subject([] {
    "a worker whose output and capture are bounded at a megabyte"_test[cts::needs { "linux" }] = [] {
        default_worker({ "--modules-builder-worker-output-mib=1", "--modules-builder-worker-capture-mib=1" }, "none");
    };
}); }};

struct Trio {
    fs::path project, module, use, control;
    std::map<fs::path, std::string> originals;
};

Trio trio(std::string_view name) {
    Trio t;
    t.project = work(name);
    t.module = t.project / "M.cppm";
    t.use = t.project / "Use.cpp";
    t.control = t.project / "Control.cpp";
    write(t.module, "export module M;\nexport int fn_m() { return 42; }\n");
    write(t.use, "import M;\nint probe() { return fn_m(); }\n");
    write(t.control, "int ControlValue = 73;\n");
    for (const auto& file : { t.module, t.use, t.control }) t.originals[file] = read(file);
    json commands = json::array();
    for (const auto& file : { t.module, t.use, t.control }) commands.push_back(compile_command(t.project, file, { "-std=c++20", "-c", file.filename().string() }));
    write_database(t.project, commands);
    return t;
}

// What both failures leave: the parent answers for another file, the sources are as they were, the module was not
// built some other way, and neither a BMI nor a worker's unit remains.
void parent_survived(const Trio& t, const json& result) {
    passed(result, t.project);
    for (const auto& [file, contents] : t.originals) expect(eq(file_text(file), contents)) << "the server changed " << str(file);
    const std::string log { result.value("stderr", std::string {}) };
    expect(contains(log, std::string { "module worker failed" })) << "no actual failed-worker event";
    expect(!log.contains("Built module M to ")) << "failed worker fell back to compilation";
    const auto bmis = files_under(t.project, [](const fs::directory_entry& e) { return e.path().extension() == ".pcm"; });
    expect(bmis.empty()) << "a BMI remains: " << (bmis.empty() ? std::string {} : str(bmis.front()));
    const auto units = files_under(t.project, [](const fs::directory_entry& e) { return e.is_directory() && e.path().filename().string().starts_with("unit-"); });
    expect(units.empty()) << "a worker unit remains: " << (units.empty() ? std::string {} : str(units.front()));
}

// A worker failure under a small address cap must leave its LSP parent usable.
CTS worker_failure{"module-worker-failure", [] { against_subject([] {
    "a worker that fails under a small address space leaves its parent answering"_test[cts::needs { "linux" }] = [] {
        const Trio t { trio("failed-worker") };
        Session session { .id = "module-worker-low-address-failure", .project = t.project,
                          .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose", "--modules-builder-workers=2",
                                     "--modules-builder-worker-aggregate-address-space-mib=32" },
                          .timeout_seconds = 40 };
        session.sequence = json::array({
            initialize(t.project), initialized(), did_open(t.use, read(t.use)),
            // Written after a worker that was started ends unsuccessfully, not when a file system is unsupported or
            // a request is refused.
            json { { "action", "await-log" }, { "contains", "module worker failed" } },
            did_open(t.control, read(t.control)),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(t.control) }, { "expect", json { { "/result/0/name", "ControlValue" } } } },
        });
        parent_survived(t, replay(session));
    };
}); }};

// A stand-in for a worker that writes eight megabytes of diagnostics: its parent keeps a bounded part through a
// FIFO that holds nothing on disk, and goes on. The transport is native Linux's; the image takes the portable one
// (https://github.com/Sunrisepeak/mcppls-clangd/issues/19). A check of the transport, not of a compiler's crash.
CTS worker_diagnostics{"module-worker-diagnostics", [] { against_subject([] {
    "a worker's diagnostics are bounded and its parent goes on"_test[cts::needs { "linux", "native" }] = [] {
        const Trio t { trio("noisy-worker") };
        const fs::path worker { t.project / "noisy-worker.sh" }, record { t.project / "writer.txt" };
        // What its standard error is, before and after it wrote: a FIFO, of no size, with nothing allocated.
        write(worker, std::format("#!/bin/sh\n"
                                  "record() {{ if [ -p /proc/self/fd/2 ]; then fifo=1; else fifo=0; fi\n"
                                  "  echo \"$1 $fifo $(stat -L -c '%s %b' /proc/self/fd/2)\" >> '{}'; }}\n"
                                  "record started\n"
                                  "echo diagnostic-prefix >&2\n"
                                  "head -c 8388608 /dev/zero | tr '\\0' X >&2\n"
                                  "record finished\n"
                                  "exit 1\n",
                                  str(record)));
        fs::permissions(worker, fs::perms::owner_all | fs::perms::group_read | fs::perms::group_exec | fs::perms::others_read | fs::perms::others_exec);
        Session session { .id = "module-worker-bounded-diagnostic-transport", .project = t.project,
                          .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose", "--modules-builder-workers=1",
                                     "--modules-builder-worker-policy=required", "--modules-builder-worker-executable=" + str(worker) },
                          .timeout_seconds = 40 };
        session.sequence = json::array({
            initialize(t.project), initialized(), did_open(t.use, read(t.use)),
            json { { "action", "await-log" }, { "contains", "diagnostics truncated" } },
            did_open(t.control, read(t.control)),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(t.control) }, { "expect", json { { "/result/0/name", "ControlValue" } } } },
        });
        const json result = replay(session);
        const auto lines = words(file_text(record), '\n');
        expect(fatal(lines.size() >= 2)) << "the worker did not record its standard error: " << file_text(record);
        expect(eq(lines[0], std::string { "started 1 0 0" })) << "its standard error is no empty FIFO";
        expect(eq(lines[1], std::string { "finished 1 0 0" })) << "noisy worker did not finish its 8 MiB write into an empty FIFO";
        parent_survived(t, result);
    };
}); }};

}  // namespace
