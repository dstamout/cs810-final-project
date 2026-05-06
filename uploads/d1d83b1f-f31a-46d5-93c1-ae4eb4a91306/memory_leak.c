#include <stdlib.h>
#include <string.h>

// CWE-401: Memory leak - malloc'd memory never freed
char *create_buffer(int size) {
    char *buf = (char *)malloc(size);
    if (buf == NULL) return NULL;
    memset(buf, 0, size);
    return buf;  // caller may forget to free
}

void leak_on_error(int flag) {
    char *data = (char *)malloc(256);
    if (flag) {
        return;  // leaked: forgot to free before early return
    }
    free(data);
}

int main(void) {
    char *p = (char *)malloc(64);
    // p is never freed before main exits
    return 0;
}
