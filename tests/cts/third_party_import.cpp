// An import the project cannot resolve (a toolchain's module seen through another compiler's
// profile) beside modules it can: the resolvable ones are built and answered from, a preamble
// with such an import is kept or dropped by what it holds, and a provider that appears through
// the compile commands reaches files that had none. The import stays text: no claim that a
// toolchain's module is mapped.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

const std::vector<std::string> FLAGS { "--experimental-modules-support", "--background-index=false", "-j=2" };

std::size_t count_of(std::string_view text, std::string_view part) {
    std::size_t count { 0 };
    for (auto at = text.find(part); at != std::string_view::npos; at = text.find(part, at + part.size())) ++count;
    return count;
}

json expecting(json step, std::initializer_list<const char*> symbols, const char* key = "expected_symbols") {
    step[key] = json::array();
    for (const char* symbol : symbols) step[key].push_back(symbol);
    return step;
}

json symbols_named(const fs::path& file, const char* first) {
    return json { { "method", "textDocument/documentSymbol" }, { "params", document(file) }, { "expect", json { { "/result/0/name", first } } } };
}

CTS third_party{"third-party-import", [] { against_subject([] {
    // The prerequisite builder once discarded every module it had built and failed for good: each request then
    // built the dependencies again and parsed without a preamble.
    "a module beside an import that cannot be resolved is built once and answered from"_test = [] {
        const fs::path root { work() };
        const fs::path dep { root / "dep.cppm" }, source { root / "main.cpp" };
        write(dep, "export module dep;\nexport int dep_value() { return 1; }\n");
        const std::string first { "import third_party_missing;\nimport dep;\nint probe() {\n    return dep_va;\n}\n" };
        std::string second { first };
        second.replace(second.find("dep_va"), 6, "dep_val");
        write(source, first);
        write_database_for(root, { dep, source });
        Session session { .id = "third-party-import-reuse", .project = root, .flags = FLAGS, .timeout_seconds = 60 };
        session.sequence = json::array({
            initialize(root), initialized(), did_open(source, first), symbols_named(source, "probe"),
            expecting(completion_at(source, position_after(first, "dep_va")), { "dep_value" }),
            did_change(source, 2, second),
            expecting(completion_at(source, position_after(second, "dep_val")), { "dep_value" }),
            await_log("Built module dep to "),
        });
        const json result = replay(session);
        passed(result, root);
        // Every preamble build scans the import again and logs it once. A completion uses the prerequisites
        // there are, so it adds none: the failures follow the preambles.
        const std::string log { result.value("stderr", std::string {}) };
        expect(le(count_of(log, "third_party_missing"), count_of(log, "Built preamble of size")))
            << "the import that cannot be resolved was built again for a request";
    };

    // A file whose only import is the third party's keeps its preamble. An import in its body of a module that
    // can be built derives the prerequisites again and keeps the real names: a PCH without imports stays only
    // with the whole audit of its compiler and inputs, else the preamble is dropped. An import in a header
    // always drops it, for that prefix would serialize a named module.
    "a preamble is kept or dropped by what the file imports"_test = [] {
        const fs::path root { work() };
        const fs::path dep { root / "dep.cppm" }, source { root / "main2.cpp" }, fat { root / "fat.h" };
        write(dep, "export module dep;\nexport int dep_value() { return 1; }\n");
        std::string header { "#pragma once\n// deterministic declarations proving preamble content\n" };
        for (int i { 0 }; i < 20000; ++i) header += std::format("namespace fat {{ struct S{0} {{ int v{0}; int w{0}; }}; }}\n", i);
        write(fat, header);
        const std::string text { "#include \"fat.h\"\nimport third_party_missing;\nint probe2() {\n    return fat::S399;\n}\n" };
        std::string flipped { text };
        flipped.replace(flipped.find("import third_party_missing;"), 27, "import third_party_missing;\nimport dep;");
        flipped += "int use_dep() {\n    return dep_va;\n}\n";
        write(source, text);
        write_database_for(root, { dep, source });
        const fs::path trace { root / "preamble-trace.json" };
        Session session { .id = "third-party-import-preamble", .project = root, .flags = FLAGS, .timeout_seconds = 240,
                          .env = { { "CLANGD_TRACE", str(trace) } } };
        const auto fat_name = [&](const std::string& in) { return expecting(completion_at(source, position_after(in, "fat::S399")), { "S3999" }); };
        const auto dep_name = [&] { return expecting(completion_at(source, position_after(flipped, "dep_va")), { "dep_value" }); };
        session.sequence = json::array({
            initialize(root), initialized(), did_open(source, text), symbols_named(source, "probe2"),
            await_log("main2.cpp version 1"),
            fat_name(text),
            json { { "action", "replace-file" }, { "file", "main2.cpp" }, { "from", "import third_party_missing;" }, { "with", "import third_party_missing;\nimport dep;" } },
            did_change(source, 2, flipped),
            await_log("main2.cpp version 2"),
            // documentSymbol waits for the AST built again, so the completions see the prerequisites derived anew.
            symbols_named(source, "probe2"),
            fat_name(flipped), dep_name(),
            json { { "action", "replace-file" }, { "file", "fat.h" }, { "from", "#pragma once" }, { "with", "#pragma once\nimport dep;" } },
            did_change(source, 3, flipped + "\n// header import\n"),
            await_log("main2.cpp version 3"),
            symbols_named(source, "probe2"),
            fat_name(flipped), dep_name(),
        });
        const json result = replay(session);
        passed(result, root);
        const std::string log { result.value("stderr", std::string {}) };

        bool audited { false };
        if (json events = json::parse(contents(trace), nullptr, false); !events.is_discarded()) {
            if (events.is_object()) events = events.value("traceEvents", json::array());
            for (const auto& event : events) {
                if (!event.is_object() || event.value("name", std::string {}) != "BuildPreamble" || event.value("ph", std::string {}) != "X") continue;
                const json args = event.value("args", json::object());
                if (!args.is_object() || !args.value("File", std::string {}).ends_with("main2.cpp")) continue;
                audited = audited || std::ranges::all_of(std::array { "TextualModulePreamble", "PCHConstructed", "PCHImportsFree", "PCHInputsComplete", "PCHOpenFilesAudited" },
                                                         [&](const char* field) { return args.value(field, json(nullptr)) == json(true); });
            }
        }
        std::map<int, long long> largest;
        const std::regex built { R"(Built preamble of size (\d+) for file \S+main2\.cpp version (\d+))" };
        for (std::sregex_iterator at { log.begin(), log.end(), built }, end; at != end; ++at) {
            long long& size { largest[std::stoi((*at)[2].str())] };
            size = std::max(size, std::stoll((*at)[1].str()));
        }
        const long long first { largest.contains(1) ? largest[1] : 0 };
        const long long second { largest.contains(2) ? largest[2] : 1000000000 };
        // A preamble of no prefix can be used again after the header's edit: it holds nothing the edit changes. No
        // build logged means the last one stays.
        const long long third { largest.contains(3) ? largest[3] : second };
        expect(fatal(gt(first, 600000LL))) << "expected a real preamble over the fat header";
        expect(second < first / 2 || audited) << std::format("an import in the body kept a PCH without the whole audit: v1={} v2={}", first, second);
        expect(lt(third, first / 2)) << std::format("an import in a header must drop the preamble: v1={} v3={}", first, third);

        // Five completions, each with names from the parser itself and an item that is a function or a class.
        const std::regex complete { R"(Code complete: (\d+) results from Sema, (\d+) from Index, (\d+) matched, (\d+) from identifiers, (\d+) returned)" };
        int answered { 0 };
        bool fromSema { true };
        for (std::sregex_iterator at { log.begin(), log.end(), complete }, end; at != end; ++at) {
            ++answered;
            fromSema = fromSema && (*at)[1].str() != "0";
        }
        expect(eq(answered, 5)) << "completions the engine answered";
        expect(fromSema) << "a completion had no name from the parser";
        const json answers = result.value("responses", json::array());
        expect(eq(answers.size(), std::size_t { 5 }));
        for (const auto& answer : answers) {
            const json chosen = answer.value("completion_items", json::object());
            for (auto items = chosen.begin(); items != chosen.end(); ++items)
                expect(std::ranges::any_of(items.value(), [](const json& item) { return item.value("kind", 0) == 3 || item.value("kind", 0) == 7; }))
                    << items.key() << " is neither a function nor a class";
        }
    };

    // A provider that appears through a change of the compile commands reaches files whose prerequisites were
    // none before: what was decided dies with the generation of the commands. One process, so the change is
    // seen in the middle of a session.
    "a provider that appears in the compile commands reaches a file that had none"_test = [] {
        const fs::path root { work() };
        const fs::path dep { root / "dep.cppm" }, dep2 { root / "dep2.cppm" }, source { root / "main3.cpp" };
        write(dep, "export module dep;\nexport int dep_value() { return 1; }\n");
        write(dep2, "export module dep2;\nexport int dep2_value() { return 2; }\n");
        const std::string text { "import third_party_missing;\nimport dep2;\nint probe3() {\n    return dep2_va;\n}\n" };
        std::string later { text };
        later.replace(later.find("dep2_va"), 7, "dep2_val");
        write(source, text);
        const auto command = [&](const fs::path& file) { return compile_command(root, file, { "-std=c++20", "-c", str(file) }); };
        // dep2 has no command yet: its import stays text.
        write_database(root, json::array({ command(dep), command(source) }));
        Session session { .id = "third-party-import-provider-gain", .project = root, .flags = FLAGS, .timeout_seconds = 240 };
        session.sequence = json::array({
            initialize(root), initialized(), did_open(source, text), symbols_named(source, "probe3"),
            expecting(completion_at(source, position_after(text, "dep2_va")), { "dep2_value" }, "forbidden_symbols"),
            json { { "action", "replace-file" }, { "file", "compile_commands.json" }, { "from", command(source).dump() },
                   { "with", command(dep2).dump() + "," + command(source).dump() } },
            // The directory's commands are looked at again every five seconds: past that, the next request
            // loads them, says the commands changed, and builds the prerequisites with the new provider.
            json { { "action", "sleep" }, { "seconds", 6 } },
            did_change(source, 2, later), symbols_named(source, "probe3"),
            await_log("Built module dep2 to "),
            expecting(completion_at(source, position_after(later, "dep2_val")), { "dep2_value" }),
        });
        passed(replay(session), root);
    };
}); }};

}  // namespace
