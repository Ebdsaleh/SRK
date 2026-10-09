#ifndef SRK_DIAG_VDP1_H
#define SRK_DIAG_VDP1_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif


typedef struct SRK_DIAG_VDP1_STATE {
    SRK_DIAG_VDP1_QUAD quad;
    srk_u32 submit_count;
    int submitted;
} SRK_DIAG_VDP1_STATE;


void srk_diag_vdp1_reset(SRK_DIAG_VDP1_STATE *state);
void srk_diag_vdp1_mark_submitted(SRK_DIAG_VDP1_STATE *state, int submitted);


#ifdef __cplusplus
}
#endif

#endif
