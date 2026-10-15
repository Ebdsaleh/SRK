#ifndef SRK_SATURN_SBL_DIRECT_MIDI_H
#define SRK_SATURN_SBL_DIRECT_MIDI_H

#include "sega_snd.h"

/*
 * Thin SRK -> Sega Sound I/F boundary.
 *
 * Musical voice allocation, tone-bank interpretation and percussion identity
 * remain owned by Sega's Saturn Sound Driver.  SRK supplies the original MIDI
 * channel message bytes and timing only.
 */
SndRet srk_saturn_sbl_direct_midi(
    SndSeqNum seq_no,
    SndSeqPri seq_pri,
    Uint8 md_com,
    Uint8 ch,
    Uint8 dt1,
    Uint8 dt2
);

#endif
