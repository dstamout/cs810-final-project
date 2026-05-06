#include <stdio.h>

int main(void) {
    int *p = NULL;
    if (p == NULL) {
        printf("Pointer is null\n");
    }
    *p = 42;  // Intentional null dereference
    return 0;
}
