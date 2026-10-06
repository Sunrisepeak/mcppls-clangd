//===-- WindowsCrashDumps.h ---------------------------------------*-C++-*-===//
//
// Part of the LLVM Project under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//
//
// Last-chance crash capture for Windows: an unhandled exception in any
// thread writes a minidump (with full memory and thread stacks) into a
// caller-provided directory, then the process terminates as it would have.
//
// Release builds print no usable stack on Windows without a debugger, which
// has kept every hard crash (unresolved-import Build AST crash, silent
// correct-command crash, save fan-out crash loop) out of reach. With dumps
// enabled next to public PDBs, each crash yields symbolized stacks.
//
// Disabled unless a dump directory is configured.
//
//===----------------------------------------------------------------------===//

#ifndef LLVM_CLANG_TOOLS_EXTRA_CLANGD_SUPPORT_WINDOWSCRASHDUMPS_H
#define LLVM_CLANG_TOOLS_EXTRA_CLANGD_SUPPORT_WINDOWSCRASHDUMPS_H

#include "llvm/ADT/StringRef.h"

namespace clang {
namespace clangd {

/// Installs the unhandled-exception filter that writes minidumps into
/// \p DumpsDir. No-op on non-Windows platforms or when \p DumpsDir is empty.
void installWindowsCrashDumps(llvm::StringRef DumpsDir);

} // namespace clangd
} // namespace clang

#endif // LLVM_CLANG_TOOLS_EXTRA_CLANGD_SUPPORT_WINDOWSCRASHDUMPS_H
