#include "main.h"
#include "srk_runtime_resident_proof.h"


#define SRK_RUNTIME_RESIDENT_PROOF_PATH        "/SAROO/SRK_RUNTIME_PROOF.BIN"
#define SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE   96
#define SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE   32
#define SRK_RUNTIME_RESIDENT_PROOF_VECTOR      0x0600090cu
#define SRK_RUNTIME_RESIDENT_PROOF_RETURN      0x0600091au

#define SRK_RUNTIME_RESIDENT_STAGE_ARMED       1
#define SRK_RUNTIME_RESIDENT_STAGE_INSTALLED   2
#define SRK_RUNTIME_RESIDENT_STAGE_PROVEN      3
#define SRK_RUNTIME_RESIDENT_STAGE_REJECTED    0x7f


/*
 * BIOS interrupt-handler instructions replaced by SAROO's established
 * cheat-style trampoline.  These correspond to 0x0600090c..0x06000918:
 *
 *   mov     r3,r4
 *   shlr16  r3
 *   ldc     r3,sr
 *   exts.w  r4,r4
 *   or      r4,r2
 *   mov.l   r2,@r1
 *   mov.l   r2,@r5
 *
 * Refuse the hook rather than patch an unexpected BIOS shape.
 */
static const u16 srk_runtime_resident_expected_vector[7] = {
    0x6433, 0x4329, 0x430e, 0x644f, 0x224b, 0x2122, 0x2522
};


static int srk_runtime_resident_armed = 0;
static int srk_runtime_resident_installed = 0;
static int srk_runtime_resident_proof_written = 0;
static u32 srk_runtime_resident_callbacks = 0;
static u32 srk_runtime_resident_arm_timer = 0;
static u8 srk_runtime_resident_file[SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE];
static u8 srk_runtime_resident_slot[SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE];


static void srk_runtime_resident_put_be32(u8 *dst, u32 value)
{
    dst[0] = (u8)((value >> 24) & 0xff);
    dst[1] = (u8)((value >> 16) & 0xff);
    dst[2] = (u8)((value >> 8) & 0xff);
    dst[3] = (u8)(value & 0xff);
}


static void srk_runtime_resident_build_slot(
    u8 *slot,
    int stage,
    u32 count,
    u32 timer
)
{
    memset(slot, 0, SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE);
    slot[0] = 'S';
    slot[1] = 'R';
    slot[2] = 'K';
    slot[3] = 'P';
    slot[4] = (u8)stage;
    slot[5] = 1;

    srk_runtime_resident_put_be32(slot + 8, count);
    srk_runtime_resident_put_be32(slot + 12, timer);
    srk_runtime_resident_put_be32(slot + 16, timer - srk_runtime_resident_arm_timer);
    srk_runtime_resident_put_be32(slot + 20, SRK_RUNTIME_RESIDENT_PROOF_VECTOR);
    srk_runtime_resident_put_be32(slot + 24, SRK_RUNTIME_RESIDENT_PROOF_RETURN);
    srk_runtime_resident_put_be32(
        slot + 28,
        SRK_RUNTIME_RESIDENT_PROOF_CALLBACKS
    );
}


static int srk_runtime_resident_write_slot(int offset, u8 *slot)
{
    int written;

    written = write_file(
        SRK_RUNTIME_RESIDENT_PROOF_PATH,
        offset,
        SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE,
        slot
    );
    return written == SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE;
}


static int srk_runtime_resident_vector_matches(void)
{
    volatile u16 *vector = (volatile u16*)SRK_RUNTIME_RESIDENT_PROOF_VECTOR;
    int i;

    for(i=0; i<7; i++){
        if(vector[i] != srk_runtime_resident_expected_vector[i])
            return i + 1;
    }
    return 0;
}


static void srk_runtime_resident_restore_vector(void)
{
    volatile u16 *vector = (volatile u16*)SRK_RUNTIME_RESIDENT_PROOF_VECTOR;
    u32 saved_sr;
    int i;

    saved_sr = get_sr();
    set_imask(15);
    for(i=0; i<7; i++)
        vector[i] = srk_runtime_resident_expected_vector[i];
    set_sr(saved_sr);
}


int srk_runtime_resident_proof_arm(void)
{
    u32 now;
    int written;

    srk_runtime_resident_armed = 0;
    srk_runtime_resident_installed = 0;
    srk_runtime_resident_proof_written = 0;
    srk_runtime_resident_callbacks = 0;

    now = SS_TIMER;
    srk_runtime_resident_arm_timer = now;

    memset(
        srk_runtime_resident_file,
        0,
        SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE
    );
    srk_runtime_resident_build_slot(
        srk_runtime_resident_file,
        SRK_RUNTIME_RESIDENT_STAGE_ARMED,
        0,
        now
    );

    written = write_file(
        SRK_RUNTIME_RESIDENT_PROOF_PATH,
        0,
        SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE,
        srk_runtime_resident_file
    );
    if(written != SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE)
        return SRK_RUNTIME_RESIDENT_PROOF_ERR_ARM_WRITE;

    srk_runtime_resident_armed = 1;
    return SRK_RUNTIME_RESIDENT_PROOF_OK;
}


int srk_runtime_resident_proof_install(void)
{
    u32 saved_sr;
    u32 now;
    int mismatch;

    if(!srk_runtime_resident_armed)
        return SRK_RUNTIME_RESIDENT_PROOF_OK;

    mismatch = srk_runtime_resident_vector_matches();
    if(mismatch){
        now = SS_TIMER;
        srk_runtime_resident_build_slot(
            srk_runtime_resident_slot,
            SRK_RUNTIME_RESIDENT_STAGE_REJECTED,
            (u32)mismatch,
            now
        );
        srk_runtime_resident_write_slot(
            SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE,
            srk_runtime_resident_slot
        );
        srk_runtime_resident_armed = 0;
        return SRK_RUNTIME_RESIDENT_PROOF_ERR_VECTOR;
    }

    saved_sr = get_sr();
    set_imask(15);
    *(volatile u32*)0x0600090c = 0xd401442b;
    *(volatile u16*)0x06000910 = 0x0009;
    *(volatile u32*)0x06000914 = (u32)srk_runtime_resident_proof_vector_entry;
    set_sr(saved_sr);

    now = SS_TIMER;
    srk_runtime_resident_build_slot(
        srk_runtime_resident_slot,
        SRK_RUNTIME_RESIDENT_STAGE_INSTALLED,
        0,
        now
    );
    if(!srk_runtime_resident_write_slot(
        SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE,
        srk_runtime_resident_slot
    )){
        srk_runtime_resident_restore_vector();
        srk_runtime_resident_armed = 0;
        return SRK_RUNTIME_RESIDENT_PROOF_ERR_INSTALL_WRITE;
    }

    srk_runtime_resident_callbacks = 0;
    srk_runtime_resident_installed = 1;
    return SRK_RUNTIME_RESIDENT_PROOF_OK;
}


void srk_runtime_resident_proof_tick(void)
{
    u32 now;

    if(!srk_runtime_resident_armed ||
       !srk_runtime_resident_installed ||
       srk_runtime_resident_proof_written)
        return;

    srk_runtime_resident_callbacks += 1;
    if(srk_runtime_resident_callbacks < SRK_RUNTIME_RESIDENT_PROOF_CALLBACKS)
        return;

    /*
     * The assembly trampoline masks interrupts around this callback and
     * preserves the BIOS-live context that has not yet been stacked by the
     * original handler.  Keep the one-shot latch before the proof write so a
     * later callback cannot attempt the same write again.
     */
    srk_runtime_resident_proof_written = 1;
    now = SS_TIMER;
    srk_runtime_resident_build_slot(
        srk_runtime_resident_slot,
        SRK_RUNTIME_RESIDENT_STAGE_PROVEN,
        srk_runtime_resident_callbacks,
        now
    );
    srk_runtime_resident_write_slot(
        SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE * 2,
        srk_runtime_resident_slot
    );

    /* One proof attempt is enough.  Restore the BIOS vector immediately. */
    srk_runtime_resident_restore_vector();
    srk_runtime_resident_installed = 0;
    srk_runtime_resident_armed = 0;
}
