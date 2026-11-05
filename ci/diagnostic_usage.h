/* Linux diagnostic counters only; no public runtime interface. */
#pragma once
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MCPP_DIAG_USAGE_FIELDS(X) \
    X(user_us) X(system_us) X(minor_faults) X(major_faults) \
    X(voluntary_switches) X(involuntary_switches) X(input_blocks) X(output_blocks) \
    X(thread_user_us) X(thread_system_us) X(thread_minor_faults) X(thread_major_faults) \
    X(thread_voluntary_switches) X(thread_involuntary_switches) \
    X(thread_input_blocks) X(thread_output_blocks) X(tid)

struct mcpp_diag_usage {
#define MCPP_DIAG_DECLARE(name) unsigned long long name;
    MCPP_DIAG_USAGE_FIELDS(MCPP_DIAG_DECLARE)
#undef MCPP_DIAG_DECLARE
};

static int mcpp_diag_read_usage(struct mcpp_diag_usage *out) {
    struct rusage process, thread;
    if (getrusage(RUSAGE_SELF, &process) || getrusage(RUSAGE_THREAD, &thread)) return -1;
#define MCPP_DIAG_COPY(prefix, value) \
    out->prefix##user_us = (unsigned long long)value.ru_utime.tv_sec * 1000000ull + value.ru_utime.tv_usec; \
    out->prefix##system_us = (unsigned long long)value.ru_stime.tv_sec * 1000000ull + value.ru_stime.tv_usec; \
    out->prefix##minor_faults = value.ru_minflt; \
    out->prefix##major_faults = value.ru_majflt; \
    out->prefix##voluntary_switches = value.ru_nvcsw; \
    out->prefix##involuntary_switches = value.ru_nivcsw; \
    out->prefix##input_blocks = value.ru_inblock; \
    out->prefix##output_blocks = value.ru_oublock;
    MCPP_DIAG_COPY(, process)
    MCPP_DIAG_COPY(thread_, thread)
#undef MCPP_DIAG_COPY
    out->tid = (unsigned long long)syscall(SYS_gettid);
    return 0;
}
