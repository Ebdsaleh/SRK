#ifndef SRK_SATURN_SBL_MIDI_CALIBRATION_H
#define SRK_SATURN_SBL_MIDI_CALIBRATION_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Bind the reusable MIDI calibration screen to Sega's SBL Direct-MIDI path.
 *
 * This binding deliberately provides no review-persistence callback.  Review
 * persistence stays unavailable until a real Saturn/SAROO transport is proven.
 */
void srk_saturn_sbl_midi_calibration_bind(SRK_DIAG_HOST *host);

#ifdef __cplusplus
}
#endif

#endif
