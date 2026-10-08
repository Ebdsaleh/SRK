#include "main.h"
#include "vdp2.h"
#include "srk_runtime_execution_proof.h"


#define SRK_RUNTIME_PROOF_IP_BASE             0x06002000u
#define SRK_RUNTIME_PROOF_FIRST_READ_OFFSET   0x000000f0u
#define SRK_RUNTIME_PROOF_WRAMH_END           0x06100000u
#define SRK_RUNTIME_PROOF_HOOK_SAMPLES        600
#define SRK_RUNTIME_PROOF_BLACK_FRAMES        120


extern int game_break_pc;
extern void (*game_break_handle)(REGS *reg);


static int srk_runtime_proof_armed = 0;
static int srk_runtime_proof_entry_seen = 0;
static int srk_runtime_proof_hook_samples = 0;
static int srk_runtime_proof_beacon_done = 0;


static void srk_runtime_execution_proof_entry_handler(REGS *reg)
{
    (void)reg;

    /* One-shot UBR gate: no SD I/O and no Work RAM capture. */
    set_break_pc(0, 0);
    game_break_pc = 0;
    game_break_handle = 0;

    if(srk_runtime_proof_armed){
        srk_runtime_proof_entry_seen = 1;
        srk_runtime_proof_hook_samples = 0;
    }
}


static void srk_runtime_execution_proof_black_beacon(void)
{
    unsigned short saved_tvmd;
    int frame;

    /*
     * Disable only the VDP2 display-enable bit for a clearly visible proof.
     * Restore the exact TVMD value before returning to the title callback.
     */
    WaitForVBLANKIn();
    saved_tvmd = TVMD;
    TVMD = (unsigned short)(saved_tvmd & (unsigned short)(~DISP));

    for(frame=0; frame<SRK_RUNTIME_PROOF_BLACK_FRAMES; frame++){
        WaitForVBLANKOut();
        WaitForVBLANKIn();
    }

    TVMD = saved_tvmd;
}


int srk_runtime_execution_proof_arm(void)
{
    srk_runtime_proof_armed = 1;
    srk_runtime_proof_entry_seen = 0;
    srk_runtime_proof_hook_samples = 0;
    srk_runtime_proof_beacon_done = 0;
    return SRK_RUNTIME_EXECUTION_PROOF_OK;
}


int srk_runtime_execution_proof_prepare(void)
{
    unsigned int first_read_pc;

    if(!srk_runtime_proof_armed)
        return 0;

    /* Do not steal an independently configured SAROO/SRK breakpoint. */
    if(game_break_pc || game_break_handle){
        srk_runtime_proof_armed = 0;
        srk_runtime_proof_entry_seen = 0;
        return SRK_RUNTIME_EXECUTION_PROOF_ERR_BREAK_BUSY;
    }

    first_read_pc = BE32(
        (void*)(SRK_RUNTIME_PROOF_IP_BASE + SRK_RUNTIME_PROOF_FIRST_READ_OFFSET)
    );
    if(first_read_pc<SRK_RUNTIME_PROOF_IP_BASE ||
       first_read_pc>=SRK_RUNTIME_PROOF_WRAMH_END ||
       (first_read_pc&1u)!=0u){
        srk_runtime_proof_armed = 0;
        srk_runtime_proof_entry_seen = 0;
        game_break_pc = 0;
        game_break_handle = 0;
        return SRK_RUNTIME_EXECUTION_PROOF_ERR_FIRST_READ;
    }

    game_break_pc = (int)first_read_pc;
    game_break_handle = srk_runtime_execution_proof_entry_handler;
    return 1;
}


void srk_runtime_execution_proof_on_controller_hook(void)
{
    if(!srk_runtime_proof_armed ||
       !srk_runtime_proof_entry_seen ||
       srk_runtime_proof_beacon_done)
        return;

    srk_runtime_proof_hook_samples += 1;
    if(srk_runtime_proof_hook_samples<SRK_RUNTIME_PROOF_HOOK_SAMPLES)
        return;

    /*
     * Reaching this point proves that the SAROO cdp_hook continued to call SRK
     * after the title crossed its 1st-read entry breakpoint. The beacon is
     * intentionally input-independent so controller semantics cannot hide the
     * result.
     */
    srk_runtime_proof_beacon_done = 1;
    srk_runtime_execution_proof_black_beacon();
    srk_runtime_proof_armed = 0;
    srk_runtime_proof_entry_seen = 0;
}
