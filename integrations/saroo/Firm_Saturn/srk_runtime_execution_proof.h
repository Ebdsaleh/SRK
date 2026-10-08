#ifndef SRK_RUNTIME_EXECUTION_PROOF_H
#define SRK_RUNTIME_EXECUTION_PROOF_H

/*
 * Title-neutral proof that SRK continues receiving the existing SAROO BIOS
 * controller callback after a game reaches its IP.BIN 1st-read entry point.
 *
 * This diagnostic deliberately does not depend on controller input.  It is
 * armed from the SAROO menu, gates itself on the already-proven one-shot UBR
 * entry mechanism, then waits for a bounded number of later cdp_hook calls.
 */
#define SRK_RUNTIME_EXECUTION_PROOF_OK             0
#define SRK_RUNTIME_EXECUTION_PROOF_ERR_FIRST_READ -1

int srk_runtime_execution_proof_arm(void);
int srk_runtime_execution_proof_prepare(void);
void srk_runtime_execution_proof_on_controller_hook(void);

#endif
