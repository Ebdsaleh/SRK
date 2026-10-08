#ifndef SRK_RUNTIME_RESIDENT_PROOF_H
#define SRK_RUNTIME_RESIDENT_PROOF_H

/*
 * Persistent proof that SRK can regain execution from the Saturn BIOS interrupt
 * trampoline used by SAROO's own cheat-style runtime hook.
 *
 * The proof is armed from the SAROO menu, installed after the title's 1ST_READ
 * has been loaded, and writes one fixed-size proof slot only after 600 runtime
 * trampoline callbacks.  It does not depend on controller input or VDP output.
 */
#define SRK_RUNTIME_RESIDENT_PROOF_OK                 0
#define SRK_RUNTIME_RESIDENT_PROOF_ERR_ARM_WRITE     -1
#define SRK_RUNTIME_RESIDENT_PROOF_ERR_VECTOR        -2
#define SRK_RUNTIME_RESIDENT_PROOF_ERR_INSTALL_WRITE -3

#define SRK_RUNTIME_RESIDENT_PROOF_CALLBACKS 600u

int srk_runtime_resident_proof_arm(void);
int srk_runtime_resident_proof_install(void);
void srk_runtime_resident_proof_tick(void);
void srk_runtime_resident_proof_vector_entry(void);

#endif
