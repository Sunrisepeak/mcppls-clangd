// How the cases drive the engine (tests/cts/README.md). A case writes a project into a directory of
// its own, states a session as a sequence of steps -- requests with what their answers must hold,
// notifications, edits of the project's files, waits for a line of the engine's log -- and
// `replay` runs it against the subject: the engine starts, the steps are sent, the engine is shut
// down, and the result says how it ended with every answer and the engine's log.
//
// The subject is what the environment names:
//   MCPPLS_ENGINE           the engine: clangd, clangd.exe, or clangd.okb (the ok image)
//   MCPPLS_ENGINE_RUNNER    the program that starts an image (okrun); unset for a native engine
//   MCPPLS_ENGINE_CLANG     a compiler the compile commands name
//   MCPPLS_ENGINE_PLATFORM  linux-x64, linux-arm64, darwin-arm64, win32-x64 (default: this host's)
//   MCPPLS_ENGINE_HAS       what else the subject can do, comma-separated:
//                             matching-clang   --clang is the engine's own build: a BMI it writes is read
//                             two-identities   the system gives an open file another identity than its name
//   MCPPLS_ENGINE_TIDY, MCPPLS_ENGINE_C_INDEX_TEST, MCPPLS_ENGINE_CLANG_REPL
//                           the other tools of the engine's build tree, where there is one: the
//                           subject then has `clang-tidy`, and `frontend-tools` with the last two
//   MCPPLS_ENGINE_CONTROL   an engine without a fix a case proves by it, started as the subject is:
//                           the subject then has `control`
//   MCPPLS_ENGINE_KEEP      a directory each case's project and results are kept in
//   MCPPLS_ENGINE_SAMPLE    1: a session that reaches its deadline on macOS is sampled before it is ended
// What the subject has without being told: its system (`linux`, `darwin`, `win32`), and `native` or
// `image`. A case that needs what the subject lacks is not run (`unsupported: <capability>`).
export module engine.harness;

import std;
import nlohmann.json;
import mcpplibs.os;
export import mcpplibs.mtest;
export import mcpplibs.mtest.cts;
import mcpplibs.mtest.e2e;

export namespace engine {

using json = nlohmann::json;
namespace fs = std::filesystem;

struct Subject {
    fs::path engine;
    fs::path runner;   // empty: the engine starts by itself
    fs::path clang;
    fs::path tidy, cIndexTest, repl;   // the build tree's other tools; empty where there is none
    fs::path control;                  // an engine without a fix, started as the subject is; empty where there is none
    std::string platform;
    std::set<std::string, std::less<>> capabilities;
    std::string problem;   // why no session can start; empty when one can
    bool has(std::string_view capability) const { return capabilities.contains(capability); }
    bool image() const { return !runner.empty(); }
};

// The subject, read from the environment once.
const Subject& subject();

// The parts `declare` declares, run against the subject: the parts of a case named `image` or
// `native` after what the subject is. A part that needs what the subject lacks
// (`"..."_test[cts::needs{"linux"}]`) is not run there, and says so: `unsupported: linux`.
//
// A regression is an object of a file of this directory, a case of its own that mtest lists, selects and
// schedules, whose body is this:
//
//   CTS cold{"module-cold-completion", [] { against_subject([] {
//       "the first answer carries the module's names"_test = [] { ... };
//   }); }};
void against_subject(std::function<void()> declare, std::source_location where = std::source_location::current());

// A path as the engine and a compile command read it: UTF-8, with `/`.
std::string str(const fs::path& path);
// The file URI of a path, as a client writes it.
std::string uri(const fs::path& path);
void write(const fs::path& file, std::string_view contents);
std::string read(const fs::path& file);
// The same, and nothing for a file that cannot be read.
std::string contents(const fs::path& file);

// A directory of the case's own, empty: under MCPPLS_ENGINE_KEEP when that is set, else temporary.
fs::path work(std::string_view name = {});

// One compile command: `clang` (the subject's when empty), then `arguments`, in `directory`.
json compile_command(const fs::path& directory, const fs::path& file, std::vector<std::string> arguments);
// `-std=c++20 -c <file>` for each of `files`, written as the project's compile_commands.json.
void write_database_for(const fs::path& directory, std::initializer_list<fs::path> files, std::string_view standard = "-std=c++20");
void write_database(const fs::path& directory, const json& commands);

// The steps every session begins with, and the shapes most steps have.
json initialize(const fs::path& root);
json initialized();
json did_open(const fs::path& file, std::string_view contents, int version = 1);
json did_change(const fs::path& file, int version, std::string_view contents);
json document(const fs::path& file);
json position(int line, int character);
// The position just after `needle` in `text`: its first occurrence, or (`last`) its last. Text of one byte a character.
json position_after(std::string_view text, std::string_view needle, bool last = false);
// A completion asked for at `at` of `file`: a step to add what is expected to.
json completion_at(const fs::path& file, json at);
// A step that waits until the engine's log has `part`.
json await_log(std::string_view part);

// The value a JSON pointer names in `value`, or nothing.
const json* pointer(const json& value, std::string_view path);

struct Session {
    std::string id;
    fs::path project;
    std::vector<std::string> flags;
    json sequence = json::array();
    double timeout_seconds = 30;
    fs::path engine;   // empty: the subject's
    std::vector<std::pair<std::string, std::string>> env;   // set for the engine, beside this program's own
    // Called once the engine runs, with the identifier the system gives its process (the runner's, for an image).
    std::function<void(std::uint64_t)> started;
};

// Runs the session. The result: `outcome` (pass, crash, timeout, error), `detail`, `exit_code`,
// `responses` (the names each completion answered with), `raw_responses` (every answer, with how
// long it took), `stderr` (the engine's log) and `readers_stopped`.
//
// A step is a request (`method`, `params`, and what its answer must hold: `expect`, JSON pointers
// to exact values; `expected_symbols`, `forbidden_symbols`, `expected_snippet_fragments` for a
// completion, asked again for `retry_seconds` and while the answer is marked incomplete), a
// notification (`notify`), a request answered later (`defer` names it, the action `await` takes
// its answer), or an action: `sleep` (`seconds`), `await-log` (`contains`), `write-file` (`file`,
// `contents`), `replace-file` (`file`, `from`, `with`, and `preserve-mtime` or `same-second`).
// Files a step changed are as they were when the session ends. `${PROJECT_URI}`, `${PROJECT_PATH}`,
// `${FILE_TEXT:<file>}` and `${REQUEST:<name>}` are written out in every string.
json replay(const Session& session);

// An engine a case talks to step by step, where a session of fixed steps does not do: several engines
// over one cache, an engine that is killed. Whatever goes wrong fails the case; an engine still
// running when its client goes is ended.
class Client {
public:
    Client(const fs::path& root, std::vector<std::string> flags);
    ~Client();
    Client(const Client&) = delete;
    Client& operator=(const Client&) = delete;

    // A request's result, within `seconds`.
    json request(const std::string& method, json params = nullptr, double seconds = 15);
    void notify(const std::string& method, json params = nullptr);
    // initialize, initialized, and `file` opened with the text it has on disk.
    void open_project(const fs::path& file);
    // The first notification of `method` that `wanted` accepts, one already received or one that comes within `seconds`.
    json notification(std::string_view method, const std::function<bool(const json&)>& wanted, double seconds = 20);
    std::string log();
    bool log_contains(std::string_view part);
    // The identifier the system gives the process (the runner's, for an image).
    std::uint64_t pid() const;
    // Shut down and left with status 0, or (`kill`) ended outright, with everything it started.
    void stop(bool kill = false);
    bool stopped() const { return stopped_; }
    // Every answer it gave, and how it ended, for a report.
    json record();

private:
    struct State;
    std::unique_ptr<State> state_;
    fs::path root_;
    std::int64_t requestId_ { 0 };
    json answers_ = json::array();
    std::deque<json> notifications_;
    bool stopped_ { false };
};

// The command that starts the subject's engine with `flags`: through its runner, for an image.
std::vector<std::string> engine_command(std::vector<std::string> flags);

// The engine in its test mode (`-lit-test`): the messages are given at once, each after a line of `---`, and it
// answers and ends. `replies` are the frames it wrote, `status` what it left with.
struct LitTest {
    int status = -1;
    bool timed_out = false;
    json replies = json::array();
    std::string log;
    std::string problem;   // what was wrong with its output; empty when it was frames
};
LitTest lit_test(const json& messages, std::vector<std::string> flags = {}, double seconds = 20);

// A program run to its end: a compiler, a tool of the build tree.
struct Ran {
    int status = -1;
    bool started = false, timed_out = false;
    std::string out, err;
    bool ok() const { return started && !timed_out && status == 0; }
};
Ran tool(std::vector<std::string> argv, const fs::path& directory = {}, std::string input = {}, double seconds = 45);

// The name this machine has, as its own `hostname` says it; `localhost` where that cannot be asked.
std::string host_name();
// The identifier the system gives this program.
std::uint64_t own_pid();

// A file's time of last access is made one of long ago, its time of last change kept.
void age_access_time(const fs::path& file);

// The session passed and the engine left with status 0; otherwise the case fails with the detail
// and the end of the engine's log. The result is kept beside the project.
void passed(const json& result, const fs::path& directory);

// The answer of the first request of `method` in the result, or nothing.
const json* answer(const json& result, std::string_view method);
double elapsed_ms(const json& result, std::string_view method);

// The lines of the engine's log.
std::vector<std::string> log_lines(const json& result);
// How often `part` is in the engine's log.
std::size_t log_count(const json& result, std::string_view part);
// The files under `directory`, however deep, that `wanted` holds for.
std::vector<fs::path> files_under(const fs::path& directory, const std::function<bool(const fs::directory_entry&)>& wanted);

}  // namespace engine

namespace engine {

namespace os = mcpplibs::os;
namespace mt = mcpplibs::mtest;
using Clock = std::chrono::steady_clock;

namespace {

std::string env(const char* name) {
    auto value = os::env::get(name);
    return value ? *value : std::string {};
}

// A name the environment gives, read by the host's rules: the standard library's own reading in a
// program over openkal is POSIX's, which takes a Windows name for one component.
fs::path host_path(std::string_view name) {
    if (name.empty()) return {};
    return os::fs::from_utf8(os::fs::generic(os::fs::from_utf8(name)));
}

std::string host_platform() {
    const bool arm { os::ARCH == os::architecture::aarch64 };
    switch (os::host()) {
    case os::platform::windows: return "win32-x64";
    case os::platform::macos: return arm ? "darwin-arm64" : "darwin-x64";
    default: return arm ? "linux-arm64" : "linux-x64";
    }
}

fs::path existing(fs::path path) {
    if (path.empty() || fs::is_regular_file(path)) return path;
    fs::path exe { path };
    exe += ".exe";
    return fs::is_regular_file(exe) ? exe : path;
}

Subject read_subject() {
    Subject s;
    s.engine = existing(host_path(env("MCPPLS_ENGINE")));
    s.runner = existing(host_path(env("MCPPLS_ENGINE_RUNNER")));
    s.clang = existing(host_path(env("MCPPLS_ENGINE_CLANG")));
    s.platform = env("MCPPLS_ENGINE_PLATFORM");
    if (s.platform.empty()) s.platform = host_platform();
    s.capabilities.insert(s.platform.substr(0, s.platform.find('-')));
    s.capabilities.insert(s.runner.empty() ? "native" : "image");
    s.tidy = existing(host_path(env("MCPPLS_ENGINE_TIDY")));
    s.cIndexTest = existing(host_path(env("MCPPLS_ENGINE_C_INDEX_TEST")));
    s.repl = existing(host_path(env("MCPPLS_ENGINE_CLANG_REPL")));
    s.control = existing(host_path(env("MCPPLS_ENGINE_CONTROL")));
    if (!s.control.empty()) s.capabilities.insert("control");
    if (!s.tidy.empty()) s.capabilities.insert("clang-tidy");
    if (!s.cIndexTest.empty() && !s.repl.empty()) s.capabilities.insert("frontend-tools");
    const std::string more { env("MCPPLS_ENGINE_HAS") };
    for (const auto part : std::views::split(more, ',')) {
        std::string_view word { part.begin(), part.end() };
        while (!word.empty() && word.front() == ' ') word.remove_prefix(1);
        while (!word.empty() && word.back() == ' ') word.remove_suffix(1);
        if (!word.empty()) s.capabilities.emplace(word);
    }
    if (s.engine.empty()) s.problem = "MCPPLS_ENGINE names no engine";
    else if (!fs::is_regular_file(s.engine)) s.problem = std::format("MCPPLS_ENGINE: no file {}", str(s.engine));
    else if (!s.runner.empty() && !fs::is_regular_file(s.runner)) s.problem = std::format("MCPPLS_ENGINE_RUNNER: no file {}", str(s.runner));
    else if (s.clang.empty()) s.problem = "MCPPLS_ENGINE_CLANG names no compiler";
    return s;
}

// What ended a session before its steps were done.
struct Timeout {};
struct Closed { std::string what; };
struct Failure { std::string what; };

[[noreturn]] void failure(std::string what) { throw Failure { std::move(what) }; }

// The engine as a process: its frames, its log, and its end.
class Engine {
public:
    struct Shared {
        std::mutex mutex;
        std::condition_variable ready;
        std::deque<json> messages;
        std::optional<Closed> closed;        // the output ended, or a frame could not be read
        bool closedIsEnd { false };          // ... by ending
        std::string log;
        bool outputDone { false }, errorDone { false };
    };

    Engine(const std::vector<std::string>& flags, const fs::path& directory, const fs::path& engine,
           const std::vector<std::pair<std::string, std::string>>& environment = {}) {
        const Subject& s { subject() };
        os::process::spawn_options options;
        options.program = s.runner.empty() ? engine : s.runner;
        if (!s.runner.empty()) options.args.push_back(str(engine));
        for (const auto& flag : flags) options.args.push_back(flag);
        options.cwd = directory;
        for (const auto& [name, value] : environment) options.env.emplace_back(name, value);
        options.in = os::process::stdio::pipe;
        options.out = os::process::stdio::pipe;
        options.err = os::process::stdio::pipe;
        options.own_unit = true;   // the engine and everything it starts: its workers, a runner's image
        auto started = os::process::process::spawn(options);
        if (!started) failure(std::format("the engine did not start: {}", started.error().message()));
        process_ = std::make_shared<os::process::process>(std::move(*started));
        shared_ = std::make_shared<Shared>();
        std::thread { [process = process_, shared = shared_] { read_frames(*process, *shared); } }.detach();
        std::thread { [process = process_, shared = shared_] { read_log(*process, *shared); } }.detach();
    }

    void write(const json& message) {
        const std::string body { message.dump() };
        (void)process_->write(std::format("Content-Length: {}\r\n\r\n{}", body.size(), body));
    }

    // The next message, by `deadline`.
    json next(Clock::time_point deadline) {
        std::unique_lock lock { shared_->mutex };
        if (!shared_->ready.wait_until(lock, deadline, [&] { return !shared_->messages.empty() || shared_->closed; })) throw Timeout {};
        if (!shared_->messages.empty()) {
            json message = std::move(shared_->messages.front());
            shared_->messages.pop_front();
            return message;
        }
        if (shared_->closedIsEnd) throw *shared_->closed;
        failure(shared_->closed->what);
    }

    bool log_contains(std::string_view part) {
        const std::lock_guard lock { shared_->mutex };
        return shared_->log.find(part) != std::string::npos;
    }

    std::string log() {
        const std::lock_guard lock { shared_->mutex };
        return shared_->log;
    }

    // Its status once it has ended: what it returned, or the negated number of what ended it.
    std::optional<int> poll() {
        if (status_) return status_;
        auto waited = process_->try_wait();
        if (waited && waited->has_value()) status_ = code_of(**waited);
        return status_;
    }

    std::optional<int> wait_until(Clock::time_point deadline) {
        if (status_) return status_;
        const auto left = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now());
        auto waited = process_->wait_for(std::max(left, std::chrono::milliseconds { 1 }));
        if (waited && waited->has_value()) status_ = code_of(**waited);
        return status_;
    }

    void close_input() { process_->close_input(); }
    std::uint64_t id() const { return process_->id(); }

    // The engine and what it started are ended; true when both of its streams then ended too.
    bool end() {
        if (!poll()) process_->kill();
        else process_->end_unit();   // a leader that crashed can leave helpers holding its pipes
        (void)wait_until(Clock::now() + std::chrono::seconds { 15 });
        std::unique_lock lock { shared_->mutex };
        return shared_->ready.wait_for(lock, std::chrono::seconds { 2 }, [&] { return shared_->outputDone && shared_->errorDone; });
    }

private:
    static int code_of(const os::process::exit_status& status) { return status.by_environment ? -(status.code & 0x7f) : status.code; }

    static void read_frames(os::process::process& process, Shared& shared) {
        std::string buffer;
        std::optional<Closed> closed;
        bool end { false };
        while (!closed) {
            // Whole frames first: the headers to an empty line, then the body the length states.
            while (true) {
                const auto head = buffer.find("\r\n\r\n");
                if (head == std::string::npos) break;
                std::size_t length { 0 };
                bool stated { false };
                for (const auto line : std::views::split(std::string_view { buffer }.substr(0, head), std::string_view { "\r\n" })) {
                    const std::string_view header { line.begin(), line.end() };
                    const auto colon = header.find(':');
                    if (colon == std::string_view::npos) continue;
                    std::string name { header.substr(0, colon) };
                    std::ranges::transform(name, name.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
                    if (name != "content-length") continue;
                    std::string_view value { header.substr(colon + 1) };
                    while (!value.empty() && value.front() == ' ') value.remove_prefix(1);
                    stated = std::from_chars(value.data(), value.data() + value.size(), length).ec == std::errc {};
                }
                if (!stated || length == 0 || length > 16777216) {
                    closed = Closed { "invalid frame length" };
                    break;
                }
                if (buffer.size() < head + 4 + length) break;
                json message = json::parse(std::string_view { buffer }.substr(head + 4, length), nullptr, false);
                buffer.erase(0, head + 4 + length);
                if (message.is_discarded()) {
                    closed = Closed { "a frame is not JSON" };
                    break;
                }
                const std::lock_guard lock { shared.mutex };
                shared.messages.push_back(std::move(message));
                shared.ready.notify_all();
            }
            if (closed) break;
            auto chunk = process.read_output();
            if (!chunk || chunk->empty()) {
                closed = Closed { "server stdout closed" };
                end = true;
                break;
            }
            buffer += *chunk;
        }
        const std::lock_guard lock { shared.mutex };
        shared.closed = std::move(closed);
        shared.closedIsEnd = end;
        shared.outputDone = true;
        shared.ready.notify_all();
    }

    static void read_log(os::process::process& process, Shared& shared) {
        while (true) {
            auto chunk = process.read_error();
            if (!chunk || chunk->empty()) break;
            const std::lock_guard lock { shared.mutex };
            // A megabyte is kept: what a step waits for is in a session's first lines, and a verbose engine writes many.
            if (shared.log.size() < 1048576) shared.log.append(chunk->substr(0, 1048576 - shared.log.size()));
        }
        const std::lock_guard lock { shared.mutex };
        shared.errorDone = true;
        shared.ready.notify_all();
    }

    std::shared_ptr<os::process::process> process_;
    std::shared_ptr<Shared> shared_;
    std::optional<int> status_;
};

std::string replace_all(std::string value, std::string_view from, std::string_view to) {
    for (std::size_t at { value.find(from) }; at != std::string::npos; at = value.find(from, at + to.size())) value.replace(at, from.size(), to);
    return value;
}

// The name a completion item is found by: its filter text, or its label, up to `(` or `<`.
std::string symbol_of(const json& item) {
    std::string name { item.is_object() ? item.value("filterText", item.value("label", std::string {})) : std::string {} };
    name = name.substr(0, name.find_first_of("(<"));
    while (!name.empty() && std::isspace(static_cast<unsigned char>(name.front()))) name.erase(0, 1);
    while (!name.empty() && std::isspace(static_cast<unsigned char>(name.back()))) name.pop_back();
    return name;
}

std::vector<std::string> strings_of(const json& step, const char* key) {
    std::vector<std::string> out;
    if (const auto found = step.find(key); found != step.end() && found->is_array())
        for (const auto& item : *found) out.push_back(item.get<std::string>());
    return out;
}

// On macOS, a session at its deadline is sampled while it still runs: a diagnosis, never a verdict.
json sample_at_deadline(Engine& engine, const fs::path& directory) {
    json info { { "pid", engine.id() }, { "alive_before_sample", !engine.poll().has_value() }, { "duration_seconds", 1 } };
    if (os::host() != os::platform::macos || engine.poll()) {
        info["skipped"] = "requires a still-alive Darwin process";
        return info;
    }
    mt::e2e::command command;
    command.argv = { "/usr/bin/sample", std::to_string(engine.id()), "1", "10", "-file", "/dev/stdout" };
    command.timeout = std::chrono::seconds { 5 };
    const auto sampled = mt::e2e::run(std::move(command));
    info["sample_exit_code"] = sampled.status;
    info["sample_timed_out"] = sampled.timed_out;
    const fs::path output { directory / "timeout-sample.txt" };
    write(output, std::string_view { sampled.out }.substr(0, 262144));
    info["truncated"] = sampled.out.size() > 262144;
    info["output"] = str(output);
    info["alive_after_sample"] = !engine.poll().has_value();
    return info;
}

}  // namespace

const Subject& subject() {
    static const Subject s { read_subject() };
    return s;
}

void against_subject(std::function<void()> declare, std::source_location where) {
    mt::cts::against({ .name = subject().image() ? "image" : "native", .has = [](std::string_view capability) { return subject().has(capability); } },
                     std::move(declare), where);
}

std::string str(const fs::path& path) { return os::fs::generic_utf8(path); }

std::string uri(const fs::path& path) {
    const std::string name { str(path) };
    std::string out { "file://" };
    // A Windows name begins with its drive, which a URI writes after a third slash.
    if (name.size() >= 2 && name[1] == ':' && std::isalpha(static_cast<unsigned char>(name[0]))) out += '/';
    for (std::size_t at { 0 }; at < name.size(); ++at) {
        const unsigned char c { static_cast<unsigned char>(name[at]) };
        if (std::isalnum(c) || c == '/' || c == '_' || c == '.' || c == '-' || c == '~' || (c == ':' && at == 1)) out += static_cast<char>(c);
        else out += std::format("%{:02X}", c);
    }
    return out;
}

void write(const fs::path& file, std::string_view contents) {
    if (file.has_parent_path()) fs::create_directories(file.parent_path());
    if (auto written = os::fs::write(file, contents); !written) mt::fail(std::format("cannot write {}: {}", str(file), written.error().message()));
}

std::string read(const fs::path& file) {
    auto contents = os::fs::read(file);
    if (!contents) mt::fail(std::format("cannot read {}: {}", str(file), contents.error().message()));
    return std::move(*contents);
}

std::string contents(const fs::path& file) {
    auto read = os::fs::read(file);
    return read ? std::move(*read) : std::string {};
}

fs::path work(std::string_view name) {
    fs::path directory;
    if (const std::string keep { env("MCPPLS_ENGINE_KEEP") }; !keep.empty()) {
        std::string id { mt::current_case() };
        for (char& c : id)
            if (!(std::isalnum(static_cast<unsigned char>(c)) || c == '-' || c == '_' || c == '.')) c = '_';
        directory = host_path(keep) / id;
        std::error_code ignored;
        fs::remove_all(directory, ignored);
    } else {
        directory = mt::temp_dir();
    }
    if (!name.empty()) directory /= name;
    fs::create_directories(directory);
    // The name the system resolves it to: the engine names files so, and a temporary directory is a link on macOS.
    std::error_code failed;
    if (const auto resolved = fs::canonical(directory, failed); !failed) directory = resolved;
    return directory;
}

json compile_command(const fs::path& directory, const fs::path& file, std::vector<std::string> arguments) {
    json words = json::array({ str(subject().clang) });
    for (auto& argument : arguments) words.push_back(std::move(argument));
    return json { { "directory", str(directory) }, { "file", str(file) }, { "arguments", std::move(words) } };
}

void write_database(const fs::path& directory, const json& commands) { write(directory / "compile_commands.json", commands.dump()); }

void write_database_for(const fs::path& directory, std::initializer_list<fs::path> files, std::string_view standard) {
    json commands = json::array();
    for (const auto& file : files) commands.push_back(compile_command(directory, file, { std::string { standard }, "-c", str(file) }));
    write_database(directory, commands);
}

json initialize(const fs::path& root) {
    return json { { "method", "initialize" }, { "params", json { { "rootUri", uri(root) }, { "capabilities", json::object() } } } };
}

json initialized() { return json { { "method", "initialized" }, { "notify", true }, { "params", json::object() } }; }

json did_open(const fs::path& file, std::string_view contents, int version) {
    return json { { "method", "textDocument/didOpen" }, { "notify", true },
                  { "params", json { { "textDocument", json { { "uri", uri(file) }, { "languageId", "cpp" }, { "version", version }, { "text", std::string { contents } } } } } } };
}

json did_change(const fs::path& file, int version, std::string_view contents) {
    return json { { "method", "textDocument/didChange" }, { "notify", true },
                  { "params", json { { "textDocument", json { { "uri", uri(file) }, { "version", version } } },
                                     { "contentChanges", json::array({ json { { "text", std::string { contents } } } }) } } } };
}

json document(const fs::path& file) { return json { { "textDocument", json { { "uri", uri(file) } } } }; }

json position(int line, int character) { return json { { "line", line }, { "character", character } }; }

json position_after(std::string_view text, std::string_view needle, bool last) {
    const auto found = last ? text.rfind(needle) : text.find(needle);
    if (found == std::string_view::npos) mt::fail(std::format("the text has no {}", needle));
    const std::string_view before { text.substr(0, found + needle.size()) };
    const auto newline = before.rfind('\n');
    return position(static_cast<int>(std::ranges::count(before, '\n')), static_cast<int>(before.size() - (newline == std::string_view::npos ? 0 : newline + 1)));
}

json completion_at(const fs::path& file, json at) {
    json params = document(file);
    params["position"] = std::move(at);
    params["context"] = json { { "triggerKind", 1 } };
    return json { { "method", "textDocument/completion" }, { "params", std::move(params) } };
}

json await_log(std::string_view part) { return json { { "action", "await-log" }, { "contains", std::string { part } } }; }

const json* pointer(const json& value, std::string_view path) {
    if (path.empty() || path.front() != '/') return nullptr;
    const json* at { &value };
    for (const auto part : std::views::split(path.substr(1), '/')) {
        std::string key { part.begin(), part.end() };
        key = replace_all(replace_all(std::move(key), "~1", "/"), "~0", "~");
        if (at->is_array()) {
            std::size_t index { 0 };
            if (key.empty() || std::from_chars(key.data(), key.data() + key.size(), index).ptr != key.data() + key.size() || index >= at->size()) return nullptr;
            at = &(*at)[index];
        } else if (at->is_object()) {
            const auto found = at->find(key);
            if (found == at->end()) return nullptr;
            at = &*found;
        } else {
            return nullptr;
        }
    }
    return at;
}

json replay(const Session& session) {
    const Subject& s { subject() };
    if (!s.problem.empty()) mt::fail(s.problem);
    const fs::path engineFile { session.engine.empty() ? s.engine : session.engine };
    const fs::path project { session.project };
    json result { { "id", session.id }, { "outcome", "error" }, { "responses", json::array() }, { "raw_responses", json::array() } };
    if (!session.sequence.is_array() || session.sequence.empty() || session.sequence[0].value("method", std::string {}) != "initialize")
        mt::fail("a session begins with initialize");
    if (!(session.timeout_seconds > 0 && session.timeout_seconds <= 600)) mt::fail("a session's deadline is within ten minutes");

    struct Original {
        std::optional<std::string> contents;
        fs::file_time_type modified;
    };
    std::map<fs::path, Original> originals;
    struct Deferred {
        std::int64_t id;
        std::string method;
        std::int64_t startedNs;
    };
    std::map<std::string, Deferred> aliases;
    std::map<std::int64_t, json> pending;
    std::map<std::size_t, Clock::time_point> retryUntil;
    std::int64_t requestId { 0 };

    const auto began = Clock::now();
    const auto deadline = began + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double> { session.timeout_seconds });
    const auto now_ns = [&] { return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - began).count(); };

    std::optional<Engine> engine;
    try {
        engine.emplace(session.flags, session.project, engineFile, session.env);
    } catch (const Failure& failed) {
        result["detail"] = failed.what;
        result["exit_code"] = nullptr;
        result["stderr"] = "";
        result["readers_stopped"] = true;
        return result;
    }

    if (session.started) session.started(engine->id());

    const auto within_project = [&](const fs::path& file) { return os::fs::within(file, project) || os::fs::same(file, project); };

    const std::function<json(const json&)> expand = [&](const json& value) -> json {
        if (value.is_string()) {
            const std::string word { value.get<std::string>() };
            if (word.starts_with("${REQUEST:") && word.ends_with("}")) {
                const auto found = aliases.find(word.substr(10, word.size() - 11));
                if (found == aliases.end()) failure("a step names a request that is not waiting");
                return found->second.id;
            }
            if (word.starts_with("${FILE_TEXT:") && word.ends_with("}")) {
                const fs::path source { fs::weakly_canonical(project / word.substr(12, word.size() - 13)) };
                if (!within_project(source)) failure("fixture text escapes project");
                auto contents = os::fs::read(source);
                if (!contents) failure(std::format("cannot read {}", str(source)));
                if (contents->starts_with("\xEF\xBB\xBF")) contents->erase(0, 3);
                return *contents;
            }
            return replace_all(replace_all(word, "${PROJECT_URI}", uri(project)), "${PROJECT_PATH}", str(project));
        }
        if (value.is_array()) {
            json out = json::array();
            for (const auto& item : value) out.push_back(expand(item));
            return out;
        }
        if (value.is_object()) {
            json out = json::object();
            for (auto item = value.begin(); item != value.end(); ++item) out[expand(json(item.key())).get<std::string>()] = expand(item.value());
            return out;
        }
        return value;
    };

    const auto wait_reply = [&](std::int64_t id, bool allowError) -> json {
        while (true) {
            json reply;
            if (const auto found = pending.find(id); found != pending.end()) {
                reply = std::move(found->second);
                pending.erase(found);
            } else {
                if (Clock::now() >= deadline) throw Timeout {};
                reply = engine->next(deadline);
                if (!reply.is_object() || !reply.contains("id") || !(reply.contains("result") || reply.contains("error"))) continue;
                // The answer to another request waits for who asks for it. Its number is read before it is moved:
                // the right side of an assignment is evaluated first.
                const std::optional<std::int64_t> answered { reply["id"].is_number_integer() ? std::optional { reply["id"].get<std::int64_t>() } : std::nullopt };
                if (answered != id) {
                    if (answered) pending.insert_or_assign(*answered, std::move(reply));
                    continue;
                }
            }
            if (reply.contains("error")) {
                const int code { reply["error"].is_object() ? reply["error"].value("code", 0) : 0 };
                if (!allowError || (code != -32800 && code != -32801)) failure(std::format("request failed: {}", reply["error"].dump()));
            }
            return reply;
        }
    };

    // A request's identifier, or zero for a notification.
    const auto send = [&](const std::string& method, json params, bool notify) -> std::int64_t {
        ++requestId;
        json message { { "jsonrpc", "2.0" }, { "method", method }, { "params", std::move(params) } };
        if (!notify) message["id"] = requestId;
        engine->write(message);
        return notify ? 0 : requestId;
    };

    const auto check_expectations = [&](const json& step, const json& response, bool deferred) {
        const auto expected = step.find("expect");
        if (expected == step.end() || !expected->is_object()) return;
        for (auto item = expected->begin(); item != expected->end(); ++item) {
            const std::string path { item.key() };
            const json wanted = expand(item.value());
            const json* actual { pointer(response, path) };
            if (actual == nullptr) failure(std::format("{}: expected {}, and the answer has no such value", path, wanted.dump()));
            if (*actual != wanted) {
                failure(deferred ? std::format("deferred response failed assertion {}", path)
                                 : std::format("{}: expected {}, observed {}", path, wanted.dump(), actual->dump()));
            }
        }
    };

    const auto remember = [&](const fs::path& file) {
        if (originals.contains(file)) return;
        std::error_code failed;
        if (fs::exists(file, failed)) originals.emplace(file, Original { read(file), fs::last_write_time(file) });
        else originals.emplace(file, Original { std::nullopt, {} });
    };

    try {
        std::size_t index { 0 };
        while (index < session.sequence.size()) {
            const std::size_t at { index };
            const json& step = session.sequence[index++];
            const std::string action { step.value("action", std::string {}) };
            if (action == "sleep") {
                const auto until = Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double> { step.at("seconds").get<double>() });
                while (Clock::now() < until) {
                    if (Clock::now() >= deadline) throw Timeout {};
                    if (engine->poll()) failure("engine exited during the requested sleep");
                    std::this_thread::sleep_for(std::chrono::milliseconds { 50 });
                }
                continue;
            }
            if (action == "await-log") {
                const std::string wanted { step.at("contains").get<std::string>() };
                while (!engine->log_contains(wanted)) {
                    if (Clock::now() >= deadline) throw Timeout {};
                    if (engine->poll()) {
                        // What it wrote last may still be on its way.
                        std::this_thread::sleep_for(std::chrono::milliseconds { 200 });
                        if (engine->log_contains(wanted)) break;
                        failure("engine exited before the required log event");
                    }
                    std::this_thread::sleep_for(std::chrono::milliseconds { 10 });
                }
                continue;
            }
            if (action == "await") {
                const auto found = aliases.find(step.at("request").get<std::string>());
                if (found == aliases.end()) failure("a step awaits a request that is not waiting");
                const Deferred waiting { found->second };
                aliases.erase(found);
                const json response = wait_reply(waiting.id, step.value("allow_error", false));
                const auto completed = now_ns();
                result["raw_responses"].push_back(json { { "method", waiting.method }, { "reply", response }, { "started_monotonic_ns", waiting.startedNs },
                                                         { "completed_monotonic_ns", completed }, { "elapsed_ms", static_cast<double>(completed - waiting.startedNs) / 1e6 } });
                check_expectations(step, response, true);
                continue;
            }
            if (action == "write-file") {
                const fs::path file { fs::weakly_canonical(project / step.at("file").get<std::string>()) };
                if (!within_project(file)) failure("fixture edit escapes project");
                remember(file);
                write(file, expand(step.at("contents")).get<std::string>());
                continue;
            }
            if (action == "replace-file") {
                const fs::path file { fs::weakly_canonical(project / step.at("file").get<std::string>()) };
                if (!within_project(file)) failure("fixture edit escapes project");
                const std::string original { read(file) };
                const auto modified = fs::last_write_time(file);
                remember(file);
                // The time the file was written at, kept on a file beside the project: a system whose own call
                // sets a time less finely than it reads one (macOS under a runner: microseconds) is given it
                // back by its `touch`, which copies it whole.
                const bool keepsTime { step.value("preserve-mtime", false) };
                const fs::path reference { mt::temp_dir() / "time-reference" };
                if (keepsTime && os::host() != os::platform::windows) (void)tool({ "touch", "-r", str(file), str(reference) });
                const std::string from { step.at("from").get<std::string>() }, with { step.at("with").get<std::string>() };
                const auto first = original.find(from);
                if (from.empty() || first == std::string::npos || original.find(from, first + from.size()) != std::string::npos)
                    failure("fixture replacement must match exactly once");
                std::string updated { original };
                updated.replace(first, from.size(), with);
                write(file, updated);
                if (keepsTime) {
                    if (updated.size() != original.size()) failure("preserved-mtime regression requires same size");
                    std::error_code refused;
                    fs::last_write_time(file, modified, refused);
                    if ((refused || fs::last_write_time(file) != modified) && fs::exists(reference)) (void)tool({ "touch", "-m", "-r", str(reference), str(file) });
                    if (fs::last_write_time(file) != modified) failure("filesystem did not preserve exact timestamp");
                }
                if (step.value("same-second", false)) {
                    if (updated.size() != original.size()) failure("same-second regression requires same size");
                    // A real change within the same second, with another subsecond timestamp. A millisecond: NTFS
                    // counts in 100 ns ticks, and a nanosecond more rounds back to the stamp there was.
                    using namespace std::chrono;
                    const auto sinceEpoch = duration_cast<nanoseconds>(modified.time_since_epoch());
                    const auto subsecond = sinceEpoch.count() % 1000000000;
                    const nanoseconds delta { 1000000 };
                    const auto stamp = subsecond >= 0 && subsecond < 1000000000 - delta.count()
                                           ? modified + duration_cast<fs::file_time_type::duration>(delta)
                                           : modified - duration_cast<fs::file_time_type::duration>(delta);
                    fs::last_write_time(file, stamp);
                    const auto observed = duration_cast<nanoseconds>(fs::last_write_time(file).time_since_epoch());
                    if (observed == sinceEpoch || floor<seconds>(observed) != floor<seconds>(sinceEpoch))
                        failure("filesystem cannot represent a changed timestamp within the same second");
                }
                continue;
            }
            if (!action.empty()) failure(std::format("a step names the action {}, which is none", action));

            const std::string method { step.at("method").get<std::string>() };
            if (method == "shutdown" || method == "exit") failure("shutdown is managed by the replay harness");
            const bool notify { step.value("notify", false) };
            const auto started = Clock::now();
            const auto startedNs = now_ns();
            const std::int64_t id { send(method, step.contains("params") ? expand(step["params"]) : json(nullptr), notify) };
            if (const auto name = step.find("defer"); name != step.end() && !name->is_null() && name->get<std::string>() != "") {
                const std::string alias { name->get<std::string>() };
                if (notify || aliases.contains(alias)) failure("deferred request requires a unique name");
                aliases.emplace(alias, Deferred { id, method, startedNs });
                continue;
            }
            if (notify) continue;
            const json response = wait_reply(id, step.value("allow_error", false));
            const auto completed = now_ns();
            const double elapsed { static_cast<double>(completed - startedNs) / 1e6 };
            result["raw_responses"].push_back(json { { "method", method }, { "reply", response }, { "started_monotonic_ns", startedNs },
                                                     { "completed_monotonic_ns", completed }, { "elapsed_ms", elapsed } });
            const auto expectedSymbols = strings_of(step, "expected_symbols");
            const auto forbiddenSymbols = strings_of(step, "forbidden_symbols");
            if (!expectedSymbols.empty() || !forbiddenSymbols.empty()) {
                const json answerResult = response.value("result", json(nullptr));
                json items = json::array();
                if (answerResult.is_array()) items = answerResult;
                else if (answerResult.is_object()) items = answerResult.value("items", json::array());
                std::set<std::string> names;
                for (const auto& item : items) names.insert(symbol_of(item));
                result["responses"].push_back(json { { "method", method }, { "symbols", names }, { "elapsed_ms", elapsed } });
                std::vector<std::string> missing, polluted;
                for (const auto& name : expectedSymbols)
                    if (!names.contains(name)) missing.push_back(name);
                for (const auto& name : forbiddenSymbols)
                    if (names.contains(name)) polluted.push_back(name);
                std::ranges::sort(missing);
                std::ranges::sort(polluted);
                // A step may allow the engine a while to catch up (a module rebuilt in the background): it is asked
                // again until then, each answer recorded.
                const auto until = retryUntil.try_emplace(at, started + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double> { step.value("retry_seconds", 0.0) })).first->second;
                // An answer marked incomplete is asked again as an editor does while the person types: completion
                // answers before a file's modules are built, and the names come once they are.
                const bool incomplete { answerResult.is_object() && answerResult.value("isIncomplete", false) };
                if (!missing.empty() && incomplete && Clock::now() < deadline - std::chrono::seconds { 2 }) {
                    std::this_thread::sleep_for(std::chrono::milliseconds { 250 });
                    --index;
                    continue;
                }
                if ((!missing.empty() || !polluted.empty()) && Clock::now() < until) {
                    std::this_thread::sleep_for(std::chrono::milliseconds { 250 });
                    --index;
                    continue;
                }
                if (!missing.empty() || !polluted.empty()) failure(std::format("missing symbols {}; forbidden symbols {}", json(missing).dump(), json(polluted).dump()));
                json selected = json::object();
                for (const auto& item : items) {
                    const std::string name { symbol_of(item) };
                    if (std::ranges::find(expectedSymbols, name) != expectedSymbols.end()) selected[name].push_back(item);
                }
                result["responses"].back()["completion_items"] = selected;
                if (const auto fragments = step.find("expected_snippet_fragments"); fragments != step.end() && fragments->is_object()) {
                    for (auto fragment = fragments->begin(); fragment != fragments->end(); ++fragment) {
                        const std::string name { fragment.key() };
                        const json& wanted = fragment.value();
                        std::vector<std::string> texts;
                        for (const auto& item : selected.value(name, json::array())) {
                            const json* edit { pointer(item, "/textEdit/newText") };
                            texts.push_back(edit != nullptr && edit->is_string() ? edit->get<std::string>() : item.value("insertText", std::string {}));
                        }
                        const bool found { std::ranges::any_of(texts, [&](const std::string& candidate) {
                            return std::ranges::all_of(wanted, [&](const json& fragment) { return candidate.find(fragment.get<std::string>()) != std::string::npos; });
                        }) };
                        if (!found) failure(std::format("{}: missing snippet fragments {}, observed {}", name, wanted.dump(), json(texts).dump()));
                    }
                }
            }
            check_expectations(step, response, false);
        }
        if (!aliases.empty()) failure("deferred requests must be awaited before shutdown");
        (void)wait_reply(send("shutdown", nullptr, false), false);
        (void)send("exit", nullptr, true);
        engine->close_input();
        const auto code = engine->wait_until(deadline);
        if (!code) throw Timeout {};
        result["outcome"] = *code == 0 ? "pass" : "crash";
    } catch (const Timeout&) {
        result["outcome"] = "timeout";
        if (env("MCPPLS_ENGINE_SAMPLE") == "1") result["timeout_diagnostics"] = sample_at_deadline(*engine, project);
    } catch (const Closed& closed) {
        // The output can close before the process can be waited for. Its own end is observed before it is
        // cleaned up: an end that was forced is never evidence of a crash, and a clean early exit still fails.
        const auto code = engine->wait_until(std::min(deadline, Clock::now() + std::chrono::seconds { 1 }));
        result["detail"] = code ? closed.what : std::string { "stdout closed before a natural exit" };
        result["outcome"] = code && *code != 0 ? "crash" : "error";
    } catch (const Failure& failed) {
        const auto code = engine->poll();
        result["outcome"] = code && *code != 0 ? "crash" : "error";
        result["detail"] = failed.what;
    } catch (const json::exception& malformed) {
        result["outcome"] = "error";
        result["detail"] = std::format("a step is not what a step is: {}", malformed.what());
    }

    const bool stopped { engine->end() };
    result["readers_stopped"] = stopped;
    if (!stopped) {
        result["outcome"] = "error";
        result["detail"] = "inherited output descriptors remain open";
    }
    for (const auto& [file, original] : originals) {
        std::error_code ignored;
        if (!original.contents) {
            fs::remove(file, ignored);
        } else {
            (void)os::fs::write(file, *original.contents);
            fs::last_write_time(file, original.modified, ignored);
        }
    }
    const auto code = engine->poll();
    result["exit_code"] = code ? json(*code) : json(nullptr);
    result["stderr"] = engine->log();
    return result;
}

struct Client::State {
    Engine engine;
};

Client::Client(const fs::path& root, std::vector<std::string> flags) : root_ { root } {
    const Subject& s { subject() };
    if (!s.problem.empty()) mt::fail(s.problem);
    try {
        state_ = std::make_unique<State>(Engine { flags, root, s.engine });
    } catch (const Failure& failed) {
        mt::fail(failed.what);
    }
}

Client::~Client() {
    if (state_ && !stopped_) (void)state_->engine.end();
}

json Client::request(const std::string& method, json params, double seconds) {
    const std::int64_t id { ++requestId_ };
    state_->engine.write(json { { "jsonrpc", "2.0" }, { "id", id }, { "method", method }, { "params", std::move(params) } });
    const auto deadline = Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double> { seconds });
    try {
        while (true) {
            const json reply = state_->engine.next(deadline);
            if (reply.is_object() && reply.contains("method") && !reply.contains("id")) notifications_.push_back(reply);
            if (!reply.is_object() || !reply.contains("id") || reply["id"] != json(id)) continue;
            answers_.push_back(json { { "method", method }, { "reply", reply } });
            if (reply.contains("error")) mt::fail(std::format("{}: {}", method, reply["error"].dump()));
            return reply.value("result", json(nullptr));
        }
    } catch (const Timeout&) {
        mt::fail(std::format("{} was not answered within {} s", method, seconds));
    } catch (const Closed& closed) {
        mt::fail(std::format("{}: {}", method, closed.what));
    } catch (const Failure& failed) {
        mt::fail(std::format("{}: {}", method, failed.what));
    }
}

json Client::notification(std::string_view method, const std::function<bool(const json&)>& wanted, double seconds) {
    const auto is_it = [&](const json& message) { return message.value("method", std::string {}) == method && wanted(message.value("params", json(nullptr))); };
    for (auto at = notifications_.begin(); at != notifications_.end(); ++at) {
        if (!is_it(*at)) continue;
        json found = std::move(*at);
        notifications_.erase(at);
        return found.value("params", json(nullptr));
    }
    const auto deadline = Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double> { seconds });
    try {
        while (true) {
            const json message = state_->engine.next(deadline);
            if (!message.is_object() || !message.contains("method") || message.contains("id")) continue;
            if (is_it(message)) return message.value("params", json(nullptr));
            notifications_.push_back(message);
        }
    } catch (const Timeout&) {
        mt::fail(std::format("no {} came within {} s", method, seconds));
    } catch (const Closed& closed) {
        mt::fail(std::format("{}: {}", method, closed.what));
    } catch (const Failure& failed) {
        mt::fail(std::format("{}: {}", method, failed.what));
    }
}

void Client::notify(const std::string& method, json params) {
    ++requestId_;
    state_->engine.write(json { { "jsonrpc", "2.0" }, { "method", method }, { "params", std::move(params) } });
}

void Client::open_project(const fs::path& file) {
    (void)request("initialize", json { { "rootUri", uri(root_) }, { "capabilities", json::object() } });
    notify("initialized", json::object());
    notify("textDocument/didOpen", json { { "textDocument", json { { "uri", uri(file) }, { "languageId", "cpp" }, { "version", 1 }, { "text", read(file) } } } });
}

std::string Client::log() { return state_->engine.log(); }
bool Client::log_contains(std::string_view part) { return state_->engine.log_contains(part); }
std::uint64_t Client::pid() const { return state_->engine.id(); }

void Client::stop(bool kill) {
    if (stopped_) return;
    std::string problem;
    if (!kill && !state_->engine.poll()) {
        try {
            const std::int64_t id { ++requestId_ };
            state_->engine.write(json { { "jsonrpc", "2.0" }, { "id", id }, { "method", "shutdown" }, { "params", nullptr } });
            const auto deadline = Clock::now() + std::chrono::seconds { 15 };
            while (true) {
                const json reply = state_->engine.next(deadline);
                if (reply.is_object() && reply.contains("id") && reply["id"] == json(id)) break;
            }
            ++requestId_;
            state_->engine.write(json { { "jsonrpc", "2.0" }, { "method", "exit" }, { "params", nullptr } });
            state_->engine.close_input();
            const auto code = state_->engine.wait_until(Clock::now() + std::chrono::seconds { 15 });
            if (!code || *code != 0) problem = "unclean shutdown";
        } catch (const Timeout&) {
            problem = "shutdown was not answered";
        } catch (const Closed& closed) {
            problem = closed.what;
        } catch (const Failure& failed) {
            problem = failed.what;
        }
    }
    stopped_ = true;
    if (!state_->engine.end() && problem.empty()) problem = "engine left inherited pipes";
    if (!problem.empty()) mt::fail(problem);
}

json Client::record() {
    const auto code = state_->engine.poll();
    return json { { "responses", answers_ }, { "stderr", state_->engine.log() }, { "exit_code", code ? json(*code) : json(nullptr) } };
}

std::vector<std::string> engine_command(std::vector<std::string> flags) {
    const Subject& s { subject() };
    if (!s.problem.empty()) mt::fail(s.problem);
    std::vector<std::string> command;
    if (!s.runner.empty()) command.push_back(str(s.runner));
    command.push_back(str(s.engine));
    for (auto& flag : flags) command.push_back(std::move(flag));
    return command;
}

LitTest lit_test(const json& messages, std::vector<std::string> flags, double seconds) {
    flags.insert(flags.begin(), "-lit-test");
    mt::e2e::command command;
    command.argv = engine_command(std::move(flags));
    for (const auto& message : messages) {
        if (!command.input.empty()) command.input += "\n---\n";
        command.input += message.dump();
    }
    command.input += "\n";
    command.timeout = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::duration<double> { seconds });
    const auto ran = mt::e2e::run(std::move(command));
    LitTest out { .status = ran.status, .timed_out = ran.timed_out, .log = ran.err };
    if (!ran.started) out.problem = "the engine did not start";
    std::string_view rest { ran.out };
    while (!rest.empty() && out.problem.empty()) {
        constexpr std::string_view HEADER { "Content-Length: " };
        if (!rest.starts_with(HEADER)) {
            out.problem = "engine emitted invalid LSP framing";
            break;
        }
        const auto end = rest.find("\r\n\r\n");
        std::size_t size { 0 };
        if (end == std::string_view::npos || std::from_chars(rest.data() + HEADER.size(), rest.data() + end, size).ec != std::errc {} || rest.size() < end + 4 + size) {
            out.problem = "missing LSP header separator";
            break;
        }
        json reply = json::parse(rest.substr(end + 4, size), nullptr, false);
        if (reply.is_discarded()) out.problem = "a frame is not JSON";
        else out.replies.push_back(std::move(reply));
        rest.remove_prefix(end + 4 + size);
    }
    return out;
}

Ran tool(std::vector<std::string> argv, const fs::path& directory, std::string input, double seconds) {
    mt::e2e::command command;
    command.argv = std::move(argv);
    command.cwd = directory;
    command.input = std::move(input);
    command.timeout = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::duration<double> { seconds });
    auto ran = mt::e2e::run(std::move(command));
    return Ran { .status = ran.status, .started = ran.started, .timed_out = ran.timed_out, .out = std::move(ran.out), .err = std::move(ran.err) };
}

std::string host_name() {
    mt::e2e::command command;
    command.argv = { "hostname" };
    auto ran = mt::e2e::run(std::move(command));
    while (!ran.out.empty() && std::isspace(static_cast<unsigned char>(ran.out.back()))) ran.out.pop_back();
    // A machine that cannot be asked is one no lock names: a lock's owner on another host is taken to live.
    return ran && !ran.out.empty() ? ran.out : std::string { "localhost" };
}

std::uint64_t own_pid() {
    const auto self = os::process::self();
    if (!self) mt::fail("this program's identifier is not known");
    return self->id;
}

void age_access_time(const fs::path& file) {
    mt::e2e::command command;
    if (os::host() == os::platform::windows) {
        command.argv = { "powershell", "-NoProfile", "-NonInteractive", "-Command",
                         std::format("(Get-Item -LiteralPath '{}').LastAccessTimeUtc = [datetime]'1980-01-01T00:00:00Z'", str(file)) };
    } else {
        command.argv = { "touch", "-a", "-t", "197001020000", str(file) };
    }
    const auto before = os::fs::stamp_of(file);
    const auto done = mt::e2e::run(std::move(command));
    if (!done) mt::fail(std::format("the access time of {} could not be set: {}{}", str(file), done.out, done.err));
    const auto after = os::fs::stamp_of(file);
    if (before && after && before->modified_ns != after->modified_ns) mt::fail(std::format("setting the access time of {} changed when it was last written", str(file)));
}

void passed(const json& result, const fs::path& directory) {
    const fs::path kept { directory / std::format("replay-{}.json", result.value("id", std::string { "session" })) };
    write(kept, result.dump(2) + "\n");
    const std::string outcome { result.value("outcome", std::string {}) };
    const bool ok { outcome == "pass" && result.value("exit_code", json(nullptr)) == json(0) && result.value("readers_stopped", false) };
    if (ok) return;
    mt::produced(kept);
    // The end of the engine's log is the first thing anyone asks for.
    const std::string log { result.value("stderr", std::string {}) };
    std::size_t from { log.size() };
    for (int lines { 0 }; lines < 60 && from != 0; ++lines) {
        const auto newline = log.rfind('\n', from - 1);
        from = newline == std::string::npos ? 0 : newline;
    }
    std::println("--- the engine's log, its end ({}) ---{}", result.value("id", std::string {}), log.substr(from));
    mt::fail(std::format("{}: {} (exit {}){}", result.value("id", std::string {}), outcome, result.value("exit_code", json(nullptr)).dump(),
                         result.contains("detail") ? ": " + result["detail"].get<std::string>() : std::string {}));
}

const json* answer(const json& result, std::string_view method) {
    const auto responses = result.find("raw_responses");
    if (responses == result.end()) return nullptr;
    for (const auto& item : *responses)
        if (item.value("method", std::string {}) == method) return &item["reply"];
    return nullptr;
}

double elapsed_ms(const json& result, std::string_view method) {
    const auto responses = result.find("raw_responses");
    if (responses == result.end()) return 0;
    for (const auto& item : *responses)
        if (item.value("method", std::string {}) == method) return item.value("elapsed_ms", 0.0);
    return 0;
}

std::size_t log_count(const json& result, std::string_view part) {
    const std::string log { result.value("stderr", std::string {}) };
    std::size_t count { 0 };
    for (std::size_t at { log.find(part) }; at != std::string::npos; at = log.find(part, at + part.size())) ++count;
    return count;
}

std::vector<fs::path> files_under(const fs::path& directory, const std::function<bool(const fs::directory_entry&)>& wanted) {
    std::vector<fs::path> found;
    std::error_code failed;
    for (fs::recursive_directory_iterator at { directory, fs::directory_options::skip_permission_denied, failed }, end; !failed && at != end; at.increment(failed))
        if (wanted(*at)) found.push_back(at->path());
    return found;
}

std::vector<std::string> log_lines(const json& result) {
    std::vector<std::string> lines;
    const std::string log { result.value("stderr", std::string {}) };
    for (const auto line : std::views::split(log, '\n')) {
        std::string text { line.begin(), line.end() };
        if (text.ends_with('\r')) text.pop_back();
        lines.push_back(std::move(text));
    }
    return lines;
}

}  // namespace engine
