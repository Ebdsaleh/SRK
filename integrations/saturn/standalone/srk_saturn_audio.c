#include "srk_saturn_audio.h"


#define SRK_AUDIO_SMPC_COMREG (*(volatile srk_u8 *)0x2010001F)
#define SRK_AUDIO_SMPC_SF     (*(volatile srk_u8 *)0x20100063)
#define SRK_AUDIO_TVSTAT      (*(volatile srk_u16 *)0x25F80004)

#define SRK_AUDIO_SOUND_RAM   ((volatile srk_u16 *)0x25A00000)
#define SRK_AUDIO_SCSP_SLOT0  ((volatile srk_u16 *)0x25B00000)
#define SRK_AUDIO_SCSP_COMMON ((volatile srk_u16 *)0x25B00400)

#define SRK_AUDIO_SMPC_SNDON  0x06u
#define SRK_AUDIO_SMPC_SNDOFF 0x07u
#define SRK_AUDIO_SMPC_TIMEOUT 1000000ul

#define SRK_AUDIO_SLOT_WORDS 16u
#define SRK_AUDIO_SLOT_COUNT 32u
#define SRK_AUDIO_SLOT_CONTROL 0u
#define SRK_AUDIO_SLOT_SA_LOW  1u
#define SRK_AUDIO_SLOT_LSA     2u
#define SRK_AUDIO_SLOT_LEA     3u
#define SRK_AUDIO_SLOT_EG1     4u
#define SRK_AUDIO_SLOT_EG2     5u
#define SRK_AUDIO_SLOT_TL      6u
#define SRK_AUDIO_SLOT_FM      7u
#define SRK_AUDIO_SLOT_PITCH   8u
#define SRK_AUDIO_SLOT_LFO     9u
#define SRK_AUDIO_SLOT_DSP    10u
#define SRK_AUDIO_SLOT_MIXER  11u

#define SRK_AUDIO_CONTROL_KYONEX 0x1000u
#define SRK_AUDIO_CONTROL_KYONB  0x0800u
#define SRK_AUDIO_CONTROL_NORMAL_LOOP 0x0020u
#define SRK_AUDIO_SOUND_DIRECT 0x0100u

#define SRK_AUDIO_SOUND_CPU_STACK 0x0007FFF0ul
#define SRK_AUDIO_SOUND_CPU_PC    0x00000400ul
#define SRK_AUDIO_VECTOR_COUNT    256u
#define SRK_AUDIO_WAVE_ADDRESS    0x00002000u
#define SRK_AUDIO_LOOP_END        100u
#define SRK_AUDIO_SAMPLE_POSITIVE 0x2000u
#define SRK_AUDIO_SAMPLE_NEGATIVE 0xE000u

#define SRK_AUDIO_PAN_HARD_RIGHT 0x0Fu
#define SRK_AUDIO_PAN_CENTER     0x00u
#define SRK_AUDIO_PAN_HARD_LEFT  0x1Fu

#define SRK_AUDIO_PITCH_LOW  0x7800u
#define SRK_AUDIO_PITCH_MID  0x0000u
#define SRK_AUDIO_PITCH_HIGH 0x0800u


static int srk_saturn_audio_wait_smpc_ready(void)
{
    unsigned long remaining;

    remaining = SRK_AUDIO_SMPC_TIMEOUT;
    while(SRK_AUDIO_SMPC_SF & 0x01u){
        if(remaining == 0)
            return 0;
        remaining -= 1;
    }
    return 1;
}


static int srk_saturn_audio_smpc_command(srk_u8 command)
{
    if(!srk_saturn_audio_wait_smpc_ready())
        return 0;

    /* Sega SMPC Type-B flow: set SF, then write the command to COMREG. */
    SRK_AUDIO_SMPC_SF = 0x01u;
    SRK_AUDIO_SMPC_COMREG = command;
    return srk_saturn_audio_wait_smpc_ready();
}


static void srk_saturn_audio_wait_command_window(void)
{
    /*
     * The SMPC manual prohibits command issue for the first ~300 us after
     * V-BLANK-IN. The diagnostic shell calls us just after V-BLANK-IN, so wait
     * for V-BLANK-OUT before the one-time SNDON/SNDOFF initialization pair.
     */
    while(SRK_AUDIO_TVSTAT & 0x0008u)
        ;
}


static void srk_saturn_audio_write_sound_long(
    unsigned int byte_address,
    srk_u32 value
)
{
    unsigned int word_index;

    word_index = byte_address >> 1;
    SRK_AUDIO_SOUND_RAM[word_index] = (srk_u16)(value >> 16);
    SRK_AUDIO_SOUND_RAM[word_index + 1u] = (srk_u16)(value & 0xffffu);
}


static void srk_saturn_audio_install_dummy_cpu(void)
{
    unsigned int vector;

    /*
     * Technical Bulletin #51 requires the MC68EC000 to keep running even when
     * the main SH-2 owns sound control. Point every exception vector at one
     * bounded BRA.S loop, then override the reset SSP/PC vector pair.
     */
    for(vector=0; vector<SRK_AUDIO_VECTOR_COUNT; vector++)
        srk_saturn_audio_write_sound_long(vector * 4u, SRK_AUDIO_SOUND_CPU_PC);

    srk_saturn_audio_write_sound_long(0u, SRK_AUDIO_SOUND_CPU_STACK);
    srk_saturn_audio_write_sound_long(4u, SRK_AUDIO_SOUND_CPU_PC);
    SRK_AUDIO_SOUND_RAM[SRK_AUDIO_SOUND_CPU_PC >> 1] = 0x60FEu;
}


static void srk_saturn_audio_install_waveform(void)
{
    unsigned int sample;
    unsigned int base;

    base = SRK_AUDIO_WAVE_ADDRESS >> 1;
    for(sample=0; sample<50u; sample++)
        SRK_AUDIO_SOUND_RAM[base + sample] = SRK_AUDIO_SAMPLE_POSITIVE;
    for(sample=50u; sample<SRK_AUDIO_LOOP_END; sample++)
        SRK_AUDIO_SOUND_RAM[base + sample] = SRK_AUDIO_SAMPLE_NEGATIVE;

    /* Normal/reverse loop endpoints must contain matching sample data. */
    SRK_AUDIO_SOUND_RAM[base + SRK_AUDIO_LOOP_END] = SRK_AUDIO_SAMPLE_POSITIVE;
}


static void srk_saturn_audio_register_key_off_all(void)
{
    volatile srk_u16 *control;
    unsigned int slot;

    for(slot=0; slot<SRK_AUDIO_SLOT_COUNT; slot++){
        control = SRK_AUDIO_SCSP_SLOT0 + (slot * SRK_AUDIO_SLOT_WORDS);
        *control = (srk_u16)(*control & (srk_u16)~SRK_AUDIO_CONTROL_KYONB);
    }

    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] =
        SRK_AUDIO_CONTROL_NORMAL_LOOP | SRK_AUDIO_CONTROL_KYONEX;
}


static void srk_saturn_audio_configure_slot_zero(void)
{
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_SA_LOW] = SRK_AUDIO_WAVE_ADDRESS;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_LSA] = 0x0000u;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_LEA] = SRK_AUDIO_LOOP_END;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_EG1] = 0x0000u;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_EG2] = 0x0000u;
    /* SDIR bypasses EG/TL/LFO for the minimal Stage-1 direct-PCM proof. */
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_TL] = SRK_AUDIO_SOUND_DIRECT;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_FM] = 0x0000u;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_LFO] = 0x0000u;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_DSP] = 0x0000u;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
}


static int srk_saturn_audio_initialize(SRK_SATURN_HOST_STATE *state)
{
    if(!state)
        return 0;
    if(state->audio_initialized)
        return 1;

    srk_saturn_audio_wait_command_window();
    if(!srk_saturn_audio_smpc_command(SRK_AUDIO_SMPC_SNDOFF))
        return 0;

    /*
     * Main-side byte access to the sound block is prohibited. One word write
     * therefore sets MEM4MB=1, DAC18B=0, reserved/VER bits to zero, MVOL=0xF.
     */
    SRK_AUDIO_SCSP_COMMON[0] = 0x020Fu;

    srk_saturn_audio_install_dummy_cpu();
    srk_saturn_audio_install_waveform();
    srk_saturn_audio_register_key_off_all();
    srk_saturn_audio_configure_slot_zero();

    if(!srk_saturn_audio_smpc_command(SRK_AUDIO_SMPC_SNDON))
        return 0;

    state->audio_initialized = 1;
    state->audio_playing = 0;
    return 1;
}


static srk_u16 srk_saturn_audio_pitch(unsigned int tone_id)
{
    if(tone_id == 0u)
        return SRK_AUDIO_PITCH_LOW;
    if(tone_id == 2u)
        return SRK_AUDIO_PITCH_HIGH;
    return SRK_AUDIO_PITCH_MID;
}


static srk_u16 srk_saturn_audio_pan(unsigned int pan_id)
{
    if(pan_id == 0u)
        return SRK_AUDIO_PAN_HARD_LEFT;
    if(pan_id == 2u)
        return SRK_AUDIO_PAN_HARD_RIGHT;
    return SRK_AUDIO_PAN_CENTER;
}


static srk_u16 srk_saturn_audio_mixer(
    const SRK_DIAG_AUDIO_REQUEST *request
)
{
    unsigned int level;
    unsigned int pan;

    level = request->volume_level;
    if(level > 7u)
        level = 7u;
    if(request->muted || !request->playing)
        level = 0u;

    pan = srk_saturn_audio_pan(request->pan_id);
    return (srk_u16)((level << 13) | (pan << 8));
}


static void srk_saturn_audio_key_on(void)
{
    srk_u16 base;

    base = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] =
        (srk_u16)(base | SRK_AUDIO_CONTROL_KYONB);
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] =
        (srk_u16)(base | SRK_AUDIO_CONTROL_KYONB | SRK_AUDIO_CONTROL_KYONEX);
}


static void srk_saturn_audio_key_off(void)
{
    srk_u16 base;

    base = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] = base;
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] =
        (srk_u16)(base | SRK_AUDIO_CONTROL_KYONEX);
}


static int srk_saturn_audio_present(
    void *context,
    const SRK_DIAG_AUDIO_REQUEST *request
)
{
    SRK_SATURN_HOST_STATE *state;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !request)
        return 0;
    if(!srk_saturn_audio_initialize(state))
        return 0;

    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_PITCH] =
        srk_saturn_audio_pitch(request->tone_id);
    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_MIXER] =
        srk_saturn_audio_mixer(request);

    if(request->playing && !state->audio_playing){
        srk_saturn_audio_key_on();
        state->audio_playing = 1;
    }else if(!request->playing && state->audio_playing){
        srk_saturn_audio_key_off();
        state->audio_playing = 0;
    }

    return 1;
}


static void srk_saturn_audio_stop(void *context)
{
    SRK_SATURN_HOST_STATE *state;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !state->audio_initialized)
        return;

    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
    srk_saturn_audio_key_off();
    state->audio_playing = 0;

    /* Leave the bounded dummy 68000 loop running; do not leave Sound CPU OFF. */
}


static int srk_saturn_audio_read_status(
    void *context,
    SRK_DIAG_AUDIO_STATUS *status
)
{
    SRK_SATURN_HOST_STATE *state;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !status || !state->audio_initialized)
        return 0;

    status->initialized = 1;
    status->common_control = SRK_AUDIO_SCSP_COMMON[0];
    status->slot_control = SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL];
    status->pitch = SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_PITCH];
    status->mixer = SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_MIXER];
    return 1;
}


void srk_saturn_audio_bind(
    SRK_DIAG_HOST *host,
    SRK_SATURN_HOST_STATE *state
)
{
    if(!host || !state)
        return;

    state->audio_initialized = 0;
    state->audio_playing = 0;
    host->present_audio_tone = srk_saturn_audio_present;
    host->stop_audio = srk_saturn_audio_stop;
    host->read_audio_status = srk_saturn_audio_read_status;
}
