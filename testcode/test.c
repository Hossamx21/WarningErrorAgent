#include <stdio.h>
#include <stdlib.h>

int main() {
    int x = 50;
    printf("Result: %d\n", x);
    
    // --- THE TRAP ---
    // We call this function, but we haven't included "math_utils.h"
    // The agent must search the DB to find where "add_numbers" is defined.
    int sum = add_numbers(10, 20); 
    printf("Sum: %d\n", sum);
    // ----------------

    return 0;
}