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
        const auto asked = [&](int line, int start, int end) { return json { { "method", "textDocument/codeAction" }, { "params", actions(line, start, end) } }; };
        session.sequence = json::array({
            initialize(root),
            initialized(),
            did_open(unit, text),
            asked(1, 8, 8),      // the class's name
            asked(10, 17, 22),   // an expression
            asked(10, 3, 3),     // `auto`
        });
        const json result = replay(session);
        passed(result, root);
        // What each request was answered with, by the refactoring's identifier: the order they are offered in is
        // the order their units registered in, which a link decides.
        std::vector<std::map<std::string, json>> offered;
        for (const auto& answer : result.value("raw_responses", json::array())) {
            if (answer.value("method", std::string {}) != "textDocument/codeAction") continue;
            auto& byId = offered.emplace_back();
            for (const auto& action : answer["reply"].value("result", json::array())) {
                const json* id { pointer(action, "/arguments/0/tweakID") };
                if (id != nullptr && id->is_string()) byId.emplace(id->get<std::string>(), action);
            }
        }
        expect(fatal(eq(offered.size(), std::size_t { 3 })));
        const auto has = [&](std::size_t request, const char* id, const char* title) {
            const auto found = offered[request].find(id);
            expect(fatal(found != offered[request].end())) << "the engine offered no " << id << " where one was asked for";
            expect(eq(found->second.value("command", std::string {}), std::string { "clangd.applyTweak" })) << id;
            if (title != nullptr) expect(eq(found->second.value("title", std::string {}), std::string { title })) << id;
        };
        has(0, "MemberwiseConstructor", "Define constructor");
        has(0, "SpecialMembers", "Declare implicit copy/move members");
        has(1, "ExtractVariable", nullptr);
        has(2, "ExpandDeducedType", nullptr);
    };
}); }};

}  // namespace
