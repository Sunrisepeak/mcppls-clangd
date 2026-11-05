#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

/* Diagnostic interposition of the existing native executable only.  It
 * changes neither argv nor the requested worker ownership/resource policy.
 * It records the main boundary and emits one report after the program's exit
 * handlers, or immediately when the program requests an immediate exit. */
typedef int (*main_fn)(int, char **, char **);
typedef int (*start_fn)(main_fn, int, char **, void (*)(void), void (*)(void),
                        void (*)(void), void *);
static main_fn original_main;
static const char *output_folder;
static unsigned long long main_started;
static unsigned long long main_ended;
struct cpu_usage { unsigned long long user_us, system_us; };
static struct cpu_usage main_started_usage, main_ended_usage;
static int main_result;
static const char *main_boundary;
static int measured_active;
static void fail_meter(void) {
    syscall(SYS_exit_group, 125);
    __builtin_unreachable();
}
static unsigned long long cpu_now(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value)) return 0;
    return (unsigned long long)value.tv_sec * 1000000000ull + value.tv_nsec;
}
static struct cpu_usage usage_now(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) fail_meter();
    return (struct cpu_usage){
        (unsigned long long)usage.ru_utime.tv_sec * 1000000ull + usage.ru_utime.tv_usec,
        (unsigned long long)usage.ru_stime.tv_sec * 1000000ull + usage.ru_stime.tv_usec};
}
static void emit_meter(void) {
    if (!measured_active) return;
    const unsigned long long end = cpu_now();
    const struct cpu_usage end_usage = usage_now();
    measured_active = 0;
    char path[4096], data[1536];
    const int path_size = snprintf(path, sizeof path, "%s/native-%ld.json", output_folder, (long)getpid());
    const int data_size = snprintf(data, sizeof data,
        "{\"pid\":%ld,\"before_main_ns\":%llu,\"after_main_ns\":%llu,\"main_ns\":%llu,\"after_exit_callbacks_ns\":%llu,\"cleanup_ns\":%llu,\"result\":%d,\"boundary\":\"%s\","
        "\"before_main_user_us\":%llu,\"before_main_system_us\":%llu,"
        "\"after_main_user_us\":%llu,\"after_main_system_us\":%llu,"
        "\"after_exit_callbacks_user_us\":%llu,\"after_exit_callbacks_system_us\":%llu}\n",
        (long)getpid(), main_started, main_ended, main_ended-main_started,
        end, end-main_ended, main_result, main_boundary,
        main_started_usage.user_us, main_started_usage.system_us,
        main_ended_usage.user_us, main_ended_usage.system_us,
        end_usage.user_us, end_usage.system_us);
    if (path_size <= 0 || path_size >= (int)sizeof path || data_size <= 0 || data_size >= (int)sizeof data)
        fail_meter();
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) fail_meter();
    const ssize_t written = write(fd, data, (size_t)data_size);
    if (close(fd) || written != data_size) fail_meter();
}
/* A preload constructor runs before the executable's constructors. Register
 * this first so the executable's later atexit registrations run before it.
 * Calibration below checks that this boundary includes actual CPU-consuming
 * handlers registered by the measured program. It precedes libc's final
 * stream shutdown and therefore is named exit_callbacks, not process exit. */
__attribute__((constructor)) static void register_meter(void) {
    if (atexit(emit_meter)) fail_meter();
}
static void record_main_end(int result, const char *boundary) {
    if (!measured_active || main_ended) return;
    main_ended = cpu_now(); main_result = result; main_boundary = boundary;
    main_ended_usage = usage_now();
}
static int measured_main(int argc, char **argv, char **envp) {
    const char *wanted = getenv("MCPP_DIAG_PHASE_BINARY");
    const char *folder = getenv("MCPP_DIAG_PHASE_DIR");
    char self[4096];
    ssize_t length = readlink("/proc/self/exe", self, sizeof self - 1);
    if (!wanted || !folder || length < 0 || length >= (ssize_t)sizeof self - 1)
        return original_main(argc, argv, envp);
    self[length] = 0;
    if (strcmp(self, wanted)) return original_main(argc, argv, envp);
    output_folder = folder;
    main_started = cpu_now();
    main_started_usage = usage_now();
    measured_active = 1;
    const int result = original_main(argc, argv, envp);
    record_main_end(result, "main-return");
    return result;
}
_Noreturn void exit(int status) {
    record_main_end(status, "exit");
    void (*next)(int) = (void (*)(int))dlsym(RTLD_NEXT, "exit");
    if (next) next(status);
    fail_meter();
    __builtin_unreachable();
}
_Noreturn void _exit(int status) {
    record_main_end(status, "_exit");
    emit_meter();
    syscall(SYS_exit_group, status);
    __builtin_unreachable();
}
_Noreturn void _Exit(int status) { _exit(status); }
int __libc_start_main(main_fn main, int argc, char **argv,
                      void (*init)(void), void (*fini)(void),
                      void (*rtld_fini)(void), void *stack_end) {
    start_fn next = (start_fn)dlsym(RTLD_NEXT, "__libc_start_main");
    if (!next) fail_meter();
    original_main = main;
    return next(measured_main, argc, argv, init, fini, rtld_fini, stack_end);
}
