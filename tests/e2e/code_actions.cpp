// The engine offers its refactorings.
//
// clangd's refactorings (its tweaks: "Define constructor", "Extract to function", "Expand macro"
// and the rest) are an object library whose every unit registers itself when the program starts;
// nothing refers to them, so clangd's link names their objects one by one. The ok image is linked
// from the libraries of that line, and through 0.0.22 from the libraries alone: it carried no
// refactoring, and answered every request for code actions that no diagnostic's fix answers with
// an empty list (mcpp-language-server issue 89).
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

CTS code_actions{"code-actions", [] { against_subject([] {
    "a class's name, an expression and a deduced type each have their refactoring"_test = [] {
        const fs::path root { work() };
        const fs::path unit { root / "pass.cpp" };
        const std::string text {
            "namespace render {\n"
            "class FinalPass {\n"
            "public:\n"
            "  static int create(int a);\n"
            "private:\n"
            "  int width_;\n"
            "  int height_;\n"
            "};\n"
            "}\n"
            "int area(int w, int h) {\n"
            "  auto doubled = w * 2;\n"
            "  return doubled * h;\n"
            "}\n" };
        write(unit, text);
        write_database_for(root, { unit });
        const auto actions = [&](int line, int start, int end) {
            json params = document(unit);
            params["range"] = json { { "start", position(line, start) }, { "end", position(line, end) } };
            params["context"] = json { { "diagnostics", json::array() } };
            return params;
        };
        Session session { .id = "code-actions", .project = root, .flags = { "--background-index=false", "-j=2", "--log=verbose" }, .timeout_seconds = 120 };
        session.sequence = json::array({
            initialize(root),
            initialized(),
            did_open(unit, text),
            // On the class's name: its constructor and its special members. The engine orders what it offers by name.
            json { { "method", "textDocument/codeAction" }, { "params", actions(1, 8, 8) },
                   { "expect", json { { "/result/0/title", "Define constructor" }, { "/result/0/command", "clangd.applyTweak" },
                                      { "/result/0/arguments/0/tweakID", "MemberwiseConstructor" },
                                      { "/result/1/title", "Declare implicit copy/move members" },
                                      { "/result/1/arguments/0/tweakID", "SpecialMembers" } } } },
            // On an expression: it can be given a name.
            json { { "method", "textDocument/codeAction" }, { "params", actions(10, 17, 22) },
                   { "expect", json { { "/result/0/arguments/0/tweakID", "ExtractVariable" } } } },
            // On `auto`: the type it stands for.
            json { { "method", "textDocument/codeAction" }, { "params", actions(10, 3, 3) },
                   { "expect", json { { "/result/0/arguments/0/tweakID", "ExpandDeducedType" } } } },
        });
        passed(replay(session), root);
    };
}); }};

}  // namespace
