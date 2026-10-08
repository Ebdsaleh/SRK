#ifndef SRK_RUNTIME_INPUT_H
#define SRK_RUNTIME_INPUT_H

/*
 * SRK title-neutral runtime input detector.
 *
 * The detector consumes completed Saturn controller samples.  It does not
 * perform SMPC I/O itself, write files, capture memory, or modify title state.
 * Integration code decides where completed samples come from and what to do
 * with emitted events.
 */

#define SRK_RUNTIME_INPUT_HOLD_SAMPLES 50u

#define SRK_RUNTIME_INPUT_NONE       0
#define SRK_RUNTIME_INPUT_OPEN_MENU  1

typedef struct {
    unsigned int hold_samples;
    int latched;
} SRK_RUNTIME_INPUT_STATE;

void srk_runtime_input_reset(SRK_RUNTIME_INPUT_STATE *state);
int srk_runtime_input_sample(
    SRK_RUNTIME_INPUT_STATE *state,
    unsigned int buttons
);

#endif
