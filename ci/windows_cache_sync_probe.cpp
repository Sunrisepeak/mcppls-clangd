#include <windows.h>
#include <cstdio>
#include <cstring>

static unsigned checks, failures;
static void check(bool ok, const char *name) {
  ++checks;
  if (!ok) {
    ++failures;
    std::fprintf(stderr, "FAIL %s (Windows error %lu)\n", name, GetLastError());
  }
}
int main() {
  constexpr wchar_t name[] = L"cache-sync-probe.tmp";
  constexpr char contents[] = "owned module cache durability";
  constexpr DWORD bytes = sizeof(contents) - 1;
  constexpr DWORD sharing = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE;
  HANDLE file = CreateFileW(name, GENERIC_READ | GENERIC_WRITE, sharing,
                            nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
  check(file != INVALID_HANDLE_VALUE, "create new owned payload");
  if (file == INVALID_HANDLE_VALUE)
    return 2;
  DWORD transferred = 0;
  check(WriteFile(file, contents, bytes, &transferred, nullptr) && transferred == bytes,
        "write exact payload");
  check(FlushFileBuffers(file) != 0, "flush original writable handle");
  check(CloseHandle(file) != 0, "close original handle");
  file = CreateFileW(name, GENERIC_READ, sharing, nullptr, OPEN_EXISTING,
                     FILE_ATTRIBUTE_NORMAL, nullptr);
  check(file != INVALID_HANDLE_VALUE, "reopen payload read only");
  if (file == INVALID_HANDLE_VALUE)
    return 2;
  char actual[sizeof(contents)] = {};
  check(ReadFile(file, actual, bytes, &transferred, nullptr) && transferred == bytes &&
            std::memcmp(actual, contents, bytes) == 0,
        "read exact payload through read only handle");
  SetLastError(ERROR_SUCCESS);
  const bool read_only_refused = !FlushFileBuffers(file) &&
                                GetLastError() == ERROR_ACCESS_DENIED;
  check(read_only_refused, "read only flush rejected with access denied");
  check(CloseHandle(file) != 0, "close read only handle");
  file = CreateFileW(name, GENERIC_READ | GENERIC_WRITE, sharing, nullptr,
                     OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  check(file != INVALID_HANDLE_VALUE, "reopen payload read write without truncation");
  if (file == INVALID_HANDLE_VALUE)
    return 2;
  check(FlushFileBuffers(file) != 0, "flush reopened writable handle");
  std::memset(actual, 0, sizeof(actual));
  check(ReadFile(file, actual, bytes, &transferred, nullptr) && transferred == bytes &&
            std::memcmp(actual, contents, bytes) == 0,
        "flush preserves payload bytes");
  LARGE_INTEGER size{};
  check(GetFileSizeEx(file, &size) && size.QuadPart == bytes,
        "reopen and flush preserve payload size");
  check(CloseHandle(file) != 0, "close reopened writable handle");
  check(DeleteFileW(name) != 0, "remove owned probe payload");
  std::printf("{\"checks\":%u,\"failures\":%u,\"read_only_flush_refused\":%s,"
              "\"outcome\":\"%s\"}\n", checks, failures,
              read_only_refused ? "true" : "false", failures ? "failure" : "success");
  return failures ? 1 : 0;
}
