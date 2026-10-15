#include "srk_saturn_sbl_direct_midi.h"

SndRet srk_saturn_sbl_direct_midi(
    SndSeqNum seq_no,
    SndSeqPri seq_pri,
    Uint8 md_com,
    Uint8 ch,
    Uint8 dt1,
    Uint8 dt2
)
{
    return SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2);
}
