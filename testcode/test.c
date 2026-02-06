#include <stdlib.h>

int main() {
    // WARNING: Unused variable
    int unused_var = 100;

    // ERROR: Missing semicolon
    int x = 50
    
    // WARNING: Implicit declaration (printf requires stdio.h)
    printf("Result: %d\n", x);

    return 0;
}