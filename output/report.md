
# Build Failure Report

**Root Cause**
Uninitialized variables and deprecated function usage

**Category**
Coding Standards Violation/Safety Issues

**Blocking**
True

**Suggested Fix**
Remove unused variables and initialize all local variables with appropriate values; replace 'legacyInit()' with the modern equivalent from init_system.

**Confidence**
0.95

**Warnings (first 50)**
gcc -Wall -Wextra -c main.c
main.c:6:9: warning: unused variable 'count' [-Wunused-variable]
    6 |     int count = 42; // unused variable warning
main.c:8:5: warning: 'legacyInit' is deprecated: use init_system instead [-Wdeprecated-declarations]
    8 |     legacyInit(); // deprecated warning
gcc -Wall -Wextra -c extra.c
extra.c:7:9: warning: variable 'x' is uninitialized when used here [-Wuninitialized]
extra.c:13:9: warning: comparison of integer expressions of different signedness: 'int' and 'unsigned int' [-Wsign-compare]
extra.c:17:15: warning: format '%s' expects argument of type 'char *', but argument 2 has type 'int' [-Wformat=]