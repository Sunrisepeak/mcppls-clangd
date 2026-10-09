"""Package source binding rejects stale or unrelated capability inputs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from package_identity import verify_build_source


class PackageSourceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'independent source'
        self.build = self.root / 'build'
        (self.source / 'llvm').mkdir(parents=True)
        self.build.mkdir()
        self.canary = self.source / 'llvm/CMakeLists.txt'
        self.canary.write_text('original configured source\n')
        self.git('init', '-q')
        self.git('add', 'llvm/CMakeLists.txt')
        self.git('-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'source')
        self.stamp = {'llvm-tree-commit': self.git('rev-parse', 'HEAD').strip()}
        self.marker = self.source / '.mcppls-clangd-patched'
        self.marker.write_text('series\n')
        self.cache = self.build / 'CMakeCache.txt'
        self.cache.write_text(f'CMAKE_HOME_DIRECTORY:INTERNAL={self.source}/llvm\n')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args], text=True)

    def verify(self):
        return verify_build_source(self.source, self.build, self.stamp, 'series')

    def test_independent_configured_source_is_used(self):
        self.assertEqual(self.verify(), self.source.resolve())

    def test_other_configured_tree_is_rejected(self):
        self.cache.write_text(f'CMAKE_HOME_DIRECTORY:INTERNAL={self.root}/other/llvm\n')
        with self.assertRaisesRegex(ValueError, 'CMake build source'):
            self.verify()

    def test_wrong_source_commit_is_rejected(self):
        self.stamp['llvm-tree-commit'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'built source stamp'):
            self.verify()

    def test_dirty_capability_source_is_rejected(self):
        self.canary.write_text('modified after build\n')
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()

    def test_stale_patch_marker_is_rejected(self):
        self.marker.write_text('previous series\n')
        with self.assertRaisesRegex(ValueError, 'ordered patch series'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
