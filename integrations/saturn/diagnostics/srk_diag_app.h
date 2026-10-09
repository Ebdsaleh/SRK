#ifndef SRK_DIAG_APP_H
#define SRK_DIAG_APP_H

#include "srk_diag_flight_recorder.h"
#include "srk_diag_input.h"
#include "srk_diag_menu.h"
#include "srk_diag_vdp1.h"
#include "srk_diag_video.h"

#ifdef __cplusplus
extern "C" {
#endif


typedef struct SRK_DIAG_APP {
    SRK_DIAG_MENU_STATE menu;
    SRK_DIAG_INPUT_STATE input;
    SRK_DIAG_FLIGHT_RECORDER recorder;
    SRK_DIAG_VIDEO_STATE video;
    SRK_DIAG_VDP1_STATE vdp1;
    srk_u32 frame;
    srk_u16 rendered_screen;
    int rendered_screen_valid;
} SRK_DIAG_APP;


void srk_diag_app_reset(SRK_DIAG_APP *app);
void srk_diag_app_frame(SRK_DIAG_APP *app, SRK_DIAG_HOST *host);

#ifdef __cplusplus
}
#endif

#endif
