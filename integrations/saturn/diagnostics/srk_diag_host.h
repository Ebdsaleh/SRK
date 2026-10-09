#ifndef SRK_DIAG_HOST_H
#define SRK_DIAG_HOST_H

/*
 * Title-neutral host boundary for the SRK Saturn diagnostics core.
 *
 * The standalone Saturn host will own SMPC/VDP/timing directly. A later
 * injected host may obtain the same logical services differently. Core
 * diagnostics must not contain Saturn BIOS snapshot addresses or direct
 * cartridge/game assumptions.
 */

#ifdef __cplusplus
extern "C" {
#endif


typedef unsigned char  srk_u8;
typedef unsigned short srk_u16;
typedef unsigned long  srk_u32;


typedef enum SRK_DIAG_BUTTON {
    SRK_DIAG_BUTTON_NONE  = 0x0000,
    SRK_DIAG_BUTTON_UP    = 0x0001,
    SRK_DIAG_BUTTON_DOWN  = 0x0002,
    SRK_DIAG_BUTTON_LEFT  = 0x0004,
    SRK_DIAG_BUTTON_RIGHT = 0x0008,
    SRK_DIAG_BUTTON_A     = 0x0010,
    SRK_DIAG_BUTTON_B     = 0x0020,
    SRK_DIAG_BUTTON_C     = 0x0040,
    SRK_DIAG_BUTTON_X     = 0x0080,
    SRK_DIAG_BUTTON_Y     = 0x0100,
    SRK_DIAG_BUTTON_Z     = 0x0200,
    SRK_DIAG_BUTTON_L     = 0x0400,
    SRK_DIAG_BUTTON_R     = 0x0800,
    SRK_DIAG_BUTTON_START = 0x1000
} SRK_DIAG_BUTTON;


typedef struct SRK_DIAG_PAD_SAMPLE {
    srk_u16 raw_state;
    srk_u16 buttons;
    int connected;
} SRK_DIAG_PAD_SAMPLE;


typedef struct SRK_DIAG_HOST {
    void *context;

    /* Monotonic microsecond-scale timer used for hold durations/telemetry. */
    srk_u32 (*time_us)(void *context);

    /*
     * Poll one controller port. raw_state is shown to the user unchanged;
     * buttons is the host-normalized SRK_DIAG_BUTTON mask.
     */
    int (*poll_pad)(void *context, unsigned int port, SRK_DIAG_PAD_SAMPLE *sample);

    /* Minimal presentation surface used by the diagnostic shell. */
    void (*begin_frame)(void *context);
    void (*clear)(void *context);
    void (*draw_text)(void *context, int x, int y, const char *text);

    /*
     * Draw one title-neutral video diagnostic pattern by stable numeric ID.
     * Pixel generation and hardware register access remain host responsibilities.
     */
    void (*draw_video_pattern)(void *context, unsigned int pattern_id);

    void (*end_frame)(void *context);

    /* Optional host observations for telemetry. */
    srk_u32 (*read_vbr)(void *context);
} SRK_DIAG_HOST;


#ifdef __cplusplus
}
#endif

#endif
