// What LLVM Support, and the C library beneath it, answer an ok image for each name given:
// the image's own name, the current directory, and per name: is_absolute, make_absolute,
// exists, a raw open/fstat/read, and MemoryBuffer::getFile (what clangd reads a file with).
#include "llvm/ADT/SmallString.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/raw_ostream.h"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

static int anchor;

int main(int argc, char** argv) {
  auto& o = llvm::outs();
  o << "main-executable: " << llvm::sys::fs::getMainExecutable(argv[0], (void*)&anchor) << "\n";
  o << "parent of it: " << llvm::sys::path::parent_path(llvm::sys::fs::getMainExecutable(argv[0], (void*)&anchor)) << "\n";
  llvm::SmallString<256> cwd;
  auto ec = llvm::sys::fs::current_path(cwd);
  o << "current_path: " << cwd << " (" << (ec ? ec.message() : "ok") << ")\n";
  char raw[4096];
  o << "getcwd: " << (getcwd(raw, sizeof raw) ? raw : std::strerror(errno)) << "\n";
  for (int i = 1; i < argc; ++i) {
    llvm::StringRef a(argv[i]);
    llvm::SmallString<256> abs(a);
    llvm::sys::fs::make_absolute(abs);
    o << "\n[" << a << "]\n  is_absolute=" << llvm::sys::path::is_absolute(a)
      << " is_absolute(windows)=" << llvm::sys::path::is_absolute(a, llvm::sys::path::Style::windows)
      << "\n  make_absolute=" << abs << "\n  exists=" << llvm::sys::fs::exists(a) << "\n";
    errno = 0;
    int fd = ::open(argv[i], O_RDONLY | O_CLOEXEC);
    o << "  open -> " << fd << " errno=" << errno << " " << (errno ? std::strerror(errno) : "") << "\n";
    if (fd >= 0) {
      struct stat st;
      errno = 0;
      int r = ::fstat(fd, &st);
      o << "  fstat -> " << r << " size=" << (long long)st.st_size << " errno=" << errno << "\n";
      errno = 0;
      long n = ::read(fd, raw, 64);
      o << "  read -> " << n << " errno=" << errno << " " << (errno ? std::strerror(errno) : "") << "\n";
      errno = 0;
      long s = ::lseek(fd, 0, SEEK_SET);
      o << "  lseek -> " << s << " errno=" << errno << "\n";
      ::close(fd);
    }
    auto mb = llvm::MemoryBuffer::getFile(a);
    o << "  MemoryBuffer::getFile -> " << (mb ? "ok size " + std::to_string((*mb)->getBufferSize()) : mb.getError().message()) << "\n";
    llvm::SmallString<256> real;
    auto rec = llvm::sys::fs::real_path(a, real);
    o << "  real_path -> " << (rec ? rec.message() : std::string(real.str())) << "\n";
    int ofd;
    llvm::SmallString<256> rp;
    auto oec = llvm::sys::fs::openFileForRead(a, ofd, llvm::sys::fs::OF_None, &rp);
    o << "  openFileForRead -> " << (oec ? oec.message() : "ok, real path " + std::string(rp.str())) << "\n";
    if (!oec) ::close(ofd);
  }
  return 0;
}
