// Observational T10 control: the same source against the host runtime and the
// public openkal runtime. No production failure is converted into a passing test.
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <system_error>

namespace fs = std::filesystem;

static void show(const char* name, const fs::path& path, const std::error_code& ec) {
  std::cout << name << " error=" << ec.value() << " path=" << std::quoted(path.generic_string())
            << " message=" << std::quoted(ec.message()) << '\n';
}

int main() {
  std::error_code ec;
  const auto cwd = fs::current_path(ec);
  show("current_path", cwd, ec);
  if (ec) return 1;
  std::cout << "cwd_is_absolute=" << cwd.is_absolute() << '\n';
  const auto base = cwd / "filesystem-review-owned";
  if (!fs::create_directory(base, ec) || ec) return 2;
  { std::ofstream file(base / "leaf"); file << "review\n"; if (!file) return 3; }
  show("absolute_cwd", fs::absolute(cwd, ec), ec);
  ec.clear();
  const auto canonical = fs::canonical(base, ec);
  show("canonical_base", canonical, ec);
  ec.clear();
  const auto weak = fs::weakly_canonical(base / "leaf", ec);
  show("weakly_canonical_leaf", weak, ec);
  ec.clear();
  fs::directory_iterator it(base, ec);
  if (ec || it == fs::directory_iterator()) return 4;
  const auto entry = it->path();
  show("walked_entry", entry, ec);
  std::cout << "lexically_relative=" << std::quoted(entry.lexically_relative(base).generic_string()) << '\n';
  ec.clear();
  const auto relative = fs::relative(entry, base, ec);
  show("relative_walked_entry", relative, ec);
  ec.clear();
  if (!fs::remove(base / "leaf", ec) || ec || !fs::remove(base, ec) || ec) return 5;
  std::cout << "review_complete=1\n";
}
