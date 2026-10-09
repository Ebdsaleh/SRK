#include "srk_diag_video.h"


static const char *srk_diag_video_labels[SRK_DIAG_VIDEO_PATTERN_COUNT] = {
    "Solid Black",
    "Solid White",
    "Solid Red",
    "Solid Green",
    "Solid Blue",
    "RGB / Color Bars",
    "Grayscale / Brightness Ramp",
    "Checkerboard",
    "Fine Grid",
    "Overscan / Safe Area"
};


void srk_diag_video_reset(SRK_DIAG_VIDEO_STATE *state)
{
    if(!state)
        return;
    state->pattern = SRK_DIAG_VIDEO_SOLID_BLACK;
}


void srk_diag_video_move(SRK_DIAG_VIDEO_STATE *state, int delta)
{
    int next;

    if(!state || delta == 0)
        return;

    next = (int)state->pattern + delta;
    while(next < 0)
        next += SRK_DIAG_VIDEO_PATTERN_COUNT;
    while(next >= SRK_DIAG_VIDEO_PATTERN_COUNT)
        next -= SRK_DIAG_VIDEO_PATTERN_COUNT;

    state->pattern = (SRK_DIAG_VIDEO_PATTERN)next;
}


const char *srk_diag_video_label(SRK_DIAG_VIDEO_PATTERN pattern)
{
    int index;

    index = (int)pattern;
    if(index < 0 || index >= SRK_DIAG_VIDEO_PATTERN_COUNT)
        return "Unknown Pattern";
    return srk_diag_video_labels[index];
}
