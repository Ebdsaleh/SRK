#ifndef SRK_RUNTIME_VIDEO_CANARY_H
#define SRK_RUNTIME_VIDEO_CANARY_H

#include "srk_runtime_video_state.h"

/*
 * Visibility/restore experiments for the runtime-menu path.
 *
 * These helpers own no VRAM, CRAM, or VDP1 resources. They temporarily change
 * only the VDP2 color-offset register family already captured by
 * SRK_RUNTIME_VIDEO_STATE and restore that exact snapshot before title control
 * resumes.
 */
int srk_runtime_video_canary_apply_solid_red(
    const SRK_RUNTIME_VIDEO_STATE *state
);
int srk_runtime_video_canary_restore(
    const SRK_RUNTIME_VIDEO_STATE *state
);
int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state);

#endif
