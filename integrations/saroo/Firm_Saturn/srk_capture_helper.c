#include "main.h"
#include "srk_capture_helper.h"

/* Canonical Sega Saturn Work RAM regions used by SRK's generic tooling. */
#define SRK_WORK_RAM_LOW_START   0x00200000u
#define SRK_WORK_RAM_HIGH_START  0x06000000u
#define SRK_WORK_RAM_SIZE        0x00100000u


static int srk_capture_range_is_valid(unsigned int start_address, unsigned int size)
{
    if(size==0)
        return 0;

    /* Reject a range that wraps the 32-bit Saturn address space. */
    if(start_address > (0xffffffffu - (size-1u)))
        return 0;

    return 1;
}


int srk_capture_range_to_file(
    char *path,
    unsigned int start_address,
    unsigned int size
)
{
    unsigned int offset;

    if(path==NULL || path[0]==0)
        return SRK_CAPTURE_ERR_ARGUMENT;
    if(!srk_capture_range_is_valid(start_address, size))
        return SRK_CAPTURE_ERR_RANGE;

    offset = 0;
    while(offset<size){
        unsigned int remaining = size-offset;
        unsigned int chunk = remaining;
        int file_offset;
        int written;

        if(chunk>SRK_CAPTURE_CHUNK_SIZE)
            chunk = SRK_CAPTURE_CHUNK_SIZE;

        /*
         * Upstream SAROO's SSCMD_FILEWR path interprets offset -1 as
         * create/truncate, then seeks to file offset zero.  Later writes use
         * their explicit offsets, so a 1 MiB capture becomes sixteen verified
         * 64 KiB writes instead of one unverified staging-buffer transfer.
         */
        file_offset = (offset==0) ? -1 : (int)offset;
        written = write_file(
            path,
            file_offset,
            (int)chunk,
            (void*)(start_address+offset)
        );
        if(written<0)
            return written;
        if((unsigned int)written!=chunk)
            return SRK_CAPTURE_ERR_SHORT_WRITE;

        offset += chunk;
    }

    return SRK_CAPTURE_OK;
}


int srk_capture_work_ram_low(char *path)
{
    return srk_capture_range_to_file(
        path,
        SRK_WORK_RAM_LOW_START,
        SRK_WORK_RAM_SIZE
    );
}


int srk_capture_work_ram_high(char *path)
{
    return srk_capture_range_to_file(
        path,
        SRK_WORK_RAM_HIGH_START,
        SRK_WORK_RAM_SIZE
    );
}
