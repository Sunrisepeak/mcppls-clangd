// Module directives that are not finished: where the diagnostic is, that the file recovers, and
// that a graph with a cycle is refused and left behind by an edit.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

// A missing separator is reported on the directive's own line.
CTS directive_diagnostics{"module-directive-diagnostics", [] { against_subject([] {
    struct Case {
        const char* name;
        const char* code;
        const char* diagnostic;
        int line, character;
    };
    static const Case CASES[] {
        { "import", "import A\nimport B;\n", "expected_semi_after_module_or_import", 0, 8 },
        { "continued-import", "import \\\n  A\nimport B;\n", "expected_semi_after_module_or_import", 1, 3 },
        { "module", "export module M // pending\nint marker;\n", "pp_unexpected_tok_after_module_name", 0, 15 },
        { "continued-module", "export module \\\n  M\nint marker;\n", "pp_unexpected_tok_after_module_name", 1, 3 },
    };
    // One engine reads every file; each part asks about its own.
    std::optional<LitTest> probed;
    const auto probe = [&]() -> const LitTest& {
        if (probed) return *probed;
        json messages = json::array({ json { { "jsonrpc", "2.0" }, { "id", 0 }, { "method", "initialize" },
            { "params", json { { "rootUri", "test:///" }, { "capabilities", json::object() },
                               { "initializationOptions", json { { "fallbackFlags", json::array({ "-std=c++20" }) } } } } } } });
        for (const auto& c : CASES) {
            messages.push_back(json { { "jsonrpc", "2.0" }, { "method", "textDocument/didOpen" },
                { "params", json { { "textDocument", json { { "uri", std::format("test:///{}.cpp", c.name) }, { "languageId", "cpp" }, { "version", 1 }, { "text", c.code } } } } } });
        }
        messages.push_back(json { { "jsonrpc", "2.0" }, { "id", 1 }, { "method", "shutdown" }, { "params", nullptr } });
        messages.push_back(json { { "jsonrpc", "2.0" }, { "method", "exit" } });
        probed = lit_test(messages, { "--background-index=false" });
        return *probed;
    };
    "the engine reads the files and leaves cleanly"_test = [&] {
        const LitTest& ran { probe() };
        expect(fatal(ran.problem.empty())) << ran.problem;
        expect(eq(ran.status, 0)) << ran.log;
        expect(std::ranges::any_of(ran.replies, [](const json& r) { return r.value("id", json(nullptr)) == json(1) && r.contains("result") && r["result"].is_null(); }))
            << "shutdown was not answered";
    };
    for (const auto& c : CASES) {
        test { std::string { c.name } } = [&probe, c] {
            const LitTest& ran { probe() };
            json found = json::array();
            for (const auto& reply : ran.replies) {
                if (reply.value("method", std::string {}) != "textDocument/publishDiagnostics") continue;
                // The test mode resolves test:/// into its platform's own root.
                if (!reply["params"].value("uri", std::string {}).ends_with(std::format("/{}.cpp", c.name))) continue;
                for (const auto& diagnostic : reply["params"].value("diagnostics", json::array()))
                    if (diagnostic.value("code", json(nullptr)) == json(c.diagnostic)) found.push_back(diagnostic);
            }
            const json at = position(c.line, c.character);
            expect(fatal(eq(found.size(), std::size_t { 1 }))) << c.diagnostic << ": " << found.dump();
            expect(found[0].value("range", json(nullptr)) == json { { "start", at }, { "end", at } }) << found[0].dump();
        };
    }
}); }};

// A directive that is not finished is recovered from: the file is answered for after a real edit, closed and
// opened again, and the engine leaves cleanly. No claim about cancelling a request or a module that is missing.
CTS directive_recovery{"module-directive-recovery", [] { against_subject([] {
    const std::pair<const char*, const char*> variants[] {
        { "import-dot", "import hello.\n" },
        { "module-dot", "export module hello.\n" },
        { "qualified-import", "import a.b.\n" },
        { "import-comment", "import hello. // unfinished\n" },
        { "import-next-line-semicolon", "import hello.\n;\n" },
        { "global-fragment-module", "module;\nexport module hello.\n" },
    };
    for (const auto& [name, malformed] : variants) {
        test { std::string { name } } = [name = std::string { name }, malformed = std::string { malformed }] {
            const fs::path root { work(name) };
            const fs::path source { root / "Use.cpp" };
            const std::string text { malformed + "int discardedByRecovery;\n" }, fixed { "int marker;\n" };
            write(source, text);
            write_database_for(root, { source });
            const json marker { { "/result/0/name", "marker" } };
            Session session { .id = name, .project = root, .flags = { "--sync", "--background-index=false" }, .timeout_seconds = 10 };
            session.sequence = json::array({
                initialize(root), initialized(), did_open(source, text, 1),
                json { { "method", "textDocument/documentSymbol" }, { "params", document(source) } },
                did_change(source, 2, fixed),
                json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", marker } },
                json { { "method", "textDocument/didClose" }, { "notify", true }, { "params", document(source) } },
                did_open(source, fixed, 3),
                json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", marker } },
                json { { "method", "textDocument/didClose" }, { "notify", true }, { "params", document(source) } },
            });
            passed(replay(session), root);
        };
    }
}); }};

// A cyclic prerequisite graph is refused and an edit leaves it behind; afterwards a real diamond over the same
// names builds, the shared module not taken for a cycle. No claim about how a graph is scheduled.
CTS cycle{"module-cycle", [] { against_subject([] {
    "a cycle is refused, and a diamond over the same names is built"_test = [] {
        const fs::path root { work() };
        const fs::path source { root / "Use.cpp" };
        write(root / "A.cppm", "export module A;\nimport B;\nexport int a;\n");
        write(root / "B.cppm", "export module B;\nimport A;\nexport int b;\n");
        write(source, "import A;\nint marker;\n");
        write_database_for(root, { root / "A.cppm", root / "B.cppm", source });
        Session session { .id = "cyclic-module-recovery", .project = root, .flags = { "--experimental-modules-support", "--background-index=false", "-j=2" },
                          .timeout_seconds = 10 };
        session.sequence = json::array({
            initialize(root), initialized(), did_open(source, read(source)),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(source) } },
            json { { "action", "await-log" }, { "contains", "Cyclic module dependency involving A" } },
            did_change(source, 2, "int healthy;\n"),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", json { { "/result/0/name", "healthy" } } } },
        });
        passed(replay(session), root);

        // A second process sees a real diamond after the cyclic providers change.
        const std::pair<const char*, const char*> diamond[] {
            { "A.cppm", "export module A;\nexport import B;\nexport import C;\n" },
            { "B.cppm", "export module B;\nexport import D;\nexport int b;\n" },
            { "C.cppm", "export module C;\nexport import D;\nexport int c;\n" },
            { "D.cppm", "export module D;\nexport int d;\nexport int diamond_value;\n" },
            { "Use.cpp", "import A;\nint marker = b + c + d;\nvoid probe() { diamond_; }\n" },
        };
        json commands = json::array();
        for (const auto& [name, contents] : diamond) {
            write(root / name, contents);
            commands.push_back(compile_command(root, root / name, { "-std=c++20", "-c", str(root / name) }));
        }
        write_database(root, commands);
        json params = document(source);
        params["position"] = position(2, static_cast<int>(std::string_view { "void probe() { diamond_" }.size()));
        Session shared { .id = "diamond-module-recovery", .project = root, .flags = session.flags, .timeout_seconds = 10 };
        shared.sequence = json::array({
            initialize(root), initialized(), did_open(source, read(source)),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(source) }, { "expect", json { { "/result/0/name", "marker" } } } },
            json { { "action", "await-log" }, { "contains", "Built module A to " } },
            json { { "method", "textDocument/completion" }, { "params", params }, { "expected_symbols", json::array({ "diamond_value" }) } },
        });
        const json built = replay(shared);
        passed(built, root);
        expect(!built.value("stderr", std::string {}).contains("Failed to build module")) << "valid diamond failed to build";
    };
}); }};

// A document whose build waits on a module's lock held by a live owner is closed: its request is cancelled, another
// file is answered for, the lock is left where it is, and the engine leaves cleanly.
CTS lock_close{"module-lock-close", [] { against_subject([] {
    "a document that waits on a live owner's lock can be closed"_test = [] {
        const fs::path root { work() };
        const fs::path module { root / "A.cppm" }, source { root / "Use.cpp" }, healthy { root / "Healthy.cpp" };
        write(module, "export module A;\nexport int item;\n");
        write(source, "import A;\nint marker;\n");
        write(healthy, "int healthy;\n");
        write_database_for(root, { module, source, healthy });
        const auto symbols = [](const fs::path& file) { return json { { "method", "textDocument/documentSymbol" }, { "params", document(file) } }; };
        const auto session_of = [&](json steps) {
            Session session { .id = "live-owner-close", .project = root, .flags = { "--experimental-modules-support", "--background-index=false", "-j=2" },
                              .timeout_seconds = 15 };
            session.sequence = json::array({ initialize(root), initialized() });
            for (auto& step : steps) session.sequence.push_back(std::move(step));
            return session;
        };
        json warmSymbols = symbols(source);
        warmSymbols["expect"] = json { { "/result/0/name", "marker" } };
        passed(replay(session_of(json::array({ did_open(source, read(source)), warmSymbols }))), root);

        const fs::path cache { root / ".cache/clangd/modules" };
        std::vector<fs::path> anchors;
        std::error_code failed;
        for (fs::directory_iterator entry { cache / ".locks", failed }, end; !failed && entry != end; entry.increment(failed))
            if (entry->is_regular_file() && !entry->path().filename().string().contains('.')) anchors.push_back(entry->path());
        expect(fatal(eq(anchors.size(), std::size_t { 1 }))) << "expected one real source lock anchor from the module builder";
        fs::path lock { anchors.front() };
        lock += ".lock";
        // The owner the lock names is this program, which lives. No newline: the engine reads a number to the end.
        const std::string owner { std::format("{} {}", host_name(), own_pid()) };
        expect(fatal(!fs::exists(lock))) << "the lock is already there";
        write(lock, owner);
        struct Unlock {
            fs::path lock;
            std::string owner;
            ~Unlock() {
                std::error_code ignored;
                if (contents(lock) == owner) fs::remove(lock, ignored);
            }
        } unlock { lock, owner };
        for (const auto& bmi : files_under(cache, [](const fs::directory_entry& e) { return e.path().extension() == ".pcm"; })) fs::remove(bmi);

        json blocked = symbols(source);
        blocked["defer"] = "blocked";
        json healthySymbols = symbols(healthy);
        healthySymbols["expect"] = json { { "/result/0/name", "healthy" } };
        const json result = replay(session_of(json::array({
            did_open(source, read(source)), blocked,
            json { { "action", "await-log" }, { "contains", "Still waiting for module lock" } },
            json { { "method", "$/cancelRequest" }, { "notify", true }, { "params", json { { "id", "${REQUEST:blocked}" } } } },
            json { { "method", "textDocument/didClose" }, { "notify", true }, { "params", document(source) } },
            did_open(healthy, read(healthy)), healthySymbols,
            json { { "action", "await" }, { "request", "blocked" }, { "allow_error", true }, { "expect", json { { "/error/code", -32800 } } } },
        })));
        passed(result, root);
        expect(fs::exists(lock) && contents(lock) == owner) << "the live owner's lock was not preserved";
    };
}); }};

}  // namespace
