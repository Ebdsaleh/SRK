#ifndef SRK_RUNTIME_MODAL_RED_H
#define SRK_RUNTIME_MODAL_RED_H

#include "srk_runtime_input.h"
#include "srk_runtime_menu_state.h"
#include "srk_runtime_video_state.h"

/*
 * First modal runtime-shell experiment.
 *
 * The calling controller hook remains on the stack while this helper owns the
 * screen.  The title's main execution path therefore does not advance.  The
 * existing BIOS controller routine is invoked once per display frame so the
 * same release-gated L+R detector can dismiss the modal state.
 */
typedef void (*SRK_RUNTIME_CONTROLLER_REFRESH)(void);

#define SRK_RUNTIME_MODAL_RED_DISMISSED  1
#define SRK_RUNTIME_MODAL_RED_TIMEOUT    2
#define SRK_RUNTIME_MODAL_RED_FAILED     0

int srk_runtime_modal_red_run(
    SRK_RUNTIME_INPUT_STATE *input_state,
    SRK_RUNTIME_MENU_STATE *menu_state,
    const SRK_RUNTIME_VIDEO_STATE *video_state,
    SRK_RUNTIME_CONTROLLER_REFRESH refresh_controller,
    volatile unsigned short *controller_buttons
);

#endif
