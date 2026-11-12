// The engine's conformance cases as one program, `engine-cts` (README.md): the cases are the
// objects of the files beside this one, each a regression run against the subject the environment names
// (harness.cppm). The program speaks the mtest protocol, so mtest lists, selects, schedules
// and records the cases; alone it runs them one after another.
import std;
import mcpplibs.mtest;

int main(int argc, char** argv) {
    return mcpplibs::mtest::run(argc, argv);
}
