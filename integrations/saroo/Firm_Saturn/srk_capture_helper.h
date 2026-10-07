#ifndef SRK_CAPTURE_HELPER_H
#define SRK_CAPTURE_HELPER_H

/*
 * SRK title-neutral SAROO memory capture helper.
 *
 * This header is intentionally independent of one game.  The implementation
 * is designed to be compiled inside upstream SAROO's Firm_Saturn tree, where
 * main.h supplies write_file() and the Saturn-side integer aliases.
 */

#define SRK_CAPTURE_CHUNK_SIZE 0x00010000u

#define SRK_CAPTURE_OK                 0
#define SRK_CAPTURE_ERR_ARGUMENT      -100
#define SRK_CAPTURE_ERR_RANGE         -101
#define SRK_CAPTURE_ERR_SHORT_WRITE   -102

int srk_capture_range_to_file(
    char *path,
    unsigned int start_address,
    unsigned int size
);

int srk_capture_work_ram_low(char *path);
int srk_capture_work_ram_high(char *path);

#endif
