#ifndef SRK_SATURN_AUDIO_H
#define SRK_SATURN_AUDIO_H

#include "srk_saturn_host.h"

#ifdef __cplusplus
extern "C" {
#endif


/* Bind the standalone SCSP/Sound-RAM implementation into the host interface. */
void srk_saturn_audio_bind(
    SRK_DIAG_HOST *host,
    SRK_SATURN_HOST_STATE *state
);

#ifdef __cplusplus
}
#endif

#endif
