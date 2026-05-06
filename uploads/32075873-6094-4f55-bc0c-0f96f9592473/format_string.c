#include <stdio.h>
#include <string.h>

// CWE-134: Uncontrolled format string
void log_message(char *user_input) {
    printf(user_input);   // format string vulnerability: attacker controls format
}

// CWE-120: Buffer copy without size check (strcpy)
void unsafe_copy(char *src) {
    char dest[16];
    strcpy(dest, src);    // no bounds check: classic buffer overflow
}

// CWE-676: Use of potentially dangerous function (gets)
void read_input(void) {
    char buf[32];
    gets(buf);            // gets() has no length limit, always unsafe
}

int main(void) {
    log_message("hello\n");
    unsafe_copy("this string is definitely longer than sixteen bytes");
    return 0;
}
