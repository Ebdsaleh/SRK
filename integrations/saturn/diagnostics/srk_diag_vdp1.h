#ifndef SRK_DIAG_VDP1_H
#define SRK_DIAG_VDP1_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif


#define SRK_DIAG_VDP1_CUBE_VERTEX_COUNT 8
#define SRK_DIAG_VDP1_CUBE_FACE_COUNT   6

#define SRK_DIAG_VDP1_MOTION_SHIFT      8
#define SRK_DIAG_VDP1_SPEED_ONE         256
#define SRK_DIAG_VDP1_SPEED_MAX         1024
#define SRK_DIAG_VDP1_VELOCITY_MAX      1536


typedef enum SRK_DIAG_VDP1_PALETTE {
    SRK_DIAG_VDP1_PALETTE_ORIGINAL = 0,
    SRK_DIAG_VDP1_PALETTE_PASTEL,
    SRK_DIAG_VDP1_PALETTE_NEON,
    SRK_DIAG_VDP1_PALETTE_COUNT
} SRK_DIAG_VDP1_PALETTE;


typedef struct SRK_DIAG_VDP1_STATE {
    /* Physically proven R7 Stage 1 reference primitive. */
    SRK_DIAG_VDP1_QUAD quad;

    /* Stage 2/3 projected and far-to-near ordered cube faces. */
    SRK_DIAG_VDP1_SCENE scene;
    srk_u16 angle_x;
    srk_u16 angle_y;
    srk_u16 angle_z;
    srk_u32 angle_accum_x;
    srk_u32 angle_accum_y;
    srk_u32 angle_accum_z;
    srk_s16 velocity_x;
    srk_s16 velocity_y;
    srk_s16 velocity_z;
    srk_u16 speed_q8;
    srk_u16 visible_face_count;
    SRK_DIAG_VDP1_PALETTE palette;
    int frozen;
    srk_u32 animation_frame;

    srk_u32 submit_count;
    int submitted;
} SRK_DIAG_VDP1_STATE;


void srk_diag_vdp1_reset(SRK_DIAG_VDP1_STATE *state);
void srk_diag_vdp1_control(
    SRK_DIAG_VDP1_STATE *state,
    srk_u16 held_buttons,
    srk_u16 pressed_buttons
);
void srk_diag_vdp1_advance(SRK_DIAG_VDP1_STATE *state);
const char *srk_diag_vdp1_palette_label(SRK_DIAG_VDP1_PALETTE palette);
void srk_diag_vdp1_mark_submitted(SRK_DIAG_VDP1_STATE *state, int submitted);


#ifdef __cplusplus
}
#endif

#endif
