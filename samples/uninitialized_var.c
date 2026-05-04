#include <stdio.h>

// CWE-457: Uninitialized variable used in computation
int compute(int flag) {
    int result;          // never initialized
    if (flag > 0) {
        result = flag * 2;
    }
    return result;       // may be uninitialized if flag <= 0
}

// Uninitialized pointer dereference
void bad_pointer_use(void) {
    int *ptr;            // uninitialized pointer
    *ptr = 99;           // undefined behavior
}

int main(void) {
    int x = compute(0);
    printf("result: %d\n", x);
    return 0;
}
