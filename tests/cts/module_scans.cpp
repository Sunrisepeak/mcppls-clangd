// What the engine keeps between requests about a file's modules: the providers of a database's
// generation, and the scan of a file's imports with the inputs it read.
import std;
import engine.harness;
import mcpplibs.mtest.e2e;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

json completion_at(const fs::path& file, int line, int character, std::vector<std::string> required, double retrySeconds = 0) {
    json params = document(file);
    params["position"] = position(line, character);
    json step { { "method", "textDocument/completion" }, { "params", std::move(params) }, { "expected_symbols", std::move(required) } };
    if (retrySeconds > 0) step["retry_seconds"] = retrySeconds;
    return step;
}

// Fresh module facades share provider inventory without losing real symbols, and a server's requests, which all
// mangle with the mangler it names, reuse the provider index without mangling a command.
CTS provider_cache{"module-provider-cache", [] { against_subject([] {
    "three files over one prebuilt module share one inventory"_test[cts::needs { "matching-clang" }] = [] {
        const fs::path root { work() };
        const fs::path dep { root / "dep.cppm" }, pcm { root / "dep.pcm" };
        write(dep, "export module dep;\nexport int dep_value() { return 1; }\n");
        const std::vector<std::string> precompile { "-std=c++20", "--precompile", str(dep), "-o", str(pcm) };
        e2e::command compile;
        compile.argv = { str(subject().clang) };
        compile.argv.insert(compile.argv.end(), precompile.begin(), precompile.end());
        const auto compiled = e2e::run(std::move(compile));
        expect(fatal(static_cast<bool>(compiled))) << "the compiler did not write dep's BMI: " << compiled.err;
        json entries = json::array({ compile_command(root, dep, precompile) });
        Session session { .id = "provider-cache", .project = root, .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose" },
                          .timeout_seconds = 30 };
        session.sequence = json::array({ initialize(root), initialized() });
        const std::string text { "import dep;\nint probe() { return dep_value(); }\n" };
        for (int number { 0 }; number < 3; ++number) {
            const fs::path source { root / std::format("Use{}.cpp", number) };
            write(source, text);
            entries.push_back(compile_command(root, source, { "-std=c++20", "-c", str(source), "-fmodule-file=dep=" + str(pcm) }));
            session.sequence.push_back(did_open(source, text));
            session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", json { { "/result/0/name", "probe" } } } });
            session.sequence.push_back(completion_at(source, 1, 27, { "dep_value" }));
        }
        for (int number { 0 }; number < 128; ++number) {
            const fs::path source { root / std::format("Unrelated{}.cpp", number) };
            write(source, "int unrelated;\n");
            entries.push_back(compile_command(root, source, { "-std=c++20", "-c", str(source) }));
        }
        write_database(root, entries);
        const json result = replay(session);
        passed(result, root);
        expect(eq(log_count(result, "Module provider inventory:"), std::size_t { 1 })) << "fresh module facades did not reuse their CDB generation";
        expect(ge(log_count(result, "Module provider index reused unmangled:"), std::size_t { 2 })) << "fresh module facades did not reuse their CDB generation";
        expect(eq(log_count(result, "Module provider index reused:"), std::size_t { 0 })) << "a request mangled the inventory again to reuse the provider index";
        expect(!result.value("stderr", std::string {}).contains("Failed to build")) << "valid module failed to build";
    };
}); }};

// Exact-input scan invalidation and warm semantic reuse.
CTS scan_memo{"module-scan-memo", [] { against_subject([] {
    "a scan is kept until an input it read changes"_test[cts::needs { "linux" }] = [] {
        const fs::path root { work() };
        const fs::path use { root / "Use.cpp" }, header { root / "enable.h" };
        const std::string text { "#if __has_include(\"enable.h\")\n#include \"enable.h\"\n#endif\nint probe() { return fn; }\n" };
        write(use, text);
        const fs::path m { root / "M.cppm" }, n { root / "N.cppm" };
        write(m, "export module M;\nexport int fn_m() { return 1; }\n");
        write(n, "export module N;\nexport int fn_n() { return 1; }\n");
        write_database_for(root, { m, n, use });
        Session session { .id = "verified-module-scan-memo", .project = root,
                          .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose", "--use-dirty-headers" }, .timeout_seconds = 35 };
        session.sequence = json::array({ initialize(root), initialized(), did_open(use, text) });
        const auto probe = [&](int version, const char* symbol = nullptr) {
            if (version > 1) session.sequence.push_back(did_change(use, version, text));
            session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(use) }, { "expect", json { { "/result/0/name", "probe" } } } });
            // The module the edit brings in is built in the background: the completion is asked again until it has been.
            if (symbol != nullptr) session.sequence.push_back(completion_at(use, 3, 23, { symbol }, 10));
        };
        probe(1);
        probe(2);
        session.sequence.push_back(json { { "action", "write-file" }, { "file", "enable.h" }, { "contents", "import M;\n" } });
        probe(3, "fn_m");
        probe(4, "fn_m");
        session.sequence.push_back(json { { "action", "replace-file" }, { "file", "enable.h" }, { "from", "import M;" }, { "with", "import N;" }, { "preserve-mtime", true } });
        probe(5, "fn_n");
        session.sequence.push_back(did_open(header, "import M;\n"));
        probe(6, "fn_m");
        probe(7, "fn_m");
        session.sequence.push_back(did_change(header, 2, "import N;\n"));
        probe(8, "fn_n");
        const json result = replay(session);
        passed(result, root);
        expect(eq(read(use), text)) << "the file on disk changed";
        expect(ge(log_count(result, "Module dependency scan memo hit:"), std::size_t { 1 }));
        expect(ge(log_count(result, "Module dependency scan memo invalidated:"), std::size_t { 1 }));
    };
}); }};

// Warm scans with the inputs preprocessing actually read, and the builtins of the clock that no scan may be kept
// across. documentSymbol waits for the AST before completion: no claim about a cold completion or a deadline.
CTS scan_builtins{"module-scan-builtins", [] { against_subject([] {
    const std::pair<const char*, const char*> cases[] {
        { "macro", "#define JOIN_(a,b) a ## b\n#define JOIN(a,b) JOIN_(a,b)\n#define FLAG_ON 1\n#if JOIN(FLAG_,ON)\nimport M;\n#endif\n" },
        { "std-header", "#include <vector>\nimport M;\n" },
        { "inactive-and-literal", "#if 0\n__DATE__ __TIME__ __TIMESTAMP__\n#endif\nconst char *literal = \"__DATE__\";\nimport M;\n" },
        { "pasted-builtin", "#define JOIN_(a,b) a ## b\n#define JOIN(a,b) JOIN_(a,b)\n#if __has_include(JOIN(__DA,TE__))\nimport N;\n#endif\nimport M;\n" },
        { "direct-builtin", "#if __has_include(__TIME__)\nimport N;\n#endif\nimport M;\n" },
    };
    for (const auto& [name, prefix] : cases) {
        test { std::string { name } }[cts::needs { "linux" }] = [name = std::string { name }, prefix = std::string { prefix }] {
            const fs::path root { work("case-" + name) };
            const fs::path source { root / "Use.cpp" };
            const std::string text { prefix + "void probe() {\n  fn\n}\n" };
            write(source, text);
            const fs::path m { root / "M.cppm" }, n { root / "N.cppm" };
            write(m, "export module M;\nexport int fn_m() { return 1; }\n");
            write(n, "export module N;\nexport int fn_n() { return 1; }\n");
            write_database_for(root, { m, n, source });
            Session session { .id = name, .project = root, .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose" }, .timeout_seconds = 30 };
            session.sequence = json::array({ initialize(root), initialized(), did_open(source, text) });
            const int line { static_cast<int>(std::ranges::count(prefix, '\n')) + 1 };
            for (int version { 1 }; version < 4; ++version) {
                if (version > 1) session.sequence.push_back(did_change(source, version, text));
                session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(source) } });
                session.sequence.push_back(completion_at(source, line, 4, { "fn_m" }));
            }
            const json result = replay(session);
            passed(result, root);
            const auto hits = log_count(result, "Module dependency scan memo hit: " + str(source));
            const auto stores = log_count(result, "Module dependency scan memo stored: " + str(source));
            const auto declines = log_count(result, "Module dependency scan memo declined: " + str(source));
            std::println("{} {} hits {} stores {} declines {}", name, result.value("outcome", std::string {}), hits, stores, declines);
            if (name == "direct-builtin" || name == "pasted-builtin") {
                expect(hits == 0 && stores == 0 && declines > 0) << "a scan that read the clock was kept: hits " << hits << ", stores " << stores << ", declines " << declines;
            } else {
                expect(hits > 0 && stores > 0) << "a warm scan was not reused: hits " << hits << ", stores " << stores;
            }
        };
    }
}); }};

}  // namespace
