// A module's members where a completion is asked for: after `.`, after a prefix, after `->`, on a
// line that is not the file's last; and after the module's interface changed, on disk within the
// same second or only in an open draft. A small module of its own: no SDK, no standard library.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

void quality(bool unsavedUpdate, bool asyncScheduling) {
    const fs::path project { work() };
    const fs::path module { project / "Api.cppm" }, source { project / "Use.cpp" };
    write(module, "export module Api;\nexport struct Cli {\n  void addHelpOption();\n  void addOption();\n};\n");
    json commands = json::array();
    for (const auto& file : { module, source }) commands.push_back(compile_command(project, file, { "-std=c++20", "-c", str(file), "-o", str(file) + ".o" }));
    write_database(project, commands);
    const std::pair<const char*, const char*> shapes[] { { "member", "cli." }, { "member-prefix", "cli.ad" }, { "pointer", "ptr->" } };
    for (const auto& [name, prefix] : shapes) {
        const std::string text { std::string { "import Api;\nvoid qVersion();\nvoid Counter();\nvoid AdlTester();\n"
                                               "void f() {\n  Cli cli;\n  Cli* ptr = &cli;\n  " }
                                 + prefix + "\n}\n// This final line is unrelated to the completion context.\n" };
        write(source, text);
        Session session { .id = name, .project = project,
                          .flags = { "--experimental-modules-support", "--background-index=false", "--header-insertion=never", "--log=verbose", "--use-dirty-headers", "-j=2" },
                          .timeout_seconds = 30 };
        if (!asyncScheduling) session.flags.push_back("--sync");
        json params = document(source);
        params["position"] = position(7, 2 + static_cast<int>(std::string_view { prefix }.size()));
        const json members { { "method", "textDocument/completion" }, { "params", params },
                             { "expected_symbols", json::array({ "addHelpOption", "addOption" }) },
                             { "forbidden_symbols", json::array({ "qVersion", "Counter", "AdlTester" }) } };
        const json symbols { { "method", "textDocument/documentSymbol" }, { "params", document(source) } };
        session.sequence = json::array({ initialize(project), initialized(), did_open(source, text), symbols, members });
        if (std::string_view { name } == "member") {
            session.sequence.push_back(did_change(source, 2, text + "// warm validation\n"));
            session.sequence.push_back(symbols);
            session.sequence.push_back(members);
            std::string updated { text };
            updated.replace(updated.find("cli."), 4, "cli.fre");
            if (unsavedUpdate) {
                std::string draft { read(module) };
                draft.replace(draft.find("addOption"), 9, "freshItem");
                session.sequence.push_back(did_open(module, draft));
            } else {
                session.sequence.push_back(json { { "action", "replace-file" }, { "file", "Api.cppm" }, { "from", "addOption" }, { "with", "freshItem" }, { "same-second", true } });
                session.sequence.push_back(json { { "method", "workspace/didChangeWatchedFiles" }, { "notify", true },
                                                  { "params", json { { "changes", json::array({ json { { "uri", uri(module) }, { "type", 2 } } }) } } } });
            }
            session.sequence.push_back(did_change(source, 3, updated));
            session.sequence.push_back(symbols);
            json fresh = document(source);
            fresh["position"] = position(7, 9);
            // Answered at once from the modules before the edit while the rebuild goes on.
            session.sequence.push_back(json { { "method", "textDocument/completion" }, { "params", fresh }, { "expected_symbols", json::array({ "freshItem" }) },
                                              { "forbidden_symbols", json::array({ "addOption" }) }, { "retry_seconds", 20 } });
        }
        passed(replay(session), project);
    }
}

CTS module_quality{"module-quality", [] { against_subject([] {
    "members after an edit of the module on disk"_test = [] { quality(false, true); };
}); }};

CTS module_drafts{"module-drafts", [] { against_subject([] {
    "members after an edit of the module in an open draft"_test = [] { quality(true, true); };
}); }};

}  // namespace
