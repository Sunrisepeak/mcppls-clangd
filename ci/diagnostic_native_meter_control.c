#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static void burn_ms(long ms) {
    struct timespec start, now;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &start);
    do {
        clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &now);
    } while ((now.tv_sec-start.tv_sec)*1000000000L+now.tv_nsec-start.tv_nsec < ms*1000000L);
}
static void cleanup(void) { burn_ms(30); }
int main(int argc, char **argv) {
    if (atexit(cleanup)) return 2;
    burn_ms(10);
    if (argc>1 && argv[1][0]=='e') exit(0);
    if (argc>1 && argv[1][0]=='q') _exit(0);
    return 0;
}
