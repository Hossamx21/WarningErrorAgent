#include <stdio.h>
#include "util.h"
#include "extra.h"

int main(void) {
    int count = 42; // unused variable warning
    printf("Result: %d\n", compute(5));
    legacyInit(); // deprecated warning
    suspicious_code();
    return 0;
}
