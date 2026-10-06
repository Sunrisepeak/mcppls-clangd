//===-- WindowsCrashDumps.cpp -------------------------------------*-C++-*-===//
//
// Part of the LLVM Project under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#include "support/WindowsCrashDumps.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/raw_ostream.h"

#ifdef _WIN32

#include <windows.h>
#include <dbghelp.h>
#include <time.h>
#endif

namespace clang {
namespace clangd {

void installWindowsCrashDumpsImpl(llvm::StringRef DumpsDir);

void installWindowsCrashDumps(llvm::StringRef DumpsDir) {
#ifdef _WIN32
  if (DumpsDir.empty())
    return;
  installWindowsCrashDumpsImpl(DumpsDir);
#endif
}

} // namespace clangd
} // namespace clang

#ifdef _WIN32
namespace clang {
namespace clangd {
namespace {

llvm::SmallString<256> DumpsDirectory;

void writeMinidump(EXCEPTION_POINTERS *ExceptionPointers) {
  if (DumpsDirectory.empty())
    return;

  llvm::SmallString<256> Path(DumpsDirectory);
  llvm::sys::fs::create_directories(Path);
  const time_t Now = time(nullptr);
  char Stamp[32];
  strftime(Stamp, sizeof(Stamp), "%Y%m%d-%H%M%S", localtime(&Now));
  llvm::sys::path::append(Path, "clangd-crash-" + std::string(Stamp) + ".dmp");

  HANDLE Process = GetCurrentProcess();
  DWORD ProcessId = GetCurrentProcessId();
  if (!DuplicateHandle(Process, Process, Process, &Process,
                       PROCESS_ALL_ACCESS, FALSE, 0))
    Process = GetCurrentProcess();

  MINIDUMP_EXCEPTION_INFORMATION ExceptionInfo;
  ExceptionInfo.ThreadId = GetCurrentThreadId();
  ExceptionInfo.ExceptionPointers = ExceptionPointers;
  ExceptionInfo.ClientPointers = FALSE;

  HANDLE File = CreateFileA(Path.c_str(), GENERIC_WRITE, 0, nullptr,
                            CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (File == INVALID_HANDLE_VALUE)
    return;
  MiniDumpWriteDump(Process, ProcessId, File, MiniDumpWithFullMemory |
                                                    MiniDumpWithHandleData,
                    ExceptionPointers ? &ExceptionInfo : nullptr, nullptr,
                    nullptr);
  CloseHandle(File);
}

LONG WINAPI crashDumpsFilter(EXCEPTION_POINTERS *ExceptionPointers) {
  writeMinidump(ExceptionPointers);
  return EXCEPTION_CONTINUE_SEARCH; // terminate exactly as before
}

} // namespace

void installWindowsCrashDumpsImpl(llvm::StringRef DumpsDir) {
  DumpsDirectory = DumpsDir;
  llvm::sys::fs::make_absolute(DumpsDirectory);
  SetUnhandledExceptionFilter(crashDumpsFilter);
  // Terminate on aborts and CRT errors the same way (pure-virtual, invalid
  // parameter, fast-fail path aside).
  _set_abort_behavior(_CALL_REPORTFAULT, _CALL_REPORTFAULT);
}

} // namespace clangd
} // namespace clang
#endif
