// A compiler's own extensions where a completion is asked for: GNU attributes, and Windows'
// structured exceptions only for a target that has them; never in an expression, a comment or
// a string. What is inserted is given to the compiler the command names. Semantic and syntax
// checks of their own: not evidence about crashes or a long run.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

using Words = std::vector<std::string>;

const Words LINUX { "-std=c++20", "--target=x86_64-unknown-linux-gnu" };
const Words WINDOWS { "-std=c++20", "--target=x86_64-pc-windows-msvc", "-fms-extensions" };

Words with(Words words, std::initializer_list<const char*> more) {
    for (const char* word : more) words.emplace_back(word);
    return words;
}

struct Case {
    std::string name, prefix, text;
    Words flags, expected, forbidden;
    std::map<std::string, Words> fragments;   // what a snippet has to hold, by the name it completes
    std::string last;                         // what fills a snippet's final field
};

std::vector<Case> cases() {
    return {
        { "gnu-introducer", "__attr", "__attr\nint marker;\n", LINUX, { "__attribute__" }, {}, { { "__attribute__", { "__attribute__((", "))" } } }, "used" },
        { "gnu-cleanup", "cle", "void release(int*);\nvoid f() { int value __attribute__((cle)); }\n", LINUX, { "cleanup" }, { "__try" },
          { { "cleanup", { "cleanup(", ")" } } }, "release" },
        { "gnu-cleanup-function", "rel",
          "void release(int*);\nvoid releaseWrong();\nvoid releaseValue(int);\nvoid releasePair(int*, int);\nint releaseData;\n"
          "void f() { int value __attribute__((cleanup(rel))); }\n",
          LINUX, { "release" }, { "cleanup", "__try", "__attribute__", "releaseWrong", "releaseValue", "releasePair", "releaseData" }, {}, "" },
        { "windows-seh", "__tr", "void f() {\n  __tr\n}\n", WINDOWS, { "__try" }, {}, { { "__try", { "__try {", "__except(", "filter-expression", "$0" } } }, "" },
        { "visible-gnu-macro", "__tr", "#define __try 1\nvoid f() { int value = __tr; }\n", LINUX, { "__try" }, {}, {}, "" },
        { "linux-no-seh", "__tr", "void f() {\n  __tr\n}\n", with(LINUX, { "-fms-extensions" }), {}, { "__try" }, {}, "" },
        { "windows-mode-off", "__tr", "void f() {\n  __tr\n}\n", { "-std=c++20", "--target=x86_64-pc-windows-msvc", "-fno-ms-extensions" }, {}, { "__try" }, {}, "" },
        { "expression-not-attribute", "__attr", "void f() { int value = __attr; }\n", LINUX, {}, { "__attribute__", "cleanup", "__try" }, {}, "" },
        { "ordinary-cleanup", "cle", "void f() { cle; }\n", LINUX, {}, { "cleanup" }, {}, "" },
        { "comment", "__attr", "void f() { // __attr\n}\n", LINUX, {}, { "__attribute__", "cleanup", "__try" }, {}, "" },
        { "string", "__attr", "const char* value = \"__attr\";\n", LINUX, {}, { "__attribute__", "cleanup", "__try" }, {}, "" },
    };
}

// A snippet with its fields filled: `${n:name}` by what the caller chose for `name`, `$0` by `last`, `$n` by nothing.
std::string filled(std::string_view snippet, const std::string& last) {
    const std::map<std::string_view, std::string_view> fields { { "statements", "int value = 0; (void)value;" }, { "filter-expression", "1" } };
    std::string out;
    for (std::size_t at { 0 }; at < snippet.size();) {
        if (snippet[at] != '$') {
            out += snippet[at++];
            continue;
        }
        std::size_t digits { at + 1 };
        const bool braced { digits < snippet.size() && snippet[digits] == '{' };
        if (braced) ++digits;
        std::size_t end { digits };
        while (end < snippet.size() && std::isdigit(static_cast<unsigned char>(snippet[end]))) ++end;
        if (end == digits) {
            out += snippet[at++];
            continue;
        }
        if (!braced) {
            if (snippet.substr(digits, end - digits) == "0") out += last;
            at = end;
            continue;
        }
        const auto close = snippet.find('}', end);
        if (end >= snippet.size() || snippet[end] != ':' || close == std::string_view::npos) {
            out += snippet[at++];
            continue;
        }
        if (const auto field = fields.find(snippet.substr(end + 1, close - end - 1)); field != fields.end()) out += field->second;
        at = close + 1;
    }
    return out;
}

std::size_t offset_of(std::string_view text, const json& at) {
    std::size_t offset { 0 };
    for (int line { at.value("line", 0) }; line > 0; --line) offset = text.find('\n', offset) + 1;
    return offset + at.value("character", std::size_t { 0 });
}

CTS extensions{"compiler-extensions", [] { against_subject([] {
    for (const Case& c : cases()) {
        test { std::string { c.name } } = [c] {
            const fs::path root { work(c.name) };
            const fs::path source { root / "test.cpp" };
            write(source, c.text);
            Words arguments { c.flags };
            arguments.insert(arguments.end(), { "-c", str(source) });
            write_database(root, json::array({ compile_command(root, source, arguments) }));
            json step = completion_at(source, position_after(c.text, c.prefix, true));
            step["params"].erase("context");
            step["expected_symbols"] = c.expected;
            step["forbidden_symbols"] = c.forbidden;
            if (!c.fragments.empty()) step["expected_snippet_fragments"] = c.fragments;
            Session session { .id = c.name, .project = root, .flags = { "--sync", "--background-index=false", "--header-insertion=never" }, .timeout_seconds = 20 };
            json begin = initialize(root);
            begin["params"]["capabilities"] = json::parse(R"({"textDocument": {"completion": {"completionItem": {"snippetSupport": true}}}})");
            session.sequence = json::array({ begin, initialized(), did_open(source, c.text), step });
            const json result = replay(session);
            passed(result, root);
            if (c.expected.empty()) return;
            // The edit the engine answered with is applied, its fields filled, and the compiler of the command's
            // target is asked whether it accepts the result.
            const json* edit { pointer(result, "/responses/0/completion_items/" + c.expected.front() + "/0/textEdit") };
            expect(fatal(edit != nullptr)) << "the completion carries no edit";
            const std::string applied { c.text.substr(0, offset_of(c.text, (*edit)["range"]["start"])) + filled((*edit)["newText"].get<std::string>(), c.last)
                                        + c.text.substr(offset_of(c.text, (*edit)["range"]["end"])) };
            const fs::path inserted { root / "inserted.cpp" };
            write(inserted, applied);
            Words command { str(subject().clang) };
            command.insert(command.end(), c.flags.begin(), c.flags.end());
            command.insert(command.end(), { "-fsyntax-only", str(inserted) });
            const Ran compiled { tool(command, root, {}, 20) };
            expect(compiled.ok()) << "the compiler refuses what was inserted:\n" << applied << compiled.err;
        };
    }

    "the compiler takes each extension only for its target"_test = [] {
        struct Source {
            const char* name;
            const char* text;
            Words flags;
            int status;
        };
        const Source sources[] {
            { "gnu", "void release(int*) {}\n__attribute__((noinline)) void f() { int value __attribute__((cleanup(release))) = 0; }\n", LINUX, 0 },
            { "windows", "void f() { __try { int value = 0; (void)value; } __except (1) {} }\n", WINDOWS, 0 },
            { "linux-rejects-seh", "void f() { __try {} __except (1) {} }\n", with(LINUX, { "-fms-extensions" }), 1 },
        };
        const fs::path root { work() };
        for (const auto& s : sources) {
            const fs::path source { root / (std::string { s.name } + ".cpp") };
            write(source, s.text);
            Words command { str(subject().clang) };
            command.insert(command.end(), s.flags.begin(), s.flags.end());
            command.insert(command.end(), { "-fsyntax-only", str(source) });
            const Ran compiled { tool(command, root, {}, 20) };
            expect(compiled.started && !compiled.timed_out && compiled.status == s.status) << s.name << ": status " << compiled.status << "\n" << compiled.err;
            if (s.status != 0) expect(contains(compiled.err, std::string { "SEH '__try' is not supported on this target" })) << s.name;
        }
    };
}); }};

}  // namespace
