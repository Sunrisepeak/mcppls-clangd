// What only a build tree can be asked: the engine's const suggestions beside clang-tidy's own,
// and the compiler's other completion consumers. The subject has `clang-tidy` and
// `frontend-tools` where the environment names those tools (src/harness.cppm); an image has
// neither, and these cases then say so.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

std::vector<std::string> lines_of(std::string_view text) {
    std::vector<std::string> lines;
    for (const auto part : std::views::split(text, '\n')) {
        std::string line { part.begin(), part.end() };
        if (!line.empty() && line.back() == '\r') line.pop_back();
        lines.push_back(std::move(line));
    }
    return lines;
}

// The variables a text says can be const: variable 'x' ... can be declared 'const'.
std::set<std::string> const_suggestions(std::string_view text) {
    std::set<std::string> names;
    for (const auto& line : lines_of(text)) {
        const auto begin = line.find("variable '");
        if (begin == std::string::npos) continue;
        const auto end = line.find('\'', begin + 10);
        if (end == std::string::npos || line.find("can be declared 'const'", end) == std::string::npos) continue;
        names.insert(line.substr(begin + 10, end - begin - 10));
    }
    return names;
}

// The engine's misc-const-correctness is clang-tidy's: the same variables, none of them an error, and the
// fixes clang-tidy writes compile. A view that is iterated is not const; a view over a const range is.
CTS const_correctness{"const-correctness", [] { against_subject([] {
    "the engine suggests const where clang-tidy does, and the fixes compile"_test[cts::needs{"clang-tidy"}] = [] {
        const std::string text {
            "#include <array>\n#include <ranges>\nstruct Number { int value; };\n"
            "int operator|(const Number &n, int mask) { return n.value | mask; }\n"
            "void check(const std::array<int, 4> &source) {\n"
            "  auto filtered = source | std::views::filter([](int v) { return v > 0; });\n"
            "  auto transformed = filtered | std::views::transform([](int v) { return v * 2; });\n"
            "  for (const int value : transformed) (void)value;\n"
            "  auto safe = source | std::views::transform([](int v) { return v * 2; });\n"
            "  auto safeAgain = safe | std::views::transform([](int v) { return v + 1; });\n"
            "  for (const int value : safeAgain) (void)value;\n"
            "  auto reference = std::ranges::ref_view(filtered);\n"
            "  for (const int value : reference) (void)value;\n"
            "  std::array<int, 4> mutableBase{};\n"
            "  for (int &value : mutableBase) value = 1;\n"
            "  Number input{3};\n  (void)(input | 1);\n  int answer = 42;\n  (void)answer;\n}\n" };
        const std::set<std::string> expected { "answer", "input", "reference", "safe", "safeAgain" };
        const fs::path root { work() };
        const fs::path source { root / "range.cpp" };
        write(source, text);
        write(root / ".clang-tidy", "Checks: '-*,misc-const-correctness'\n");
        write(root / ".clangd", "Diagnostics:\n  ClangTidy:\n    FastCheckFilter: None\n");
        write_database_for(root, { source });

        Client client { root, { "--sync", "--background-index=false", "--enable-config", "--clang-tidy" } };
        client.open_project(source);
        const json published = client.notification("textDocument/publishDiagnostics", [&](const json& params) { return params.value("uri", std::string {}) == uri(source); });
        client.stop();
        std::set<std::string> observed;
        for (const auto& diagnostic : published.value("diagnostics", json::array())) {
            expect(ne(diagnostic.value("severity", 0), 1)) << diagnostic.dump();
            observed.merge(const_suggestions(diagnostic.value("message", std::string {})));
        }
        expect(observed == expected) << "the engine suggests " << json(observed).dump() << ", expected " << json(expected).dump();

        const Ran tidied { tool({ str(subject().tidy), str(source), "-fix", "--", "-std=c++20" }, root, {}, 60) };
        expect(tidied.ok()) << tidied.out << tidied.err;
        expect(const_suggestions(tidied.out + tidied.err) == expected) << "clang-tidy disagrees: " << tidied.out << tidied.err;
        const Ran compiled { tool({ str(subject().clang), "-std=c++20", "-fsyntax-only", str(source) }, root, {}, 60) };
        expect(compiled.ok()) << "the const fixes do not compile: " << compiled.err;
    };
}); }};

// The compiler's own completion (the driver, the C index) answers the same from the text of a header and from
// its PCH: both overloads and the second name. The interpreter runs a declaration. No claim about interactive
// completion or how fast any of it is.
CTS consumers{"frontend-completion-consumers", [] { against_subject([] {
    "the compiler's completion consumers agree on text and PCH"_test[cts::needs{"frontend-tools"}] = [] {
        const fs::path root { work() };
        const fs::path header { root / "API.h" }, source { root / "Use.cpp" };
        write(header, "namespace api {\nint vector(int count);\nint vector(double amount);\nint version();\nint ordinary;\n}\n");
        const std::string text { "void probe() { api::ve; }\n" };
        write(source, text);
        const std::string at { std::format("{}:1:{}", str(source), text.find("ve;") + 3) };
        const std::string clang { str(subject().clang) }, index { str(subject().cIndexTest) };
        const auto run = [&](const char* stage, std::vector<std::string> argv, std::string input = {}) {
            const Ran ran { tool(std::move(argv), root, std::move(input)) };
            expect(fatal(ran.ok())) << stage << ": status " << ran.status << "\n" << ran.err;
            expect(fatal(ran.out.size() <= 2 * 1048576 && ran.err.size() <= 2 * 1048576)) << stage << " wrote more than a consumer does";
            return ran;
        };
        const auto chosen = [](const Ran& ran, std::string_view prefix) {
            std::vector<std::string> lines;
            for (auto& line : lines_of(ran.out))
                if (line.starts_with(prefix)) lines.push_back(std::move(line));
            std::ranges::sort(lines);
            return lines;
        };
        const auto count = [](const std::vector<std::string>& lines, std::string_view part, bool atStart) {
            return std::ranges::count_if(lines, [&](const std::string& line) { return atStart ? line.starts_with(part) : line.contains(part); });
        };

        const fs::path pch { root / "API.pch" };
        run("clang-build-pch", { clang, "-x", "c++-header", "-std=c++20", str(header), "-o", str(pch) });
        expect(fatal(fs::is_regular_file(pch))) << "the driver wrote no PCH";
        std::vector<std::vector<std::string>> driver;
        for (const auto& include : { std::vector<std::string> { "-include", str(header) }, std::vector<std::string> { "-include-pch", str(pch) } }) {
            std::vector<std::string> argv { clang, "-std=c++20", "-fsyntax-only" };
            argv.insert(argv.end(), include.begin(), include.end());
            argv.insert(argv.end(), { "-Xclang", "-code-completion-at=" + at, str(source) });
            driver.push_back(chosen(run("clang-completion", argv), "COMPLETION:"));
            expect(eq(count(driver.back(), "COMPLETION: vector :", true), 2)) << "the driver lost an overload of vector";
            expect(ge(count(driver.back(), "COMPLETION: version :", true), 1)) << "the driver lost version";
        }
        expect(driver[0] == driver[1]) << "the driver's completion differs between text and PCH";

        const fs::path indexPch { root / "API-index.pch" };
        run("index-build-pch", { index, "-write-pch", str(indexPch), "-x", "c++-header", "-std=c++20", str(header) });
        expect(fatal(fs::is_regular_file(indexPch))) << "the C index wrote no PCH";
        std::vector<std::vector<std::string>> indexed;
        for (const auto& include : { std::vector<std::string> { "-include", str(header) }, std::vector<std::string> { "-include-pch", str(indexPch) } }) {
            std::vector<std::string> argv { index, "-code-completion-at=" + at, "-std=c++20" };
            argv.insert(argv.end(), include.begin(), include.end());
            argv.push_back(str(source));
            indexed.push_back(chosen(run("index-completion", argv), "FunctionDecl:"));
            expect(eq(count(indexed.back(), "{TypedText vector}", false), 2)) << "the C index lost an overload of vector";
            expect(ge(count(indexed.back(), "{TypedText version}", false), 1)) << "the C index lost version";
        }
        expect(indexed[0] == indexed[1]) << "the C index's completion differs between text and PCH";

        const Ran interpreted { run("interpreter", { str(subject().repl) }, "int value = 41;\nint next = value + 1;\n%quit\n") };
        expect(!(interpreted.out + interpreted.err).contains("error:")) << interpreted.out << interpreted.err;
        expect(eq(read(source), text)) << "a consumer changed the source";
    };
}); }};

}  // namespace
