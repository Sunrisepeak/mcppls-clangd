// Completion over modules: the first answer of a cold session, the answer after a response file
// changed with the database and the draft as they were, and the names across changes of what the
// file's preamble is.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

json complete(const fs::path& file, int line, int character, std::vector<std::string> required, std::vector<std::string> forbidden = {}) {
    json params = document(file);
    params["position"] = position(line, character);
    json step { { "method", "textDocument/completion" }, { "params", std::move(params) }, { "expected_symbols", std::move(required) } };
    if (!forbidden.empty()) step["forbidden_symbols"] = std::move(forbidden);
    return step;
}

// Imported symbols arrive without an AST barrier: the first answer, given within the first-preamble
// wait, is marked incomplete until the module is built, and asked again it carries the module's names.
CTS cold{"module-cold-completion", [] { against_subject([] {
    "the first completion of a session carries the module's names"_test = [] {
        // A directory of its own: this session never borrows another's BMI.
        const fs::path project { work("cold") };
        const fs::path module { project / "M.cppm" }, source { project / "Use.cpp" };
        write(module, "export module M;\nexport int fn_m() { return 1; }\n");
        const std::string text { "import M;\nvoid probe() { fn; }\n" };
        write(source, text);
        write_database_for(project, { module, source });
        Session session { .id = "module-first-completion", .project = project,
                          .flags = { "--experimental-modules-support", "--background-index=false" }, .timeout_seconds = 40 };
        session.sequence = json::array({ initialize(project), initialized(), did_open(source, text), complete(source, 1, 17, { "fn_m" }) });
        passed(replay(session), project);
        expect(eq(read(source), text)) << "the source on disk changed";
    };
}); }};

// Response edits must refresh module inputs with unchanged JSON and draft.
CTS response_inputs{"module-response-inputs", [] { against_subject([] {
    "a response file's edit reaches the module the file imports"_test = [] {
        const fs::path root { work() };
        const fs::path use { root / "Use.cpp" };
        std::vector<fs::path> modules;
        for (const std::string name : { "M", "N" }) {
            std::string lower { name };
            lower[0] = static_cast<char>(std::tolower(static_cast<unsigned char>(lower[0])));
            modules.push_back(root / (name + ".cppm"));
            write(modules.back(), std::format("export module {};\nexport int fn_{}() {{ return 1; }}\n", name, lower));
        }
        write(root / "flags.rsp", "-DMODE=1\n");
        const std::string text { "#if MODE == 1\nimport M;\n#else\nimport N;\n#endif\nvoid probe() { fn; }\n" };
        write(use, text);
        json commands = json::array();
        for (const auto& provider : modules) commands.push_back(compile_command(root, provider, { "-std=c++20", "-c", str(provider) }));
        commands.push_back(compile_command(root, use, { "-std=c++20", "@flags.rsp", "-c", str(use) }));
        write_database(root, commands);
        const std::string database { read(root / "compile_commands.json") };

        Session session { .id = "response-command-generation", .project = root,
                          .flags = { "--experimental-modules-support", "--background-index=false", "--log=verbose" }, .timeout_seconds = 40 };
        session.sequence = json::array({ initialize(root), initialized(), did_open(use, text) });
        const auto probe = [&](const char* symbol) {
            session.sequence.push_back(json { { "method", "textDocument/documentSymbol" }, { "params", document(use) } });
            session.sequence.push_back(complete(use, 5, 17, { symbol }));
        };
        probe("fn_m");
        session.sequence.push_back(json { { "action", "replace-file" }, { "file", "flags.rsp" }, { "from", "-DMODE=1" }, { "with", "-DMODE=2" }, { "preserve-mtime", true } });
        session.sequence.push_back(did_change(use, 2, text));
        probe("fn_n");
        passed(replay(session), root);
        expect(eq(read(root / "compile_commands.json"), database)) << "the database changed";
        expect(eq(read(use), text)) << "the importer on disk changed";
    };
}); }};

// The current module's symbols across changes of the preamble's mode, without AST barriers.
void preamble_mode(std::vector<std::string> engineFlags) {
    const fs::path project { work("mode") };
    const fs::path source { project / "Use.cpp" }, header { project / "imports.h" };
    const std::string text { "#include \"imports.h\"\nvoid probe() { fn; }\n" };
    write(source, text);
    write(header, "import M;\n");
    const fs::path m { project / "M.cppm" }, n { project / "N.cppm" };
    write(m, "export module M;\nexport int fn_m() { return 1; }\n");
    write(n, "export module N;\nexport int fn_n() { return 1; }\n");
    write_database_for(project, { m, n, source });
    Session session { .id = "completion-preamble-mode-transitions", .project = project,
                      .flags = { "--experimental-modules-support", "--background-index=false" }, .timeout_seconds = 40 };
    for (auto& flag : engineFlags) session.flags.push_back(std::move(flag));
    session.sequence = json::array({ initialize(project), initialized(), did_open(source, text) });
    session.sequence.push_back(complete(source, 1, 17, { "fn_m" }, { "fn_n" }));
    session.sequence.push_back(json { { "action", "replace-file" }, { "file", "imports.h" }, { "from", "import M;" }, { "with", "import N;" }, { "preserve-mtime", true } });
    session.sequence.push_back(complete(source, 1, 17, { "fn_n" }, { "fn_m" }));
    session.sequence.push_back(did_change(source, 2, "int textual_value;\nvoid probe() { tex; }\n"));
    session.sequence.push_back(complete(source, 1, 18, { "textual_value" }, { "fn_m", "fn_n" }));
    session.sequence.push_back(did_change(source, 3, "import M;\nvoid probe() { fn; }\n"));
    session.sequence.push_back(complete(source, 1, 17, { "fn_m" }, { "fn_n" }));
    passed(replay(session), project);
    expect(eq(read(source), text)) << "the source on disk changed";
}

CTS preamble{"module-preamble-mode", [] { against_subject([] {
    "the names follow the header's import, then the draft's"_test = [] { preamble_mode({}); };
}); }};

}  // namespace
