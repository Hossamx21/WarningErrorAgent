#include "util.h"

int compute(int x) {
    // Intentional error: returning int as char* triggers invalid conversion in C++
    // For C, force a type mismatch via incompatible pointer return in a helper.
    return x + missing_symbol(); // undefined reference
}

void legacyInit(void) {
}
