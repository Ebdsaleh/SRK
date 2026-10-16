#include "srk_saturn_sbl_midi_calibration.h"
#include "srk_saturn_sbl_direct_midi.h"


#define SRK_SBL_CAL_SEQ_NO 2u
#define SRK_SBL_CAL_SEQ_PRI 0u
#define SRK_SBL_CAL_CHANNEL 0u
#define SRK_SBL_CAL_NOTE_OFF 0u
#define SRK_SBL_CAL_NOTE_ON 1u
#define SRK_SBL_CAL_CONTROL_CHANGE 3u
#define SRK_SBL_CAL_PROGRAM_CHANGE 4u
#define SRK_SBL_CAL_BANK_CONTROLLER 32u
#define SRK_SBL_CAL_MELODIC_BANK 0u
#define SRK_SBL_CAL_PAN_CONTROLLER 10u
#define SRK_SBL_CAL_MIDI_CHANNEL_MAX 15u
#define SRK_SBL_CAL_MIDI_DATA_MAX 127u


static int srk_saturn_sbl_midi_result(SndRet result)
{
    return result == SND_RET_SET;
}


static int srk_saturn_sbl_midi_select_program(
    void *context,
    unsigned int program
)
{
    SndRet result;

    (void)context;
    if(program > SRK_SBL_CAL_MIDI_DATA_MAX)
        return 0;

    result = srk_saturn_sbl_direct_midi(
        SRK_SBL_CAL_SEQ_NO,
        SRK_SBL_CAL_SEQ_PRI,
        SRK_SBL_CAL_CONTROL_CHANGE,
        SRK_SBL_CAL_CHANNEL,
        SRK_SBL_CAL_BANK_CONTROLLER,
        SRK_SBL_CAL_MELODIC_BANK
    );
    if(!srk_saturn_sbl_midi_result(result))
        return 0;

    return srk_saturn_sbl_midi_result(
        srk_saturn_sbl_direct_midi(
            SRK_SBL_CAL_SEQ_NO,
            SRK_SBL_CAL_SEQ_PRI,
            SRK_SBL_CAL_PROGRAM_CHANGE,
            SRK_SBL_CAL_CHANNEL,
            (Uint8)program,
            0u
        )
    );
}


static int srk_saturn_sbl_midi_set_pan(
    void *context,
    unsigned int channel,
    unsigned int pan
)
{
    (void)context;
    if(channel > SRK_SBL_CAL_MIDI_CHANNEL_MAX || pan > SRK_SBL_CAL_MIDI_DATA_MAX)
        return 0;

    return srk_saturn_sbl_midi_result(
        srk_saturn_sbl_direct_midi(
            SRK_SBL_CAL_SEQ_NO,
            SRK_SBL_CAL_SEQ_PRI,
            SRK_SBL_CAL_CONTROL_CHANGE,
            (Uint8)channel,
            SRK_SBL_CAL_PAN_CONTROLLER,
            (Uint8)pan
        )
    );
}


static int srk_saturn_sbl_midi_note_on(
    void *context,
    unsigned int channel,
    unsigned int note,
    unsigned int velocity
)
{
    (void)context;
    if(channel > SRK_SBL_CAL_MIDI_CHANNEL_MAX ||
       note > SRK_SBL_CAL_MIDI_DATA_MAX ||
       velocity > SRK_SBL_CAL_MIDI_DATA_MAX)
        return 0;

    return srk_saturn_sbl_midi_result(
        srk_saturn_sbl_direct_midi(
            SRK_SBL_CAL_SEQ_NO,
            SRK_SBL_CAL_SEQ_PRI,
            SRK_SBL_CAL_NOTE_ON,
            (Uint8)channel,
            (Uint8)note,
            (Uint8)velocity
        )
    );
}


static int srk_saturn_sbl_midi_note_off(
    void *context,
    unsigned int channel,
    unsigned int note,
    unsigned int velocity
)
{
    (void)context;
    if(channel > SRK_SBL_CAL_MIDI_CHANNEL_MAX ||
       note > SRK_SBL_CAL_MIDI_DATA_MAX ||
       velocity > SRK_SBL_CAL_MIDI_DATA_MAX)
        return 0;

    return srk_saturn_sbl_midi_result(
        srk_saturn_sbl_direct_midi(
            SRK_SBL_CAL_SEQ_NO,
            SRK_SBL_CAL_SEQ_PRI,
            SRK_SBL_CAL_NOTE_OFF,
            (Uint8)channel,
            (Uint8)note,
            (Uint8)velocity
        )
    );
}


void srk_saturn_sbl_midi_calibration_bind(SRK_DIAG_HOST *host)
{
    if(!host)
        return;

    host->midi_select_program = srk_saturn_sbl_midi_select_program;
    host->midi_set_pan = srk_saturn_sbl_midi_set_pan;
    host->midi_note_on = srk_saturn_sbl_midi_note_on;
    host->midi_note_off = srk_saturn_sbl_midi_note_off;
    host->midi_persist_review = 0;
}
