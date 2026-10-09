#ifndef SRK_DIAG_VIDEO_H
#define SRK_DIAG_VIDEO_H

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_VIDEO_PATTERN_COUNT 10


typedef enum SRK_DIAG_VIDEO_PATTERN {
    SRK_DIAG_VIDEO_SOLID_BLACK = 0,
    SRK_DIAG_VIDEO_SOLID_WHITE = 1,
    SRK_DIAG_VIDEO_SOLID_RED = 2,
    SRK_DIAG_VIDEO_SOLID_GREEN = 3,
    SRK_DIAG_VIDEO_SOLID_BLUE = 4,
    SRK_DIAG_VIDEO_COLOR_BARS = 5,
    SRK_DIAG_VIDEO_GRAYSCALE_RAMP = 6,
    SRK_DIAG_VIDEO_CHECKERBOARD = 7,
    SRK_DIAG_VIDEO_FINE_GRID = 8,
    SRK_DIAG_VIDEO_SAFE_AREA = 9
} SRK_DIAG_VIDEO_PATTERN;


typedef struct SRK_DIAG_VIDEO_STATE {
    SRK_DIAG_VIDEO_PATTERN pattern;
} SRK_DIAG_VIDEO_STATE;


void srk_diag_video_reset(SRK_DIAG_VIDEO_STATE *state);
void srk_diag_video_move(SRK_DIAG_VIDEO_STATE *state, int delta);
const char *srk_diag_video_label(SRK_DIAG_VIDEO_PATTERN pattern);

#ifdef __cplusplus
}
#endif

#endif
