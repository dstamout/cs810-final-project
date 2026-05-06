#include <stdio.h>
#include <string.h>

int main(void) {
    char small[8];
    const char *input = "this_string_is_too_long";
    strcpy(small, input);  // Intentional overflow
    printf("%s\n", small);
    return 0;
}
