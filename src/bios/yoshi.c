#include <stdio.h>
#include <generated/csr.h>

void yoshi_isr(void){
    printf("Hello\n");
    yoshi_ev_pending_write(1);
}
