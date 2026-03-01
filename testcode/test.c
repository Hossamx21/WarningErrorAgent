#include <stdio.h>
#include <stdlib.h>
#include "math_utils.h"
// A weird GCC specific directive that throws an obscure warning
#pragma GCC diagnostic warning "-Wunknown-pragmas"
#pragma this_is_a_fake_pragma_to_confuse_the_compiler
// WARNING 1: Unused parameter
void init_sensor(int config_id) {
    printf("Sensor initialized.\n");
}

int main() {
    // WARNING 2: Unused variable
    // int diagnostic_code = 0xFF; 

    int x = 50;
    int sum = add_numbers(10, x);
    
    init_sensor(1);
    printf("System ready. Sum: %d\n", sum);

    return 0;
}