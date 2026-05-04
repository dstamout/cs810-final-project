#include <stdio.h>

// CWE-190: Integer overflow used as allocation size
void integer_overflow_alloc(void) {
    int n = 1073741825; // just over INT_MAX / 2
    int size = n * 2;   // overflows to negative
    printf("Computed size: %d\n", size);
}

// CWE-369: Division by zero
int divide(int a, int b) {
    return a / b;  // no check that b != 0
}

// CWE-191: Signed integer overflow in loop bound
void overflow_loop(void) {
    signed char i;
    for (i = 0; i < 200; i++) {  // signed char max is 127, wraps
        printf("%d\n", i);
    }
}

int main(void) {
    integer_overflow_alloc();
    printf("%d\n", divide(10, 0));
    overflow_loop();
    return 0;
}
