// Diagnostic counterfactual only: append the existing prefetch override to
// each image-initiated child's complete environment when the caller has not
// supplied it. The parent environment, spawn options, grants, streams and
// arguments are unchanged. No workload names or private worker flags are used.
OKRUN_IMAGE_ABI int own_kal_process_spawn(
    const kal_spawn* how, const char* path, kal_uintptr path_len,
    const char** argv, const kal_uintptr* argv_lens, kal_uintptr argc,
    const char** envp, const kal_uintptr* envp_lens, kal_uintptr envc,
    const kal_spawn_streams* streams, kal_process* out) {
    auto original = [&] {
        return kal_process_spawn(how, path, path_len, argv, argv_lens, argc,
                                 envp, envp_lens, envc, streams, out);
    };
    constexpr char prefix[] = "OKRUN_PREFETCH=";
    constexpr char value[] = "OKRUN_PREFETCH=0";
    if ((envc && (!envp || !envp_lens)) ||
        envc >= (~kal_uintptr(0) / sizeof(kal_uintptr)) - 1 ||
        envc >= (~kal_uintptr(0) / sizeof(const char*)) - 1)
        return original();
    for (kal_uintptr i = 0; i < envc; ++i) {
        if (!envp[i]) return original();
        if (envp_lens[i] < sizeof(prefix)-1) continue;
        kal_uintptr j = 0;
        while (j < sizeof(prefix)-1 && envp[i][j] == prefix[j]) ++j;
        if (j == sizeof(prefix)-1) return original();
    }
    const kal_uintptr slots_size = (envc+1) * sizeof(const char*);
    const kal_uintptr lens_size = (envc+1) * sizeof(kal_uintptr);
    auto** slots = static_cast<const char**>(kal_alloc(slots_size, alignof(const char*)));
    auto* lens = static_cast<kal_uintptr*>(kal_alloc(lens_size, alignof(kal_uintptr)));
    if (!slots || !lens) {
        if (slots) kal_free(slots, slots_size, alignof(const char*));
        if (lens) kal_free(lens, lens_size, alignof(kal_uintptr));
        return kal_err_no_memory;
    }
    for (kal_uintptr i = 0; i < envc; ++i) { slots[i] = envp[i]; lens[i] = envp_lens[i]; }
    slots[envc] = value; lens[envc] = sizeof(value)-1;
    const int result = kal_process_spawn(how, path, path_len, argv, argv_lens, argc,
                                        slots, lens, envc+1, streams, out);
    kal_free(lens, lens_size, alignof(kal_uintptr));
    kal_free(slots, slots_size, alignof(const char*));
    return result;
}
