#include "srk_diag_menu.h"


static const char *srk_diag_menu_labels[SRK_DIAG_MENU_ITEM_COUNT] = {
    "Controller / Input Test",
    "Video Pattern Test",
    "VDP1 / 3D Test",
    "Audio / SCSP Test",
    "Timing / Interrupt Test",
    "Memory / Dump Tools",
    "Flight Recorder",
    "System Information"
};


void srk_diag_menu_reset(SRK_DIAG_MENU_STATE *state)
{
    if(!state)
        return;

    state->selection = 0;
    state->active = 0;
    state->active_screen = SRK_DIAG_SCREEN_INPUT_TEST;
}


void srk_diag_menu_move(SRK_DIAG_MENU_STATE *state, int delta)
{
    int next;

    if(!state || state->active || !delta)
        return;

    next = state->selection + delta;
    if(next < 0)
        next = 0;
    if(next >= SRK_DIAG_MENU_ITEM_COUNT)
        next = SRK_DIAG_MENU_ITEM_COUNT - 1;

    state->selection = next;
}


void srk_diag_menu_enter(SRK_DIAG_MENU_STATE *state)
{
    if(!state || state->active)
        return;

    state->active_screen = (SRK_DIAG_SCREEN)state->selection;
    state->active = 1;
}


void srk_diag_menu_back(SRK_DIAG_MENU_STATE *state)
{
    if(!state)
        return;

    state->active = 0;
}


const char *srk_diag_menu_label(int index)
{
    if(index < 0 || index >= SRK_DIAG_MENU_ITEM_COUNT)
        return 0;
    return srk_diag_menu_labels[index];
}
