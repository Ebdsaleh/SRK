#ifndef SRK_RUNTIME_RESIDENT_INPUT_PROOF_H
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_H

/*
 * R9 persistent proof that the physically validated resident trampoline can
 * remain active after title launch and observe an explicit L+R hold from the
 * Saturn BIOS controller-1 memory snapshot.
 *
 * Runtime sampling is rate-limited with SAROO's 1 MHz SS_TIMER so HBLANK-IN
 * callback frequency cannot make the hold detector fire artificially fast.
 */
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_OK                 0
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_ARM_WRITE     -1
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_VECTOR        -2
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_INSTALL_WRITE -3

#define SRK_RUNTIME_RESIDENT_INPUT_SAMPLE_US    20000u
#define SRK_RUNTIME_RESIDENT_INPUT_HOLD_SAMPLES 50u

int srk_runtime_resident_input_proof_arm(void);
int srk_runtime_resident_input_proof_install(void);
void srk_runtime_resident_input_proof_tick(void);
void srk_runtime_resident_input_proof_vector_entry(void);

#endif
