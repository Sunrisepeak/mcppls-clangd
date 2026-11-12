// The engine's end-to-end regressions as one program, `engine-cts` (README.md): the cases are the
// objects of the files of e2e/, each a regression run against the subject the environment names
// (src/harness.cppm). The program speaks the mtest protocol, so mtest lists, selects, schedules
// and records the cases; alone it runs them one after another.
import std;
import mcpplibs.mtest;

int main(int argc, char** argv) {
    return mcpplibs::mtest::run(argc, argv);
}
