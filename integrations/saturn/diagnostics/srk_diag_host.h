#ifndef SRK_DIAG_HOST_H
#define SRK_DIAG_HOST_H

/*
 * Title-neutral host boundary for the SRK Saturn diagnostics core.
 *
 * The standalone Saturn host will own SMPC/VDP/SCSP/timing directly. A later
 * injected host may obtain the same logical services differently. Core
 * diagnostics must not contain Saturn BIOS snapshot addresses or direct
 * cartridge/game assumptions.
 */

#ifdef __cplusplus
extern "C" {
#endif


typedef signed short   srk_s16;
typedef signed long    srk_s32;
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


typedef struct SRK_DIAG_VDP1_POINT {
    srk_s16 x;
    srk_s16 y;
} SRK_DIAG_VDP1_POINT;


typedef struct SRK_DIAG_VDP1_QUAD {
    SRK_DIAG_VDP1_POINT vertex[4];
    srk_u8 red;
    srk_u8 green;
    srk_u8 blue;
} SRK_DIAG_VDP1_QUAD;


#define SRK_DIAG_VDP1_MAX_QUADS 6


typedef struct SRK_DIAG_VDP1_SCENE {
    SRK_DIAG_VDP1_QUAD quad[SRK_DIAG_VDP1_MAX_QUADS];
    unsigned int count;
} SRK_DIAG_VDP1_SCENE;


typedef struct SRK_DIAG_VDP1_STATUS {
    srk_u16 edsr;
    srk_u16 lopr;
    srk_u16 copr;
    srk_u16 modr;
} SRK_DIAG_VDP1_STATUS;


/*
 * Title-neutral SCSP diagnostic request. Numeric tone/pan IDs belong to the
 * diagnostic contract, not to SCSP register encodings. The standalone host
 * translates them to waveform, pitch, mixer, and sound-CPU hardware state.
 */
typedef struct SRK_DIAG_AUDIO_REQUEST {
    unsigned int tone_id;
    unsigned int pan_id;
    unsigned int volume_level;
    int playing;
    int muted;
} SRK_DIAG_AUDIO_REQUEST;


typedef struct SRK_DIAG_AUDIO_STATUS {
    int initialized;
    srk_u16 common_control;
    srk_u16 slot_control;
    srk_u16 pitch;
    srk_u16 mixer;
} SRK_DIAG_AUDIO_STATUS;


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

    /*
     * VDP1 diagnostics submit logical geometry through the host boundary.
     * Command-table layout, registers, framebuffer state, and RGB encoding remain
     * host responsibilities so the reusable core contains no Saturn addresses.
     *
     * Stage 1 uses present_vdp1_quad. Stage 2 adds the bounded scene callback so
     * a title-neutral core can submit up to six already ordered cube faces while
     * retaining the physically proven single-quad path as a recovery reference.
     */
    int (*present_vdp1_quad)(void *context, const SRK_DIAG_VDP1_QUAD *quad);
    int (*present_vdp1_scene)(void *context, const SRK_DIAG_VDP1_SCENE *scene);
    void (*hide_vdp1)(void *context);
    int (*read_vdp1_status)(void *context, SRK_DIAG_VDP1_STATUS *status);

    /*
     * Audio diagnostics submit only logical state. Sound-RAM layout, SMPC sound
     * CPU lifecycle, SCSP slot registers, pitch encoding, and pan/send encoding
     * are standalone-host responsibilities.
     */
    int (*present_audio_tone)(void *context, const SRK_DIAG_AUDIO_REQUEST *request);
    void (*stop_audio)(void *context);
    int (*read_audio_status)(void *context, SRK_DIAG_AUDIO_STATUS *status);

    void (*end_frame)(void *context);

    /* Optional host observations for telemetry. */
    srk_u32 (*read_vbr)(void *context);
} SRK_DIAG_HOST;


#ifdef __cplusplus
}
#endif

#endif
