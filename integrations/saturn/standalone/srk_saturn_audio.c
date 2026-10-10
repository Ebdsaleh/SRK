#include "srk_saturn_audio.h"
#include "srk_saturn_packaged_pcm.h"


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

#define SRK_AUDIO_STAGE4_SAMPLE_ADDRESS 0x00002400u
#define SRK_AUDIO_STAGE4_SAMPLE_LOOP_END 256u
#define SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID 0u
#define SRK_AUDIO_STAGE4_WAVEFORM_SHAPED_PCM_ID 1u
#define SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID 2u
#define SRK_AUDIO_STAGE4_SHAPE_LEVEL_COUNT 16u
#define SRK_AUDIO_STAGE4_SAMPLES_PER_LEVEL 16u

#define SRK_AUDIO_STAGE6_SAMPLE_ADDRESS 0x00002800u
#define SRK_AUDIO_STAGE6_SAMPLE_LOOP_END SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT

#define SRK_AUDIO_PAN_HARD_RIGHT 0x0Fu
#define SRK_AUDIO_PAN_CENTER     0x00u
#define SRK_AUDIO_PAN_HARD_LEFT  0x1Fu

#define SRK_AUDIO_PITCH_LOW  0x7800u
#define SRK_AUDIO_PITCH_MID  0x0000u
#define SRK_AUDIO_PITCH_HIGH 0x0800u

#define SRK_AUDIO_STAGE2_STEREO_TONE_ID 3u
#define SRK_AUDIO_STAGE5_MIXED_TONE_ID 4u
#define SRK_AUDIO_STAGE2_LEFT_SLOT 0u
#define SRK_AUDIO_STAGE2_RIGHT_SLOT 1u
#define SRK_AUDIO_STAGE2_LEFT_MASK 0x01u
#define SRK_AUDIO_STAGE2_RIGHT_MASK 0x02u


static const srk_u16 srk_audio_stage4_shape[SRK_AUDIO_STAGE4_SHAPE_LEVEL_COUNT] = {
    0x0000u, 0x1000u, 0x2800u, 0x1800u,
    0x3000u, 0x1000u, 0x0800u, 0x0000u,
    0xF800u, 0xE800u, 0xD000u, 0xE000u,
    0xF000u, 0xF800u, 0x0000u, 0x0000u
};


static volatile srk_u16 *srk_saturn_audio_slot(unsigned int slot)
{
    return SRK_AUDIO_SCSP_SLOT0 + (slot * SRK_AUDIO_SLOT_WORDS);
}


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


static void srk_saturn_audio_install_stage4_sample(void)
{
    unsigned int level;
    unsigned int repeat;
    unsigned int sample;
    unsigned int base;

    base = SRK_AUDIO_STAGE4_SAMPLE_ADDRESS >> 1;
    sample = 0u;
    for(level=0u; level<SRK_AUDIO_STAGE4_SHAPE_LEVEL_COUNT; level++){
        for(repeat=0u; repeat<SRK_AUDIO_STAGE4_SAMPLES_PER_LEVEL; repeat++){
            SRK_AUDIO_SOUND_RAM[base + sample] = srk_audio_stage4_shape[level];
            sample += 1u;
        }
    }
    SRK_AUDIO_SOUND_RAM[base + SRK_AUDIO_STAGE4_SAMPLE_LOOP_END] =
        srk_audio_stage4_shape[0];
}


static void srk_saturn_audio_install_stage6_sample(
    const SRK_SATURN_PACKAGED_PCM *pcm
)
{
    unsigned int sample;
    unsigned int base;

    if(!pcm || pcm->sample_count != SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT)
        return;

    base = SRK_AUDIO_STAGE6_SAMPLE_ADDRESS >> 1;
    for(sample=0u; sample<pcm->sample_count; sample++)
        SRK_AUDIO_SOUND_RAM[base + sample] = pcm->samples[sample];

    /* Match the already accepted exclusive loop-end Sound-RAM convention. */
    SRK_AUDIO_SOUND_RAM[base + SRK_AUDIO_STAGE6_SAMPLE_LOOP_END] =
        pcm->samples[pcm->loop_start];
}


static void srk_saturn_audio_register_key_off_all(void)
{
    volatile srk_u16 *control;
    unsigned int slot;

    for(slot=0; slot<SRK_AUDIO_SLOT_COUNT; slot++){
        control = srk_saturn_audio_slot(slot);
        *control = (srk_u16)(*control & (srk_u16)~SRK_AUDIO_CONTROL_KYONB);
    }

    SRK_AUDIO_SCSP_SLOT0[SRK_AUDIO_SLOT_CONTROL] =
        SRK_AUDIO_CONTROL_NORMAL_LOOP | SRK_AUDIO_CONTROL_KYONEX;
}


static void srk_saturn_audio_set_slot_source(
    unsigned int slot,
    unsigned int waveform_id
)
{
    volatile srk_u16 *registers;

    registers = srk_saturn_audio_slot(slot);
    if(waveform_id == SRK_AUDIO_STAGE4_WAVEFORM_SHAPED_PCM_ID){
        registers[SRK_AUDIO_SLOT_SA_LOW] = SRK_AUDIO_STAGE4_SAMPLE_ADDRESS;
        registers[SRK_AUDIO_SLOT_LSA] = 0x0000u;
        registers[SRK_AUDIO_SLOT_LEA] = SRK_AUDIO_STAGE4_SAMPLE_LOOP_END;
    }else if(waveform_id == SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID){
        registers[SRK_AUDIO_SLOT_SA_LOW] = SRK_AUDIO_STAGE6_SAMPLE_ADDRESS;
        registers[SRK_AUDIO_SLOT_LSA] = 0x0000u;
        registers[SRK_AUDIO_SLOT_LEA] = SRK_AUDIO_STAGE6_SAMPLE_LOOP_END;
    }else{
        registers[SRK_AUDIO_SLOT_SA_LOW] = SRK_AUDIO_WAVE_ADDRESS;
        registers[SRK_AUDIO_SLOT_LSA] = 0x0000u;
        registers[SRK_AUDIO_SLOT_LEA] = SRK_AUDIO_LOOP_END;
    }
}


static void srk_saturn_audio_configure_slot(unsigned int slot)
{
    volatile srk_u16 *registers;

    registers = srk_saturn_audio_slot(slot);
    registers[SRK_AUDIO_SLOT_CONTROL] = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    srk_saturn_audio_set_slot_source(slot, SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID);
    registers[SRK_AUDIO_SLOT_EG1] = 0x0000u;
    registers[SRK_AUDIO_SLOT_EG2] = 0x0000u;
    /* SDIR bypasses EG/TL/LFO for the deterministic direct-PCM proof. */
    registers[SRK_AUDIO_SLOT_TL] = SRK_AUDIO_SOUND_DIRECT;
    registers[SRK_AUDIO_SLOT_FM] = 0x0000u;
    registers[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID;
    registers[SRK_AUDIO_SLOT_LFO] = 0x0000u;
    registers[SRK_AUDIO_SLOT_DSP] = 0x0000u;
    registers[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
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

    SRK_AUDIO_SCSP_COMMON[0] = 0x020Fu;

    srk_saturn_audio_install_dummy_cpu();
    srk_saturn_audio_install_waveform();
    srk_saturn_audio_install_stage4_sample();
    srk_saturn_audio_register_key_off_all();
    srk_saturn_audio_configure_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    srk_saturn_audio_configure_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);

    if(!srk_saturn_audio_smpc_command(SRK_AUDIO_SMPC_SNDON))
        return 0;

    state->audio_initialized = 1;
    state->audio_playing = 0;
    state->audio_playing_mask = 0u;
    state->audio_waveform_id = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    state->audio_right_waveform_id = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    state->audio_packaged_attempted = 0;
    state->audio_packaged_ready = 0;
    state->audio_packaged_pcm.status = SRK_SATURN_PACKAGED_PCM_NOT_ATTEMPTED;
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


static srk_u16 srk_saturn_audio_mixer_value(
    unsigned int volume_level,
    unsigned int pan_value,
    int audible
)
{
    unsigned int level;

    level = volume_level;
    if(level > 7u)
        level = 7u;
    if(!audible)
        level = 0u;

    return (srk_u16)((level << 13) | ((pan_value & 0x1fu) << 8));
}


static void srk_saturn_audio_apply_key_mask(unsigned int mask)
{
    volatile srk_u16 *left;
    volatile srk_u16 *right;
    srk_u16 left_control;
    srk_u16 right_control;

    left = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    right = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);

    left_control = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    right_control = SRK_AUDIO_CONTROL_NORMAL_LOOP;
    if(mask & SRK_AUDIO_STAGE2_LEFT_MASK)
        left_control = (srk_u16)(left_control | SRK_AUDIO_CONTROL_KYONB);
    if(mask & SRK_AUDIO_STAGE2_RIGHT_MASK)
        right_control = (srk_u16)(right_control | SRK_AUDIO_CONTROL_KYONB);

    left[SRK_AUDIO_SLOT_CONTROL] = left_control;
    right[SRK_AUDIO_SLOT_CONTROL] = right_control;
    left[SRK_AUDIO_SLOT_CONTROL] = (srk_u16)(left_control | SRK_AUDIO_CONTROL_KYONEX);
}


static int srk_saturn_audio_prepare_packaged(SRK_SATURN_HOST_STATE *state)
{
    volatile srk_u16 *left;
    volatile srk_u16 *right;

    if(!state)
        return 0;
    if(state->audio_packaged_ready)
        return 1;
    if(state->audio_packaged_attempted)
        return 0;

    state->audio_packaged_attempted = 1;

    /* Silence owned voices before the synchronous CD read begins. */
    left = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    right = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);
    left[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
    right[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
    if(state->audio_playing_mask != 0u){
        srk_saturn_audio_apply_key_mask(0u);
        state->audio_playing_mask = 0u;
        state->audio_playing = 0;
    }

    if(!srk_saturn_packaged_pcm_load(&state->audio_packaged_pcm))
        return 0;

    srk_saturn_audio_install_stage6_sample(&state->audio_packaged_pcm);
    state->audio_packaged_ready = 1;
    return 1;
}


static void srk_saturn_audio_retarget_sources(
    SRK_SATURN_HOST_STATE *state,
    unsigned int left_waveform,
    unsigned int right_waveform
)
{
    if(!state)
        return;

    if(left_waveform == state->audio_waveform_id &&
       right_waveform == state->audio_right_waveform_id)
        return;

    if(state->audio_playing_mask != 0u){
        srk_saturn_audio_apply_key_mask(0u);
        state->audio_playing_mask = 0u;
    }

    if(left_waveform != state->audio_waveform_id){
        srk_saturn_audio_set_slot_source(SRK_AUDIO_STAGE2_LEFT_SLOT, left_waveform);
        state->audio_waveform_id = left_waveform;
    }
    if(right_waveform != state->audio_right_waveform_id){
        srk_saturn_audio_set_slot_source(SRK_AUDIO_STAGE2_RIGHT_SLOT, right_waveform);
        state->audio_right_waveform_id = right_waveform;
    }
}


static int srk_saturn_audio_present(
    void *context,
    const SRK_DIAG_AUDIO_REQUEST *request
)
{
    SRK_SATURN_HOST_STATE *state;
    volatile srk_u16 *left;
    volatile srk_u16 *right;
    unsigned int desired_mask;
    unsigned int desired_left_waveform;
    unsigned int desired_right_waveform;
    int audible;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !request)
        return 0;
    if(!srk_saturn_audio_initialize(state))
        return 0;

    left = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    right = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);
    desired_mask = 0u;
    audible = request->playing && !request->muted;

    desired_left_waveform = request->waveform_id;
    if(desired_left_waveform != SRK_AUDIO_STAGE4_WAVEFORM_SHAPED_PCM_ID &&
       desired_left_waveform != SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID)
        desired_left_waveform = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    desired_right_waveform = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;

    if(request->tone_id == SRK_AUDIO_STAGE2_STEREO_TONE_ID){
        desired_left_waveform = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
        desired_right_waveform = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    }else if(request->tone_id == SRK_AUDIO_STAGE5_MIXED_TONE_ID){
        desired_left_waveform = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
        desired_right_waveform = SRK_AUDIO_STAGE4_WAVEFORM_SHAPED_PCM_ID;
    }

    if(desired_left_waveform == SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID ||
       desired_right_waveform == SRK_AUDIO_STAGE6_WAVEFORM_PACKAGED_PCM_ID){
        if(!srk_saturn_audio_prepare_packaged(state))
            return 0;
    }else if(!state->audio_packaged_ready){
        /* Leaving a failed attempt permits one fresh retry on the next entry. */
        state->audio_packaged_attempted = 0;
        state->audio_packaged_pcm.status = SRK_SATURN_PACKAGED_PCM_NOT_ATTEMPTED;
    }

    srk_saturn_audio_retarget_sources(
        state,
        desired_left_waveform,
        desired_right_waveform
    );

    if(request->tone_id == SRK_AUDIO_STAGE2_STEREO_TONE_ID ||
       request->tone_id == SRK_AUDIO_STAGE5_MIXED_TONE_ID){
        if(request->tone_id == SRK_AUDIO_STAGE2_STEREO_TONE_ID){
            left[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_LOW;
            right[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_HIGH;
        }else{
            left[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID;
            right[SRK_AUDIO_SLOT_PITCH] = SRK_AUDIO_PITCH_MID;
        }

        left[SRK_AUDIO_SLOT_MIXER] = srk_saturn_audio_mixer_value(
            request->volume_level,
            SRK_AUDIO_PAN_HARD_LEFT,
            audible && request->pan_id != 2u
        );
        right[SRK_AUDIO_SLOT_MIXER] = srk_saturn_audio_mixer_value(
            request->volume_level,
            SRK_AUDIO_PAN_HARD_RIGHT,
            audible && request->pan_id != 0u
        );

        if(request->playing && request->pan_id != 2u)
            desired_mask |= SRK_AUDIO_STAGE2_LEFT_MASK;
        if(request->playing && request->pan_id != 0u)
            desired_mask |= SRK_AUDIO_STAGE2_RIGHT_MASK;
    }else{
        left[SRK_AUDIO_SLOT_PITCH] = srk_saturn_audio_pitch(request->tone_id);
        left[SRK_AUDIO_SLOT_MIXER] = srk_saturn_audio_mixer_value(
            request->volume_level,
            srk_saturn_audio_pan(request->pan_id),
            audible
        );
        right[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
        if(request->playing)
            desired_mask = SRK_AUDIO_STAGE2_LEFT_MASK;
    }

    if(desired_mask != state->audio_playing_mask){
        srk_saturn_audio_apply_key_mask(desired_mask);
        state->audio_playing_mask = desired_mask;
    }
    state->audio_playing = desired_mask ? 1 : 0;

    return 1;
}


static void srk_saturn_audio_stop(void *context)
{
    SRK_SATURN_HOST_STATE *state;
    volatile srk_u16 *left;
    volatile srk_u16 *right;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !state->audio_initialized)
        return;

    left = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    right = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);
    left[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
    right[SRK_AUDIO_SLOT_MIXER] = 0x0000u;
    srk_saturn_audio_apply_key_mask(0u);
    state->audio_playing_mask = 0u;
    state->audio_playing = 0;
}


static int srk_saturn_audio_read_status(
    void *context,
    SRK_DIAG_AUDIO_STATUS *status
)
{
    SRK_SATURN_HOST_STATE *state;
    volatile srk_u16 *left;
    volatile srk_u16 *right;

    state = (SRK_SATURN_HOST_STATE *)context;
    if(!state || !status || !state->audio_initialized)
        return 0;

    left = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_LEFT_SLOT);
    right = srk_saturn_audio_slot(SRK_AUDIO_STAGE2_RIGHT_SLOT);
    status->initialized = 1;
    status->common_control = SRK_AUDIO_SCSP_COMMON[0];

    status->slot_control = left[SRK_AUDIO_SLOT_CONTROL];
    status->slot_source = left[SRK_AUDIO_SLOT_SA_LOW];
    status->slot_loop_end = left[SRK_AUDIO_SLOT_LEA];
    status->pitch = left[SRK_AUDIO_SLOT_PITCH];
    status->mixer = left[SRK_AUDIO_SLOT_MIXER];

    status->slot1_control = right[SRK_AUDIO_SLOT_CONTROL];
    status->slot1_source = right[SRK_AUDIO_SLOT_SA_LOW];
    status->slot1_loop_end = right[SRK_AUDIO_SLOT_LEA];
    status->slot1_pitch = right[SRK_AUDIO_SLOT_PITCH];
    status->slot1_mixer = right[SRK_AUDIO_SLOT_MIXER];
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
    state->audio_playing_mask = 0u;
    state->audio_waveform_id = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    state->audio_right_waveform_id = SRK_AUDIO_STAGE4_WAVEFORM_TONE_ID;
    state->audio_packaged_attempted = 0;
    state->audio_packaged_ready = 0;
    state->audio_packaged_pcm.status = SRK_SATURN_PACKAGED_PCM_NOT_ATTEMPTED;
    host->present_audio_tone = srk_saturn_audio_present;
    host->stop_audio = srk_saturn_audio_stop;
    host->read_audio_status = srk_saturn_audio_read_status;
}