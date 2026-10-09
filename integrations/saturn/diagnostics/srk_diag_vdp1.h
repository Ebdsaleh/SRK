#ifndef SRK_DIAG_VDP1_H
#define SRK_DIAG_VDP1_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif


#define SRK_DIAG_VDP1_CUBE_VERTEX_COUNT 8
#define SRK_DIAG_VDP1_CUBE_FACE_COUNT   6


typedef struct SRK_DIAG_VDP1_STATE {
    /* Physically proven R7 Stage 1 reference primitive. */
    SRK_DIAG_VDP1_QUAD quad;

    /* Stage 2 projected and far-to-near ordered cube faces. */
    SRK_DIAG_VDP1_SCENE scene;
    srk_u16 angle_x;
    srk_u16 angle_y;
    srk_u16 angle_z;
    srk_u16 visible_face_count;
    srk_u32 animation_frame;

    srk_u32 submit_count;
    int submitted;
} SRK_DIAG_VDP1_STATE;


void srk_diag_vdp1_reset(SRK_DIAG_VDP1_STATE *state);
void srk_diag_vdp1_advance(SRK_DIAG_VDP1_STATE *state);
void srk_diag_vdp1_mark_submitted(SRK_DIAG_VDP1_STATE *state, int submitted);


#ifdef __cplusplus
}
#endif

#endif
