#include "srk_diag_app.h"
#include "srk_saturn_audio.h"
#include "srk_saturn_host.h"

#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || \
    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)
#include "srk_saturn_midi_68k_physical_proof.h"
#endif


static SRK_DIAG_APP srk_app;
static SRK_DIAG_HOST srk_host;
static SRK_SATURN_HOST_STATE srk_host_state;

#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || \
    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)

#ifdef SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE
typedef SRK_SATURN_MIDI_68K_SILENT_BATCH_PHYSICAL_PROOF_STATE
    SRK_MIDI_68K_ACTIVE_PROOF_STATE;
#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u
#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K BATCH PROOF"
#define SRK_MIDI_68K_PROOF_SUBTITLE "27 records - no MIDI SCSP note"
#define SRK_MIDI_68K_PROOF_SUCCESS "Success: sequence=1 index=27 error=0"
#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_silent_batch_physical_proof_reset
#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_silent_batch_physical_proof_begin
#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_silent_batch_physical_proof_poll
#else
typedef SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE SRK_MIDI_68K_ACTIVE_PROOF_STATE;
#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 1u
#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K SILENT PROOF"
#define SRK_MIDI_68K_PROOF_SUBTITLE "Protocol only - no MIDI SCSP note"
#define SRK_MIDI_68K_PROOF_SUCCESS "Success: sequence=1 index=1 error=0"
#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_physical_proof_reset
#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_physical_proof_begin
#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_physical_proof_poll
#endif

static SRK_MIDI_68K_ACTIVE_PROOF_STATE srk_midi_68k_proof;
static int srk_midi_68k_proof_screen_armed;


static void srk_midi_68k_u32(char out[11], srk_u32 value)
{
    char reversed[10];
    int count;
    int i;

    if(value == 0u){
        out[0] = '0';
        out[1] = '\0';
        return;
    }

    count = 0;
    while(value && count < 10){
        reversed[count++] = (char)('0' + (value % 10u));
        value /= 10u;
    }

    for(i=0; i<count; i++)
        out[i] = reversed[count - i - 1];
    out[count] = '\0';
}


static void srk_midi_68k_hex16(char out[7], srk_u16 value)
{
    static const char digits[] = "0123456789ABCDEF";

    out[0] = '0';
    out[1] = 'x';
    out[2] = digits[(value >> 12) & 0x0fu];
    out[3] = digits[(value >> 8) & 0x0fu];
    out[4] = digits[(value >> 4) & 0x0fu];
    out[5] = digits[value & 0x0fu];
    out[6] = '\0';
}


static void srk_midi_68k_draw_field(
    int x,
    int y,
    int width,
    const char *text
)
{
    char field[41];
    int i;

    if(!srk_host.draw_text || width < 1)
        return;
    if(width > 40)
        width = 40;

    for(i=0; i<width; i++)
        field[i] = ' ';
    field[width] = '\0';

    if(text){
        for(i=0; i<width && text[i]; i++)
            field[i] = text[i];
    }

    srk_host.draw_text(srk_host.context, x, y, field);
}


static const char *srk_midi_68k_status_label(unsigned int status)
{
    switch(status){
    case SRK_MIDI_68K_RUNTIME_NOT_STARTED:
        return "NOT STARTED";
    case SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED:
        return "SNDOFF FAIL";
    case SRK_MIDI_68K_RUNTIME_INSTALL_FAILED:
        return "INSTALL FAIL";
    case SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED:
        return "PRELOAD FAIL";
    case SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED:
        return "SNDON FAIL";
    case SRK_MIDI_68K_RUNTIME_RUNNING:
        return "RUNNING";
    case SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED:
        return "ACKNOWLEDGED";
    case SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR:
        return "68K ERROR";
    default:
        return "UNKNOWN";
    }
}


static const char *srk_midi_68k_boundary_label(void)
{
    if(!srk_midi_68k_proof.attempted)
        return "NOT RUN";

    if(srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED &&
       srk_midi_68k_proof.telemetry.read_sequence == 1u &&
       srk_midi_68k_proof.telemetry.read_index == SRK_MIDI_68K_PROOF_EXPECTED_INDEX &&
       srk_midi_68k_proof.telemetry.last_error == 0u){
        return "PASS";
    }

    if(srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED ||
       srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_INSTALL_FAILED ||
       srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED ||
       srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED ||
       srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR){
        return "FAIL";
    }

    return "PENDING";
}


static void srk_midi_68k_render_proof(void)
{
    char number[11];
    char flags[7];

    srk_midi_68k_draw_field(2, 1, 36, SRK_MIDI_68K_PROOF_TITLE);
    srk_midi_68k_draw_field(2, 2, 36, SRK_MIDI_68K_PROOF_SUBTITLE);

    srk_midi_68k_draw_field(2, 4, 14, "Status:");
    srk_midi_68k_draw_field(
        16,
        4,
        20,
        srk_midi_68k_status_label(srk_midi_68k_proof.runtime_status)
    );

    srk_midi_68k_draw_field(2, 5, 14, "Boundary:");
    srk_midi_68k_draw_field(16, 5, 20, srk_midi_68k_boundary_label());

    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.poll_count);
    srk_midi_68k_draw_field(2, 7, 14, "Polls:");
    srk_midi_68k_draw_field(16, 7, 10, number);

    srk_midi_68k_hex16(flags, srk_midi_68k_proof.telemetry.flags);
    srk_midi_68k_draw_field(2, 8, 14, "Flags:");
    srk_midi_68k_draw_field(16, 8, 10, flags);

    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_sequence);
    srk_midi_68k_draw_field(2, 9, 14, "Read sequence:");
    srk_midi_68k_draw_field(16, 9, 10, number);

    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_index);
    srk_midi_68k_draw_field(2, 10, 14, "Read index:");
    srk_midi_68k_draw_field(16, 10, 10, number);

    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);
    srk_midi_68k_draw_field(2, 11, 14, "Last error:");
    srk_midi_68k_draw_field(16, 11, 10, number);

    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);
    if(srk_midi_68k_proof_screen_armed){
        if(srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_RUNNING)
            srk_midi_68k_draw_field(2, 17, 36, "A ignored while proof is RUNNING");
        else if(srk_midi_68k_proof.attempted)
            srk_midi_68k_draw_field(2, 17, 36, "A Run again (explicit reset + begin)");
        else
            srk_midi_68k_draw_field(2, 17, 36, "A Run explicit silent proof");
    }else{
        srk_midi_68k_draw_field(2, 17, 36, "Release A to arm proof action");
    }
    srk_midi_68k_draw_field(2, 19, 36, "START Return to diagnostics menu");
}


static void srk_midi_68k_candidate_frame(void)
{
    int proof_screen;

    proof_screen =
        srk_app.menu.active &&
        srk_app.menu.active_screen == SRK_DIAG_SCREEN_TIMING_INTERRUPT_TEST;

    if(!proof_screen){
        srk_midi_68k_proof_screen_armed = 0;
        return;
    }

    if(srk_midi_68k_proof.attempted &&
       srk_midi_68k_proof.runtime_status == SRK_MIDI_68K_RUNTIME_RUNNING){
        (void)SRK_MIDI_68K_PROOF_POLL(&srk_midi_68k_proof);
    }

    if(!srk_midi_68k_proof_screen_armed){
        if((srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u)
            srk_midi_68k_proof_screen_armed = 1;
    }else if((srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u &&
             srk_midi_68k_proof.runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING){
        SRK_MIDI_68K_PROOF_RESET(&srk_midi_68k_proof);
        (void)SRK_MIDI_68K_PROOF_BEGIN(&srk_midi_68k_proof);
    }

    srk_midi_68k_render_proof();
}
#endif


/*
 * The reviewed GNUSH Saturn startup convention calls C function `_main`, whose
 * external symbol is `__main` for the historical SH-ELF toolchain.
 */
void _main(void)
{
    srk_saturn_host_init(&srk_host, &srk_host_state);
    srk_saturn_audio_bind(&srk_host, &srk_host_state);
    srk_diag_app_reset(&srk_app);

#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || \
    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)
    SRK_MIDI_68K_PROOF_RESET(&srk_midi_68k_proof);
    srk_midi_68k_proof_screen_armed = 0;
#endif

    for(;;){
        srk_diag_app_frame(&srk_app, &srk_host);
#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || \
    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)
        srk_midi_68k_candidate_frame();
#endif
    }
}
