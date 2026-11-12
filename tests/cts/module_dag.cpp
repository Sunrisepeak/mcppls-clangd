// The modules a file imports are built as a graph: at most as many at once as the bound allows,
// none before what it imports, and a module that does not compile takes with it only what imports
// it.
import std;
import engine.harness;
import mcpplibs.mtest.e2e;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

const std::string HEADERS { "module;\n#include <vector>\n#include <map>\n#include <string>\n#include <algorithm>\n" };

using Dependencies = std::vector<std::pair<std::string, std::vector<std::string>>>;   // in the order they are written

struct Project {
    fs::path source;
    std::string text;
    Dependencies dependencies;
};

Project generate(const fs::path& root, std::string_view shape, bool heavy) {
    Dependencies dependencies;
    std::vector<std::string> imports;
    if (shape == "textual") {
        dependencies = { { "A", { "foreign_missing" } }, { "C", {} } };
        imports = { "A", "C" };
    } else if (shape == "prebuilt") {
        dependencies = { { "A", { "B" } } };
        imports = { "A" };
    } else if (shape == "wide" || shape == "concurrent") {
        for (int i { 1 }; i < 5; ++i) dependencies.push_back({ std::format("m{}", i), {} });
        for (const auto& [name, required] : dependencies) imports.push_back(name);
    } else {
        dependencies = { { "D", {} }, { "B", { "D" } }, { "C", { "D" } }, { "A", { "B", "C" } } };
        imports = { "A" };
    }
    std::vector<fs::path> sources;
    for (const auto& [name, required] : dependencies) {
        std::string text { heavy ? HEADERS : std::string {} };
        text += std::format("export module {};\n", name);
        for (const auto& dependency : required) text += std::format("export import {};\n", dependency);
        text += std::format("export int fn{}() {{ return 1; }}\n", name);
        if (shape == "failure" && name == "B") text += "export int broken = unknown_name;\n";
        sources.push_back(root / (name + ".cppm"));
        write(sources.back(), text);
    }
    const fs::path source { root / "Use.cpp" };
    std::string text;
    for (const auto& name : imports) text += std::format("import {};\n", name);
    text += "void caller(){\n  fn\n}\n";
    write(source, text);
    json commands = json::array();
    for (const auto& file : sources) commands.push_back(compile_command(root, file, { "-std=c++20", "-c", str(file) }));
    commands.push_back(compile_command(root, source, { "-std=c++20", "-c", str(source) }));
    if (shape == "concurrent") {
        const fs::path peer { root / "Peer.cpp" };
        write(peer, text);
        commands.push_back(compile_command(root, peer, { "-std=c++20", "-c", str(peer) }));
    }
    if (shape == "prebuilt") {
        // B is not the project's to build: the compiler writes its BMI, and A's command names it.
        const fs::path prebuiltSource { root / "B.cppm" }, prebuilt { root / "B.pcm" };
        write(prebuiltSource, "export module B;\nexport int fnB() { return 1; }\n");
        e2e::command precompile;
        precompile.argv = { str(subject().clang), "-std=c++20", "--precompile", str(prebuiltSource), "-o", str(prebuilt) };
        precompile.timeout = std::chrono::seconds { 20 };
        const auto compiled = e2e::run(std::move(precompile));
        expect(fatal(static_cast<bool>(compiled))) << "the compiler did not write B's BMI: " << compiled.err;
        commands[0]["arguments"].push_back("-fmodule-file=B=" + str(prebuilt));
    }
    write_database(root, commands);
    return { source, text, dependencies };
}

int line_of(std::string_view text, std::string_view wanted) {
    int line { 0 };
    for (const auto part : std::views::split(text, '\n')) {
        if (std::string_view { part.begin(), part.end() } == wanted) return line;
        ++line;
    }
    return -1;
}

void shape_with(std::string_view shape, int workers) {
    const fs::path root { work(std::format("{}-{}", shape, workers)) };
    const Project project { generate(root, shape, shape == "wide" || shape == "concurrent") };
    const fs::path& source { project.source };
    const fs::path peer { root / "Peer.cpp" };
    Session session { .id = std::format("{}-{}", shape, workers), .project = root,
                      .flags = { "--experimental-modules-support", "--background-index=false", "-j=4", "--log=verbose", std::format("--modules-builder-workers={}", workers) },
                      .timeout_seconds = 30 };
    session.sequence = json::array({ initialize(root), initialized(), did_open(source, project.text) });
    if (shape == "concurrent") session.sequence.push_back(did_open(peer, project.text));
    session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", json { { "/result/0/name", "caller" } } } });
    if (shape == "concurrent")
        session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(peer) }, { "expect", json { { "/result/0/name", "caller" } } } });
    json at = position(line_of(project.text, "  fn"), 4);
    if (shape == "failure") {
        session.sequence.push_back(json { { "action", "await-log" }, { "contains", "Failed to build module prerequisites" } });
        session.sequence.push_back(did_change(source, 2, "int healthy;\n"));
        session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", json { { "/result/0/name", "healthy" } } } });
    } else {
        std::vector<std::string> expected;
        if (shape == "textual") expected = { "fnC" };
        else
            for (const auto& [name, required] : project.dependencies) expected.push_back("fn" + name);
        if (shape == "prebuilt") expected.push_back("fnB");
        json params = document(source);
        params["position"] = at;
        session.sequence.push_back(json { { "method", "textDocument/completion" }, { "params", params }, { "expected_symbols", expected } });
    }
    if (shape == "concurrent") {
        std::vector<std::string> expected;
        for (const auto& [name, required] : project.dependencies) expected.push_back("fn" + name);
        json params = document(peer);
        params["position"] = at;
        session.sequence.push_back(json { { "method", "textDocument/completion" }, { "params", params }, { "expected_symbols", expected } });
    }
    const json result = replay(session);
    passed(result, root);
    const std::string log { result.value("stderr", std::string {}) };
    if (shape != "failure") expect(!log.contains("Failed to build")) << "a valid DAG failed to build";

    static const std::regex START { R"(Module build task (\S+) started \(active=(\d+), limit=(\d+)\))" };
    static const std::regex FINISH { R"(Module build task (\S+) finished)" };
    std::map<std::string, std::size_t> starts, finished;
    int maximum { 0 }, limit { 0 };
    const auto lines = log_lines(result);
    for (std::size_t index { 0 }; index < lines.size(); ++index) {
        std::smatch match;
        if (std::regex_search(lines[index], match, START)) {
            const std::string name { match[1] };
            const int active { std::stoi(match[2]) }, bound { std::stoi(match[3]) };
            expect((!starts.contains(name) || shape == "concurrent") && 1 <= active && active <= bound && bound <= workers)
                << "duplicate task or worker bound violated: " << lines[index];
            starts[name] = index;
            maximum = std::max(maximum, active);
            limit = std::max(limit, bound);
        }
        if (std::regex_search(lines[index], match, FINISH)) finished[match[1]] = index;
    }
    std::set<std::string> required;
    for (const auto& [name, imports] : project.dependencies) required.insert(name);
    if (shape == "textual") {
        required = { "C" };
        expect(contains(log, std::string { "Keeping import of third-party module foreign_missing textual" })) << "unavailable transitive provider lost textual behavior";
    }
    // A imports B, which does not compile; C, B's independent sibling, is built and used whatever the bound (it was
    // left out with one worker while one failure still failed the whole set).
    if (shape == "failure") required.erase("A");
    const auto keys = [](const std::map<std::string, std::size_t>& map) {
        std::set<std::string> out;
        for (const auto& [name, index] : map) out.insert(name);
        return out;
    };
    expect(keys(starts) == required && keys(finished) == required)
        << "wrong tasks: started=" << json(keys(starts)).dump() << ", finished=" << json(keys(finished)).dump();
    for (const auto& [name, imports] : project.dependencies) {
        if (!required.contains(name) || !starts.contains(name)) continue;
        for (const auto& dependency : imports) {
            if (finished.contains(dependency)) expect(lt(finished[dependency], starts[name])) << name << " started before dependency " << dependency << " finished";
        }
    }
    if ((shape == "wide" || shape == "concurrent") && workers > 1 && limit > 1) expect(ge(maximum, 2)) << "independent compilation tasks never overlapped";
    std::println("{} {} max_active {} document_symbol_ms {:.2f}", session.id, result.value("outcome", std::string {}), maximum,
                 elapsed_ms(result, "textDocument/documentSymbol"));
}

// One cold run of each shape; the times are told, not bounded. The worker count bounds the compilers at work at
// once, not the memory they take.
//
// Every part needs a compiler that is the engine's own build: the engine reads the standard headers the heavy
// shapes include through the compile command's compiler, and `prebuilt` reads a BMI that compiler writes.
CTS dag{"module-dag", [] { against_subject([] {
    const std::pair<const char*, int> shapes[] { { "wide", 1 }, { "wide", 2 }, { "wide", 4 }, { "diamond", 1 }, { "diamond", 4 },
                                                 { "failure", 1 }, { "failure", 4 }, { "prebuilt", 4 }, { "concurrent", 2 }, { "textual", 4 } };
    for (const auto& [shape, workers] : shapes) {
        test(std::format("{} with {} at once", shape, workers))[cts::needs { "matching-clang" }] = [shape, workers] { shape_with(shape, workers); };
    }
}); }};

}  // namespace
