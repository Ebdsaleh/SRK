#ifndef SRK_SATURN_PACKAGED_PCM_H
#define SRK_SATURN_PACKAGED_PCM_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT 512u
#define SRK_SATURN_PACKAGED_PCM_FILE_BYTES 1040u

typedef enum SRK_SATURN_PACKAGED_PCM_STATUS {
    SRK_SATURN_PACKAGED_PCM_NOT_ATTEMPTED = 0,
    SRK_SATURN_PACKAGED_PCM_READY = 1,
    SRK_SATURN_PACKAGED_PCM_GFS_INIT_FAILED = 2,
    SRK_SATURN_PACKAGED_PCM_NAME_LOOKUP_FAILED = 3,
    SRK_SATURN_PACKAGED_PCM_OPEN_FAILED = 4,
    SRK_SATURN_PACKAGED_PCM_SIZE_FAILED = 5,
    SRK_SATURN_PACKAGED_PCM_LOAD_FAILED = 6,
    SRK_SATURN_PACKAGED_PCM_FORMAT_FAILED = 7
} SRK_SATURN_PACKAGED_PCM_STATUS;

typedef struct SRK_SATURN_PACKAGED_PCM {
    srk_u16 samples[SRK_SATURN_PACKAGED_PCM_SAMPLE_COUNT];
    unsigned int sample_count;
    unsigned int loop_start;
    unsigned int loop_end;
    unsigned int bytes_loaded;
    SRK_SATURN_PACKAGED_PCM_STATUS status;
} SRK_SATURN_PACKAGED_PCM;

/*
 * Load and validate the SRK-owned /SRKPCM.BIN payload through the installed
 * Sega GFS runtime. The caller owns the returned sample words; this module does
 * not touch Sound RAM or SCSP registers.
 */
int srk_saturn_packaged_pcm_load(SRK_SATURN_PACKAGED_PCM *pcm);

#ifdef __cplusplus
}
#endif

#endif