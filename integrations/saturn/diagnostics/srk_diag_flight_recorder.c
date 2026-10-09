#include "srk_diag_flight_recorder.h"


void srk_diag_flight_reset(SRK_DIAG_FLIGHT_RECORDER *recorder)
{
    if(!recorder)
        return;

    recorder->count = 0;
    recorder->write_index = 0;
    recorder->armed = 0;
    recorder->frozen = 0;
}


void srk_diag_flight_arm(SRK_DIAG_FLIGHT_RECORDER *recorder)
{
    if(!recorder)
        return;

    recorder->count = 0;
    recorder->write_index = 0;
    recorder->armed = 1;
    recorder->frozen = 0;
}


void srk_diag_flight_append(
    SRK_DIAG_FLIGHT_RECORDER *recorder,
    const SRK_DIAG_FLIGHT_RECORD *record
)
{
    if(!recorder || !record || !recorder->armed || recorder->frozen)
        return;

    recorder->records[recorder->write_index] = *record;
    recorder->write_index += 1;
    if(recorder->write_index >= SRK_DIAG_FLIGHT_CAPACITY)
        recorder->write_index = 0;

    if(recorder->count < SRK_DIAG_FLIGHT_CAPACITY)
        recorder->count += 1;
}


void srk_diag_flight_freeze(SRK_DIAG_FLIGHT_RECORDER *recorder)
{
    if(!recorder || !recorder->armed)
        return;

    recorder->frozen = 1;
}


unsigned int srk_diag_flight_count(const SRK_DIAG_FLIGHT_RECORDER *recorder)
{
    return recorder ? recorder->count : 0;
}


const SRK_DIAG_FLIGHT_RECORD *srk_diag_flight_record(
    const SRK_DIAG_FLIGHT_RECORDER *recorder,
    unsigned int chronological_index
)
{
    unsigned int oldest;
    unsigned int physical;

    if(!recorder || chronological_index >= recorder->count)
        return 0;

    if(recorder->count < SRK_DIAG_FLIGHT_CAPACITY)
        return &recorder->records[chronological_index];

    oldest = recorder->write_index;
    physical = oldest + chronological_index;
    if(physical >= SRK_DIAG_FLIGHT_CAPACITY)
        physical -= SRK_DIAG_FLIGHT_CAPACITY;

    return &recorder->records[physical];
}
