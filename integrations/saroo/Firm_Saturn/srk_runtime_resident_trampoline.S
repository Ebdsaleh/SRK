	.text
	.align 2
	.global _srk_runtime_resident_proof_vector_entry

/*
 * Context-safe wrapper for the Saturn BIOS SCU interrupt handler sequence
 * patched at 0x0600090c.
 *
 * The original BIOS has already saved r1-r5 before the patch site, but r0 is
 * still the interrupt-vector index and r6/r7 are not saved until 0x0600091c
 * and 0x06000920.  A normal C callback may freely clobber r0-r7, so preserve
 * the still-live registers here before entering C.
 *
 * PR, GBR, MACH and MACL are also preserved explicitly so the callback cannot
 * leak C-library/compiler state into the interrupted title.  After replaying
 * the displaced BIOS instructions, interrupts are masked while the SRK
 * callback runs.  The exact post-displacement SR is restored before control
 * returns to the BIOS continuation at 0x0600091a.
 */
_srk_runtime_resident_proof_vector_entry:
	sts.l	pr,@-r15
	mov.l	r0,@-r15
	mov.l	r6,@-r15
	mov.l	r7,@-r15
	sts.l	mach,@-r15
	sts.l	macl,@-r15
	stc.l	gbr,@-r15

	/* Replay BIOS instructions displaced from 0x0600090c..0x06000918. */
	mov	r3,r4
	shlr16	r3
	ldc	r3,sr
	exts.w	r4,r4
	or	r4,r2
	mov.l	r2,@r1
	mov.l	r2,@r5

	/* Save the BIOS-selected SR, then block nesting while SRK runs. */
	stc	sr,r0
	mov.l	r0,@-r15
	or	#0xf0,r0
	ldc	r0,sr

	mov.l	.Lsrk_tick,r1
	jsr	@r1
	nop

	/* Keep interrupts masked while restoring the live interrupt context. */
	mov.l	@r15+,r2
	ldc.l	@r15+,gbr
	lds.l	@r15+,macl
	lds.l	@r15+,mach
	mov.l	@r15+,r7
	mov.l	@r15+,r6
	mov.l	@r15+,r0
	lds.l	@r15+,pr

	/*
	 * r1-r5 were already saved by the BIOS before the patch site.  r1 is safe
	 * to reuse for the continuation address, and r2 is safe to hold the saved
	 * post-displacement SR because the BIOS later restores the interrupted r2.
	 */
	mov.l	.Lbios_continue,r1
	ldc	r2,sr
	jmp	@r1
	nop

	.align 2
.Lsrk_tick:
	.long	_srk_runtime_resident_proof_tick
.Lbios_continue:
	.long	0x0600091a
