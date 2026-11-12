// A header of the global module fragment is analysed whatever identity its path has.
//
// A module unit that imports a module has no textual preamble: the headers of its global module
// fragment are entered with the unit itself. The include analysis then asks for the entry of each
// include's resolved path, and identifies the header by that entry's identity. Where the resolved
// path is another spelling than the one the header was entered by, a file system may answer with
// another identity (Windows 11 24H2 under okrun did: an open file and its name were two nodes),
// the include structure has no ID for the entry, and the engine dereferenced the empty result: it
// ended on the first build of the unit, by an illegal instruction where the standard library
// checks, silently elsewhere (mcpp-language-server issue 86).
//
// The unit here includes a header through a search path that is not its resolved path, imports a
// module and uses the header's type. The engine must build it, answer for it, and not offer the
// header in use for removal.
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

CTS gmf_include_analysis{"gmf-include-analysis", [] { against_subject([] {
    // What the subject's session logged, for the parts below that ask about the system.
    std::string log;
    const std::string_view TWO_IDENTITIES { "an open file is not the node its name refers to" };
    // The session, by the subject or by `engine`.
    const auto session_by = [](const fs::path& engine) {
        const fs::path root { work(engine.empty() ? "subject" : "control") };
        fs::create_directories(root / "other");
        write(root / "inc" / "widget.h", "#ifndef WIDGET_H\n#define WIDGET_H\nstruct Widget { int size; };\n#define WIDGET_UNIT 1\n#endif\n");
        const fs::path dep { root / "dep.cppm" }, unit { root / "view.cppm" };
        write(dep, "export module dep;\nexport int dep_value() { return 1; }\n");
        const std::string text { "module;\n"
                                 "#include \"widget.h\"\n"
                                 "export module view;\n"
                                 "import dep;\n"
                                 "export int measure(const Widget &w) { return w.size * WIDGET_UNIT + dep_value(); }\n" };
        write(unit, text);
        // The search path is spelled through a sibling directory, so the header is entered by one path and
        // resolved to another.
        const std::string include { "-I" + str(root) + "/other/../inc" };
        json commands = json::array();
        for (const auto& file : { dep, unit }) commands.push_back(compile_command(root, file, { "-std=c++20", include, "-c", str(file) }));
        write_database(root, commands);

        json hover = document(unit);
        hover["position"] = position(4, 12);
        Session session { .id = engine.empty() ? "gmf-include-analysis" : "gmf-include-analysis-control", .project = root,
                          .flags = { "--experimental-modules-support", "--background-index=false", "-j=2", "--log=verbose" }, .timeout_seconds = 120,
                          .engine = engine };
        session.sequence = json::array({
            initialize(root),
            initialized(),
            did_open(unit, text),
            json { { "method", "textDocument/documentSymbol" }, { "params", document(unit) }, { "expect", json { { "/result/0/name", "measure" } } } },
            // The unit's diagnostics, the include analysis among them, are published when its build ends; the
            // engine answers after it.
            await_log("textDocument/publishDiagnostics"),
            json { { "method", "textDocument/hover" }, { "params", hover }, { "expect", json { { "/result/contents/kind", "plaintext" } } } },
        });
        return std::pair { replay(session), root };
    };
    "the unit is built and answered for"_test = [&] {
        const auto [result, root] = session_by({});
        log = result.value("stderr", std::string {});
        std::println("two identities for a file on this system: {}", log.contains(TWO_IDENTITIES));
        passed(result, root);
        expect(contains(log, std::string { "Built module dep to " })) << "the unit did not take the module path: dep was not built";
        expect(!(log.contains("widget.h") && log.contains("is not used directly"))) << "the header in use was offered for removal";
    };
    // The engine measures its cache directory at the first module it builds and says when the system gives an
    // open file another identity than its name: the condition under which this case met the defect. Asked only
    // of a subject said to be on such a system (Windows build 26100 and later under a runner through 0.21.0).
    "the system gave a file two identities"_test[cts::needs { "two-identities" }] = [&] {
        expect(contains(log, std::string { TWO_IDENTITIES })) << "this system gave a file one identity: the case did not meet the condition";
    };
    // What the part above proves, it proves only where an engine without the fix fails: the control ends on the
    // session while this system gives two identities, or the pass above shows nothing. Where the system gives
    // one (a platform that no longer has the condition) neither engine can meet the defect, and the control
    // passes too.
    "an engine without the fix ends on the unit where a file has two identities"_test[cts::needs { "control" }] = [&] {
        expect(fatal(!log.empty())) << "the subject's session did not run";
        const auto [result, root] = session_by(subject().control);
        write(root / "replay-gmf-include-analysis-control.json", result.dump(2) + "\n");
        const std::string outcome { result.value("outcome", std::string {}) };
        std::println("the control: {} {}", outcome, result.value("detail", std::string {}));
        if (log.contains(TWO_IDENTITIES)) expect(eq(outcome, std::string { "crash" })) << "the control did not end on the case: the gate does not show the defect";
        else expect(eq(outcome, std::string { "pass" })) << "one identity for a file, and the control still failed: " << result.value("detail", std::string {});
    };
}); }};

}  // namespace
