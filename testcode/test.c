#include <stdio.h>
#include <stdlib.h>

// WARNING 1: Unused parameter
// We pass 'config_id' into the function, but never actually use it inside.
void init_sensor(int config_id) {
    printf("Sensor initialized.\n");
}

int main() {
    // WARNING 2: Unused variable
    // We declare a variable and give it a hex value, but never read it later.
    int diagnostic_code = 0xFF; 

    int x = 50;
    int sum = x+10;
    
    init_sensor(1);
    printf("System ready. Sum: %d\n", sum);

    return 0;
}