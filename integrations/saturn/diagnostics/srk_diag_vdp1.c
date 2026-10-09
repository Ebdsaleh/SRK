#include "srk_diag_vdp1.h"


void srk_diag_vdp1_reset(SRK_DIAG_VDP1_STATE *state)
{
    if(!state)
        return;

    /* Keep the primitive below the raw-status rows and above the footer text. */
    state->quad.vertex[0].x = 96;
    state->quad.vertex[0].y = 104;
    state->quad.vertex[1].x = 224;
    state->quad.vertex[1].y = 112;
    state->quad.vertex[2].x = 208;
    state->quad.vertex[2].y = 176;
    state->quad.vertex[3].x = 112;
    state->quad.vertex[3].y = 168;

    state->quad.red = 255;
    state->quad.green = 64;
    state->quad.blue = 32;
    state->submit_count = 0;
    state->submitted = 0;
}


void srk_diag_vdp1_mark_submitted(SRK_DIAG_VDP1_STATE *state, int submitted)
{
    if(!state)
        return;

    state->submitted = submitted ? 1 : 0;
    if(state->submitted)
        state->submit_count += 1;
}
