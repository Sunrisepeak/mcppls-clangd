// Observe filesystem cleanup with the host runtime and two published groups.
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;

void make(const fs::path& root, int levels, bool quoted) {
    std::string segment;
    while (segment.size() < 72) segment += quoted ? "a\"" : "a";
    for (int n = 0; n < 16; ++n) {
        fs::path path = root / std::to_string(n);
        for (int depth = 0; depth < levels; ++depth) path /= segment;
        fs::create_directories(path);
    }
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const fs::path root(argv[1]);
    if (root.filename().string().find("mcpp-885-cleanup") != 0) return 2;
    struct entry { const char* name; int depth; bool quoted; };
    const entry entries[] = {{"short", 0, false}, {"deep", 10, false}, {"quoted", 10, true}};
    for (const auto& item : entries) {
        const auto path = root / item.name;
        make(path, item.depth, item.quoted);
        std::error_code error;
        const auto removed = fs::remove_all(path, error);
        const bool remains = fs::exists(path);
        std::printf("{\"case\":\"%s\",\"depth\":%d,\"quoted\":%s,\"removed\":%llu,"
                    "\"cleanup_error\":%d,\"remains\":%s}\n", item.name, item.depth,
                    item.quoted ? "true" : "false", static_cast<unsigned long long>(removed),
                    error.value(), remains ? "true" : "false");
    }
    std::puts("review_complete=1");
    return 0; // Observation completion, not an assertion that cleanup succeeded.
}
