#include "main.h"
#include "vdp2.h"
#include "srk_runtime_modal_red.h"
#include "srk_runtime_video_canary.h"


#define SRK_RUNTIME_MODAL_RED_MAX_FRAMES 600


int srk_runtime_modal_red_run(
    SRK_RUNTIME_INPUT_STATE *input_state,
    SRK_RUNTIME_MENU_STATE *menu_state,
    const SRK_RUNTIME_VIDEO_STATE *video_state,
    SRK_RUNTIME_CONTROLLER_REFRESH refresh_controller,
    volatile unsigned short *controller_buttons
)
{
    int frame;
    int event;
    int result;
    unsigned int buttons;

    if(!input_state || !menu_state || !video_state)
        return SRK_RUNTIME_MODAL_RED_FAILED;
    if(!refresh_controller || !controller_buttons || !video_state->valid)
        return SRK_RUNTIME_MODAL_RED_FAILED;

    if(!srk_runtime_video_canary_apply_solid_red(video_state))
        return SRK_RUNTIME_MODAL_RED_FAILED;

    result = SRK_RUNTIME_MODAL_RED_TIMEOUT;

    /*
     * The opening L+R event leaves input_state latched.  Sampling the same
     * state here naturally requires both shoulders to be released before a
     * second 50-sample L+R hold can dismiss the modal shell.
     *
     * Keep the title's main path blocked in the controller hook, but invoke
     * the original BIOS controller routine once per display frame so fresh
     * controller samples continue to arrive.  The 600-frame timeout is a
     * first-hardware-test fail-safe; it is not intended as final menu policy.
     */
    WaitForVBLANKIn();
    for(frame=0; frame<SRK_RUNTIME_MODAL_RED_MAX_FRAMES; frame++){
        WaitForVBLANKOut();
        WaitForVBLANKIn();

        refresh_controller();
        buttons = (unsigned int)(*controller_buttons);
        event = srk_runtime_input_sample(input_state, buttons);
        if(event==SRK_RUNTIME_INPUT_OPEN_MENU){
            result = SRK_RUNTIME_MODAL_RED_DISMISSED;
            break;
        }
    }

    if(!srk_runtime_video_canary_restore(video_state))
        result = SRK_RUNTIME_MODAL_RED_FAILED;

    srk_runtime_menu_state_reset(menu_state);
    return result;
}
