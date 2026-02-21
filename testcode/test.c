#include <stdio.h>
#include <stdlib.h>
#include "math_utils.h"

// WARNING 1: Unused parameter
void init_sensor(int config_id) {
    printf("Sensor initialized.\n");
}

int main() {
    // WARNING 2: Unused variable
    int diagnostic_code = 0xFF; 

    int x = 50;
    int sum = add_numbers(10, x);
    
    init_sensor(1);
    printf("System ready. Sum: %d\n", sum);

    return 0;
}