#include <stdio.h>
#include "extra.h"

void suspicious_code(void) {
    int x;
    // warning: variable 'x' is uninitialized when used here [-Wuninitialized]
    if (x) { 
        printf("Value: %d\n", x);
    }

    unsigned int u = 10;
    int s = -5;
    
    // warning: comparison of integer expressions of different signedness: 'int' and 'unsigned int' [-Wsign-compare]
    if (s < u) { 
        printf("Comparison made\n");
    }

    // warning: format '%s' expects argument of type 'char *', but argument 2 has type 'int' [-Wformat=]
    printf("Number: %s\n", 123); 
}
