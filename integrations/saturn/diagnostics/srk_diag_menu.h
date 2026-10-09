#ifndef SRK_DIAG_MENU_H
#define SRK_DIAG_MENU_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_MENU_ITEM_COUNT 8


typedef enum SRK_DIAG_SCREEN {
    SRK_DIAG_SCREEN_INPUT_TEST = 0,
    SRK_DIAG_SCREEN_VIDEO_PATTERN_TEST = 1,
    SRK_DIAG_SCREEN_VDP1_3D_TEST = 2,
    SRK_DIAG_SCREEN_AUDIO_TEST = 3,
    SRK_DIAG_SCREEN_TIMING_INTERRUPT_TEST = 4,
    SRK_DIAG_SCREEN_MEMORY_DUMP_TOOLS = 5,
    SRK_DIAG_SCREEN_FLIGHT_RECORDER = 6,
    SRK_DIAG_SCREEN_SYSTEM_INFORMATION = 7
} SRK_DIAG_SCREEN;


typedef struct SRK_DIAG_MENU_STATE {
    int selection;
    int active;
    SRK_DIAG_SCREEN active_screen;
} SRK_DIAG_MENU_STATE;


void srk_diag_menu_reset(SRK_DIAG_MENU_STATE *state);
void srk_diag_menu_move(SRK_DIAG_MENU_STATE *state, int delta);
void srk_diag_menu_enter(SRK_DIAG_MENU_STATE *state);
void srk_diag_menu_back(SRK_DIAG_MENU_STATE *state);
const char *srk_diag_menu_label(int index);

#ifdef __cplusplus
}
#endif

#endif
