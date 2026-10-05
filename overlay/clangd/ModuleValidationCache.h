//===-- ModuleValidationCache.h ---------------------------------*- C++-*-===//
//
// Part of the LLVM Project under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//
//
// Memoizes the outcome of validating a built module file (BMI).
//
// Validating a BMI is expensive: the reader parses the module's control
// blocks and re-hashes every user input file the module unit recorded. The
// preamble re-runs this validation for every request that reuses prerequisite
// modules, so a file importing many modules pays the full validation cost on
// every keystroke even when nothing changed.
//
// A memo entry records the up-to-date verdict plus the (size, mtime)
// identity of the BMI and of every user input file the validation read. A
// later lookup re-stats those files: when none of them moved, the verdict is
// reused instead of recomputing it. Any drift falls back to a full
// validation, so the memo can only save work, never change the outcome. Like
// the compiler's own default BMI staleness checks, identity is (size, mtime):
// a content change that preserves both is not detected by the fast path. A
// validation that read an input through an overlay buffer (an unsaved edit)
// is not memoized at all, because its outcome depends on the buffer rather
// than the file the fast path re-stats.
//
// Only up-to-date verdicts are memoized: a stale result leads to a rebuild,
// and the rebuilt BMI has a new identity that misses anyway. Entries are
// bounded; when the bound is hit the cache is dropped wholesale. The working
// set is the project's module count, so this stays small in practice. The
// cache is process-wide: a clangd process hosts a single language-server
// session.
//
//===----------------------------------------------------------------------===//

#ifndef LLVM_CLANG_TOOLS_EXTRA_CLANGD_MODULE_VALIDATION_CACHE_H
#define LLVM_CLANG_TOOLS_EXTRA_CLANGD_MODULE_VALIDATION_CACHE_H

#include "llvm/ADT/StringMap.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/FileSystem.h"
#include <chrono>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace clang {
namespace clangd {

class ModuleValidationCache {
public:
  struct FileIdentity {
    uint64_t Size = 0;
    llvm::sys::TimePoint<> ModTime = {};
    bool operator==(const FileIdentity &Other) const {
      return Size == Other.Size && ModTime == Other.ModTime;
    }
    bool operator!=(const FileIdentity &Other) const {
      return !(*this == Other);
    }
  };

  /// The (size, mtime) identity of a regular file, or nullopt when the file
  /// cannot be stated (missing, unreadable, or a directory). The mtime is
  /// truncated to seconds: clang's FileEntry records second-precision times,
  /// and the fast path compares identities across that boundary.
  static std::optional<FileIdentity> identityOf(llvm::StringRef Path) {
    llvm::sys::fs::file_status Status;
    if (std::error_code EC = llvm::sys::fs::status(Path, Status))
      return std::nullopt;
    if (llvm::sys::fs::is_directory(Status) || !llvm::sys::fs::is_regular_file(Status))
      return std::nullopt;
    return FileIdentity{
        static_cast<uint64_t>(Status.getSize()),
        std::chrono::time_point_cast<std::chrono::seconds>(
            Status.getLastModificationTime())};
  }

  /// Returns true when a previous validation of \p BMIPath under the
  /// dependency chain \p ChainKey concluded up-to-date and neither the BMI
  /// nor any recorded input has moved since. Any doubt returns false.
  bool isFresh(llvm::StringRef BMIPath, llvm::StringRef ChainKey) {
    std::lock_guard<std::mutex> Lock(Mutex);
    auto It = Entries.find(key(BMIPath, ChainKey));
    if (It == Entries.end())
      return false;
    if (identityOf(BMIPath) != It->second.BMI) {
      Entries.erase(It);
      return false;
    }
    for (const auto &Input : It->second.Inputs)
      if (identityOf(Input.first) != Input.second) {
        Entries.erase(It);
        return false;
      }
    return true;
  }

  /// Records a fresh up-to-date verdict. \p Inputs carries the identity of
  /// every user input file the validation read; a validation whose inputs
  /// were read through an overlay buffer must not be recorded (pass an empty
  /// \p Inputs to skip memoization).
  void markFresh(llvm::StringRef BMIPath, llvm::StringRef ChainKey,
                 std::vector<std::pair<std::string, FileIdentity>> Inputs) {
    if (Inputs.empty())
      return;
    auto BMI = identityOf(BMIPath);
    if (!BMI)
      return;
    std::lock_guard<std::mutex> Lock(Mutex);
    if (Entries.size() >= Bound)
      Entries.clear();
    Entries[key(BMIPath, ChainKey)] = {std::move(*BMI), std::move(Inputs)};
  }

private:
  static std::string key(llvm::StringRef BMIPath, llvm::StringRef ChainKey) {
    std::string Result;
    Result.reserve(BMIPath.size() + ChainKey.size() + 1);
    Result.append(BMIPath);
    Result.push_back('\0');
    Result.append(ChainKey);
    return Result;
  }

  struct Entry {
    FileIdentity BMI;
    std::vector<std::pair<std::string, FileIdentity>> Inputs;
  };

  static constexpr size_t Bound = 256;
  llvm::StringMap<Entry> Entries;
  std::mutex Mutex;
};

inline ModuleValidationCache &getModuleValidationCache() {
  static ModuleValidationCache Cache;
  return Cache;
}

} // namespace clangd
} // namespace clang

#endif // LLVM_CLANG_TOOLS_EXTRA_CLANGD_MODULE_VALIDATION_CACHE_H
