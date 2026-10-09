#ifndef SRK_SATURN_HOST_H
#define SRK_SATURN_HOST_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif


typedef struct SRK_SATURN_HOST_STATE {
    srk_u32 now_us;
    srk_u32 frame_period_us;
    int audio_initialized;
    int audio_playing;
    unsigned int audio_playing_mask;
    unsigned int audio_waveform_id;
    unsigned int audio_right_waveform_id;
} SRK_SATURN_HOST_STATE;


/*
 * Configure the standalone/master-mode Saturn host.
 *
 * This host owns the direct controller port and a minimal VDP2 bitmap text
 * surface. Device-specific helpers such as the SCSP backend bind through the
 * same host/context state while remaining separate source modules. A later
 * resident host can provide equivalent services without taking over a
 * commercial title's hardware state.
 */
void srk_saturn_host_init(
    SRK_DIAG_HOST *host,
    SRK_SATURN_HOST_STATE *state
);

#ifdef __cplusplus
}
#endif

#endif
