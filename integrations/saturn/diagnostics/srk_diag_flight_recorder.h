#ifndef SRK_DIAG_FLIGHT_RECORDER_H
#define SRK_DIAG_FLIGHT_RECORDER_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_FLIGHT_SECONDS 30
#define SRK_DIAG_FLIGHT_MAX_HZ 60
#define SRK_DIAG_FLIGHT_CAPACITY (SRK_DIAG_FLIGHT_SECONDS * SRK_DIAG_FLIGHT_MAX_HZ)


typedef struct SRK_DIAG_FLIGHT_RECORD {
    srk_u32 timestamp_us;
    srk_u32 frame;
    srk_u16 raw_pad;
    srk_u16 normalized_pad;
    srk_u16 pressed;
    srk_u16 released;
    srk_u16 held;
    srk_u16 diagnostic_id;
    srk_u32 vbr;
    srk_u32 value0;
    srk_u32 value1;
} SRK_DIAG_FLIGHT_RECORD;


typedef struct SRK_DIAG_FLIGHT_RECORDER {
    SRK_DIAG_FLIGHT_RECORD records[SRK_DIAG_FLIGHT_CAPACITY];
    unsigned int count;
    unsigned int write_index;
    int armed;
    int frozen;
} SRK_DIAG_FLIGHT_RECORDER;


void srk_diag_flight_reset(SRK_DIAG_FLIGHT_RECORDER *recorder);
void srk_diag_flight_arm(SRK_DIAG_FLIGHT_RECORDER *recorder);
void srk_diag_flight_append(
    SRK_DIAG_FLIGHT_RECORDER *recorder,
    const SRK_DIAG_FLIGHT_RECORD *record
);
void srk_diag_flight_freeze(SRK_DIAG_FLIGHT_RECORDER *recorder);
unsigned int srk_diag_flight_count(const SRK_DIAG_FLIGHT_RECORDER *recorder);
const SRK_DIAG_FLIGHT_RECORD *srk_diag_flight_record(
    const SRK_DIAG_FLIGHT_RECORDER *recorder,
    unsigned int chronological_index
);

#ifdef __cplusplus
}
#endif

#endif
