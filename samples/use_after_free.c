#include <stdlib.h>
#include <stdio.h>

// CWE-416: Use after free
void use_after_free_example(void) {
    int *p = (int *)malloc(sizeof(int));
    *p = 42;
    free(p);
    printf("%d\n", *p);  // use after free: undefined behavior
}

// CWE-415: Double free
void double_free_example(int condition) {
    char *buf = (char *)malloc(128);
    if (condition) {
        free(buf);
    }
    free(buf);  // double free if condition was true
}

int main(void) {
    use_after_free_example();
    double_free_example(1);
    return 0;
}
