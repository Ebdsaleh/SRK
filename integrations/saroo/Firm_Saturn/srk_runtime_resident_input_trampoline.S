	.text
	.align 2
	.global _srk_runtime_resident_input_proof_vector_entry

/*
 * Context-safe wrapper for the Saturn BIOS HBLANK-IN handler sequence patched
 * at 0x0600090c.  This is the input-proof counterpart of the physically proven
 * R8 resident trampoline.
 *
 * The BIOS has already saved r1-r5 before the patch site, while r0, r6 and r7
 * are still live.  Preserve those registers plus PR/GBR/MACH/MACL before calling
 * ordinary C.  Replay the displaced BIOS instructions exactly, mask interrupt
 * nesting only around the SRK callback, restore the post-displacement SR, and
 * resume the BIOS at 0x0600091a.
 */
_srk_runtime_resident_input_proof_vector_entry:
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

	mov.l	.Lsrk_input_tick,r1
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

	/* r1-r5 are restored by the BIOS after the continuation point. */
	mov.l	.Lbios_continue,r1
	ldc	r2,sr
	jmp	@r1
	nop

	.align 2
.Lsrk_input_tick:
	.long	_srk_runtime_resident_input_proof_tick
.Lbios_continue:
	.long	0x0600091a
