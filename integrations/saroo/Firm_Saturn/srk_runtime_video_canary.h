#ifndef SRK_RUNTIME_VIDEO_CANARY_H
#define SRK_RUNTIME_VIDEO_CANARY_H

#include "srk_runtime_video_state.h"

/*
 * Bounded visibility/restore experiment for the runtime-menu path.
 *
 * The canary owns no VRAM, CRAM, or VDP1 resources.  It temporarily changes
 * only the VDP2 color-offset register family already captured by
 * SRK_RUNTIME_VIDEO_STATE and restores that exact snapshot before returning.
 */
int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state);

#endif
