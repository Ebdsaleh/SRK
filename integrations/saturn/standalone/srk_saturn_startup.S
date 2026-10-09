!
! SRK standalone Sega Saturn startup.
!
! The reviewed local vdp1ex scaffold loads the first-read binary at 0x06004000,
! reserves 0x06002000-0x06003FFF for the downward-growing stack, and calls the
! SH-GCC external symbol __main.  SRK keeps that proven entry contract but does
! not inherit the historical Action Replay return path.
!

.section .text
.global start
start:
    ! Clear BSS: [__bss_start, __bss_end)
    mov.l   bss_start,r0
    mov.l   bss_end,r1
    mov     #0,r2
clear_bss:
    cmp/hs  r1,r0
    bt      clear_bss_done
    mov.b   r2,@r0
    add     #1,r0
    bra     clear_bss
    nop
clear_bss_done:

    ! Stack grows down through 0x06002000-0x06003FFF.
    mov.l   stack_ptr,r15

    ! Enter SRK's C master-mode loop.
    mov.l   main_ptr,r0
    jsr     @r0
    nop

    ! The standalone diagnostics loop is not expected to return.  If it does,
    ! mask interrupts and remain in a bounded terminal loop rather than jumping
    ! to a cartridge-specific address.
    mov     #0xf,r0
    shll2   r0
    shll2   r0
    ldc     r0,sr
halt:
    bra     halt
    nop

.align 2
main_ptr:   .long __main
stack_ptr:  .long 0x06004000
bss_start:  .long __bss_start
bss_end:    .long __bss_end
