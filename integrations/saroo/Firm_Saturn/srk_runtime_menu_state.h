#ifndef SRK_RUNTIME_MENU_STATE_H
#define SRK_RUNTIME_MENU_STATE_H

/*
 * Title-neutral runtime-menu state machine.
 *
 * This layer owns only menu lifecycle/input state. It performs no rendering,
 * no SMPC I/O, no RAM capture, and no SD-card I/O.
 */

#define SRK_RUNTIME_MENU_EVENT_NONE     0
#define SRK_RUNTIME_MENU_EVENT_OPENED   1
#define SRK_RUNTIME_MENU_EVENT_RESUMED  2

typedef struct {
    int active;
    int input_armed;
    unsigned int previous_buttons;
} SRK_RUNTIME_MENU_STATE;

void srk_runtime_menu_state_reset(SRK_RUNTIME_MENU_STATE *state);
int srk_runtime_menu_request_open(SRK_RUNTIME_MENU_STATE *state);
int srk_runtime_menu_state_sample(
    SRK_RUNTIME_MENU_STATE *state,
    unsigned int buttons
);

#endif
