#include <stdio.h>

int *bad_pointer(void) {
    int local = 7;
    return &local;  // Intentional lifetime bug
}

int main(void) {
    int *p = bad_pointer();
    printf("%d\n", *p);
    return 0;
}
