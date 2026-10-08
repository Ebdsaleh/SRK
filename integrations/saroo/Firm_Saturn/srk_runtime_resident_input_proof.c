#include "main.h"
#include "srk_runtime_input.h"
#include "srk_runtime_resident_input_proof.h"


#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_PATH      "/SAROO/SRK_RUNTIME_INPUT_PROOF.BIN"
#define SRK_RUNTIME_RESIDENT_INPUT_PROOF_FILE_SIZE 96
#define SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE       32
#define SRK_RUNTIME_RESIDENT_INPUT_VECTOR          0x0600090cu
#define SRK_RUNTIME_RESIDENT_INPUT_RETURN          0x0600091au
#define SRK_RUNTIME_RESIDENT_INPUT_PAD1            0x06020232u

#define SRK_RUNTIME_RESIDENT_INPUT_STAGE_ARMED      1
#define SRK_RUNTIME_RESIDENT_INPUT_STAGE_INSTALLED  2
#define SRK_RUNTIME_RESIDENT_INPUT_STAGE_ACTIVATED  3
#define SRK_RUNTIME_RESIDENT_INPUT_STAGE_REJECTED   0x7f

#if SRK_RUNTIME_RESIDENT_INPUT_HOLD_SAMPLES != SRK_RUNTIME_INPUT_HOLD_SAMPLES
#error "resident input proof hold threshold must match srk_runtime_input"
#endif


/* Exact BIOS HBLANK-IN instructions displaced at 0x0600090c..0x06000918. */
static const u16 srk_runtime_resident_input_expected_vector[7] = {
    0x6433, 0x4329, 0x430e, 0x644f, 0x224b, 0x2122, 0x2522
};


static int srk_runtime_resident_input_armed = 0;
static int srk_runtime_resident_input_installed = 0;
static int srk_runtime_resident_input_activated = 0;
static u32 srk_runtime_resident_input_callbacks = 0;
static u32 srk_runtime_resident_input_samples = 0;
static u32 srk_runtime_resident_input_arm_timer = 0;
static u32 srk_runtime_resident_input_last_sample_timer = 0;
static SRK_RUNTIME_INPUT_STATE srk_runtime_resident_input_state;
static u8 srk_runtime_resident_input_file[SRK_RUNTIME_RESIDENT_INPUT_PROOF_FILE_SIZE];
static u8 srk_runtime_resident_input_slot[SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE];


static void srk_runtime_resident_input_put_be16(u8 *dst, u16 value)
{
    dst[0] = (u8)((value >> 8) & 0xff);
    dst[1] = (u8)(value & 0xff);
}


static void srk_runtime_resident_input_put_be32(u8 *dst, u32 value)
{
    dst[0] = (u8)((value >> 24) & 0xff);
    dst[1] = (u8)((value >> 16) & 0xff);
    dst[2] = (u8)((value >> 8) & 0xff);
    dst[3] = (u8)(value & 0xff);
}


static void srk_runtime_resident_input_build_slot(
    u8 *slot,
    int stage,
    u16 buttons,
    u32 callbacks,
    u32 samples,
    u32 timer
)
{
    memset(slot, 0, SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE);
    slot[0] = 'S';
    slot[1] = 'R';
    slot[2] = 'K';
    slot[3] = 'I';
    slot[4] = (u8)stage;
    slot[5] = 1;

    srk_runtime_resident_input_put_be16(slot + 6, buttons);
    srk_runtime_resident_input_put_be32(slot + 8, callbacks);
    srk_runtime_resident_input_put_be32(slot + 12, samples);
    srk_runtime_resident_input_put_be32(slot + 16, timer);
    srk_runtime_resident_input_put_be32(
        slot + 20,
        timer - srk_runtime_resident_input_arm_timer
    );
    srk_runtime_resident_input_put_be32(
        slot + 24,
        SRK_RUNTIME_RESIDENT_INPUT_SAMPLE_US
    );
    srk_runtime_resident_input_put_be32(
        slot + 28,
        SRK_RUNTIME_RESIDENT_INPUT_HOLD_SAMPLES
    );
}


static int srk_runtime_resident_input_write_slot(int offset, u8 *slot)
{
    int written;

    written = write_file(
        SRK_RUNTIME_RESIDENT_INPUT_PROOF_PATH,
        offset,
        SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE,
        slot
    );
    return written == SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE;
}


static int srk_runtime_resident_input_vector_matches(void)
{
    volatile u16 *vector = (volatile u16*)SRK_RUNTIME_RESIDENT_INPUT_VECTOR;
    int i;

    for(i=0; i<7; i++){
        if(vector[i] != srk_runtime_resident_input_expected_vector[i])
            return i + 1;
    }
    return 0;
}


static void srk_runtime_resident_input_restore_vector(void)
{
    volatile u16 *vector = (volatile u16*)SRK_RUNTIME_RESIDENT_INPUT_VECTOR;
    u32 saved_sr;
    int i;

    saved_sr = get_sr();
    set_imask(15);
    for(i=0; i<7; i++)
        vector[i] = srk_runtime_resident_input_expected_vector[i];
    set_sr(saved_sr);
}


int srk_runtime_resident_input_proof_arm(void)
{
    u32 now;
    int written;

    srk_runtime_resident_input_armed = 0;
    srk_runtime_resident_input_installed = 0;
    srk_runtime_resident_input_activated = 0;
    srk_runtime_resident_input_callbacks = 0;
    srk_runtime_resident_input_samples = 0;
    srk_runtime_input_reset(&srk_runtime_resident_input_state);

    now = SS_TIMER;
    srk_runtime_resident_input_arm_timer = now;
    srk_runtime_resident_input_last_sample_timer = now;

    memset(
        srk_runtime_resident_input_file,
        0,
        SRK_RUNTIME_RESIDENT_INPUT_PROOF_FILE_SIZE
    );
    srk_runtime_resident_input_build_slot(
        srk_runtime_resident_input_file,
        SRK_RUNTIME_RESIDENT_INPUT_STAGE_ARMED,
        0,
        0,
        0,
        now
    );

    written = write_file(
        SRK_RUNTIME_RESIDENT_INPUT_PROOF_PATH,
        0,
        SRK_RUNTIME_RESIDENT_INPUT_PROOF_FILE_SIZE,
        srk_runtime_resident_input_file
    );
    if(written != SRK_RUNTIME_RESIDENT_INPUT_PROOF_FILE_SIZE)
        return SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_ARM_WRITE;

    srk_runtime_resident_input_armed = 1;
    return SRK_RUNTIME_RESIDENT_INPUT_PROOF_OK;
}


int srk_runtime_resident_input_proof_install(void)
{
    u32 saved_sr;
    u32 now;
    int mismatch;

    if(!srk_runtime_resident_input_armed)
        return SRK_RUNTIME_RESIDENT_INPUT_PROOF_OK;

    mismatch = srk_runtime_resident_input_vector_matches();
    if(mismatch){
        now = SS_TIMER;
        srk_runtime_resident_input_build_slot(
            srk_runtime_resident_input_slot,
            SRK_RUNTIME_RESIDENT_INPUT_STAGE_REJECTED,
            0,
            (u32)mismatch,
            0,
            now
        );
        srk_runtime_resident_input_write_slot(
            SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE,
            srk_runtime_resident_input_slot
        );
        srk_runtime_resident_input_armed = 0;
        return SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_VECTOR;
    }

    saved_sr = get_sr();
    set_imask(15);
    *(volatile u32*)0x0600090c = 0xd401442b;
    *(volatile u16*)0x06000910 = 0x0009;
    *(volatile u32*)0x06000914 = (u32)srk_runtime_resident_input_proof_vector_entry;
    set_sr(saved_sr);

    now = SS_TIMER;
    srk_runtime_resident_input_build_slot(
        srk_runtime_resident_input_slot,
        SRK_RUNTIME_RESIDENT_INPUT_STAGE_INSTALLED,
        0,
        0,
        0,
        now
    );
    if(!srk_runtime_resident_input_write_slot(
        SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE,
        srk_runtime_resident_input_slot
    )){
        srk_runtime_resident_input_restore_vector();
        srk_runtime_resident_input_armed = 0;
        return SRK_RUNTIME_RESIDENT_INPUT_PROOF_ERR_INSTALL_WRITE;
    }

    srk_runtime_resident_input_callbacks = 0;
    srk_runtime_resident_input_samples = 0;
    srk_runtime_resident_input_last_sample_timer = now;
    srk_runtime_input_reset(&srk_runtime_resident_input_state);
    srk_runtime_resident_input_installed = 1;
    return SRK_RUNTIME_RESIDENT_INPUT_PROOF_OK;
}


void srk_runtime_resident_input_proof_tick(void)
{
    u32 now;
    u16 buttons;
    int event;

    if(!srk_runtime_resident_input_armed ||
       !srk_runtime_resident_input_installed ||
       srk_runtime_resident_input_activated)
        return;

    srk_runtime_resident_input_callbacks += 1;
    now = SS_TIMER;
    if((u32)(now - srk_runtime_resident_input_last_sample_timer) <
       SRK_RUNTIME_RESIDENT_INPUT_SAMPLE_US)
        return;

    srk_runtime_resident_input_last_sample_timer = now;
    buttons = *(volatile u16*)SRK_RUNTIME_RESIDENT_INPUT_PAD1;
    srk_runtime_resident_input_samples += 1;
    event = srk_runtime_input_sample(
        &srk_runtime_resident_input_state,
        (unsigned int)buttons
    );
    if(event != SRK_RUNTIME_INPUT_OPEN_MENU)
        return;

    /* Latch before the single persistent write so nested/repeated activation is inert. */
    srk_runtime_resident_input_activated = 1;
    srk_runtime_resident_input_build_slot(
        srk_runtime_resident_input_slot,
        SRK_RUNTIME_RESIDENT_INPUT_STAGE_ACTIVATED,
        buttons,
        srk_runtime_resident_input_callbacks,
        srk_runtime_resident_input_samples,
        now
    );
    srk_runtime_resident_input_write_slot(
        SRK_RUNTIME_RESIDENT_INPUT_SLOT_SIZE * 2,
        srk_runtime_resident_input_slot
    );

    /* One input proof is enough. Restore the original HBLANK-IN BIOS path. */
    srk_runtime_resident_input_restore_vector();
    srk_runtime_resident_input_installed = 0;
    srk_runtime_resident_input_armed = 0;
}
