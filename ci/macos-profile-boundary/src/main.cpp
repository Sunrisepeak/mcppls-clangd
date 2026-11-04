// Review the released macOS confinement profile capacity without changing it.
import std;
import mcpplibs.os;

namespace os = mcpplibs::os;
namespace fs = std::filesystem;

struct observation {
    bool returned, child_success, marker;
    int error, native_error;
};

std::vector<fs::path> directories(const fs::path& base, int levels, bool escaped) {
    std::vector<fs::path> paths;
    const std::string component = escaped ? std::string("a\\\"") : std::string("a");
    std::string segment;
    while (segment.size() < 72) segment += component;
    for (int n = 0; n < 16; ++n) {
        fs::path path = base / std::to_string(n);
        for (int depth = 0; depth < levels; ++depth) path /= segment;
        fs::create_directories(path);
        paths.push_back(fs::canonical(path));
    }
    return paths;
}

observation run(const char* label, const std::vector<fs::path>& paths, bool readonly,
                bool confine, const fs::path& marker) {
    fs::remove(marker);
    os::process::spawn_options options;
    options.program = "/usr/bin/touch";
    options.args = {os::fs::generic_utf8(marker)};
    options.confine = confine;
    std::vector<os::process::grant> grants;
    std::size_t longest = 0;
    for (std::size_t n = 0; n < paths.size(); ++n) {
        // Short logical names keep environment/conveyance size independent
        // of the physical F_GETPATH names used to build the sandbox profile.
        grants.push_back({"/slot/" + std::to_string(n), paths[n], readonly});
        longest = std::max(longest, os::fs::generic_utf8(paths[n]).size());
    }
    options.grants = grants;
    const auto result = os::process::run(options);
    observation value{result.has_value(), result && result->status.success(), fs::exists(marker),
                      result ? 0 : static_cast<int>(result.error().code),
                      result ? 0 : result.error().native};
    std::printf("{\"case\":\"%s\",\"confine\":%s,\"read_only\":%s,\"grants\":%zu,"
                "\"longest_physical_path_bytes\":%zu,\"returned\":%s,\"child_success\":%s,"
                "\"marker\":%s,\"error\":%d,\"native_error\":%d}\n",
                label, confine ? "true" : "false", readonly ? "true" : "false", paths.size(), longest,
                value.returned ? "true" : "false", value.child_success ? "true" : "false",
                value.marker ? "true" : "false", value.error, value.native_error);
    std::fflush(nullptr);
    fs::remove(marker);
    return value;
}

int main() {
#if !defined(__APPLE__)
    std::puts("This runtime observation requires macOS.");
    return 2;
#endif
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto base = fs::temp_directory_path() / ("mcpp-885-profile-" + std::to_string(unique));
    fs::create_directories(base);
    int failed = 0;
    auto check = [&](bool condition, const char* name) {
        if (!condition) { std::println("control failed: {}", name); ++failed; }
    };
    const auto short_paths = directories(base / "short", 0, false);
    const auto short_rw = run("short-rw-confined", short_paths, false, true, short_paths[0] / "marker");
    check(short_rw.returned && short_rw.child_success && short_rw.marker, "short confined writable grant works");
    const auto short_ro = run("short-ro-confined", short_paths, true, true, short_paths[0] / "marker");
    check(short_ro.returned && !short_ro.child_success && !short_ro.marker, "short read-only grant refuses write");
    const auto long_paths = directories(base / "long", 10, false);
    const auto unconfined = run("long-rw-unconfined", long_paths, false, false, base / "outside-marker");
    check(unconfined.returned && unconfined.child_success && unconfined.marker, "sixteen long physical grants are otherwise valid");
    const auto confined = run("long-rw-confined", long_paths, false, true, base / "outside-marker");
    check(!confined.returned && confined.error == static_cast<int>(os::errc::invalid) && !confined.marker,
          "oversize writable profile refuses startup before touch can run");
    const auto escaped = directories(base / "escaped", 10, true);
    const auto escaped_plain = run("escaped-ro-unconfined", escaped, true, false, base / "outside-marker");
    check(escaped_plain.returned && escaped_plain.child_success && escaped_plain.marker, "escaped physical names and rights are otherwise valid");
    const auto escaped_confined = run("escaped-ro-confined", escaped, true, true, base / "outside-marker");
    check(!escaped_confined.returned && escaped_confined.error == static_cast<int>(os::errc::invalid) && !escaped_confined.marker,
          "escaping can exhaust the read-only profile and refuses before execution");
    fs::remove_all(base);
    std::printf("{\"controls\":6,\"failures\":%d}\n", failed);
    return failed ? 1 : 0;
}
