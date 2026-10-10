#include "srk_saturn_midi_68k_silent_batch_runtime.h"
#include "srk_saturn_midi_68k_command_state.h"
#include "srk_saturn_midi_mailbox.h"

static int srk_saturn_midi_68k_silent_batch_runtime_ops_valid(
    const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *ops
)
{
    return ops &&
        ops->stop_sound_cpu &&
        ops->install_program &&
        ops->publish_preload &&
        ops->verify_preload &&
        ops->start_sound_cpu &&
        ops->read_mailbox_word &&
        ops->read_sound_word;
}

unsigned int srk_saturn_midi_68k_silent_batch_protocol_begin(
    const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *ops
)
{
    if(!srk_saturn_midi_68k_silent_batch_runtime_ops_valid(ops))
        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;
    if(!ops->stop_sound_cpu())
        return SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED;
    if(!ops->install_program())
        return SRK_MIDI_68K_RUNTIME_INSTALL_FAILED;
    ops->publish_preload();
    if(!ops->verify_preload())
        return SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED;
    if(!ops->start_sound_cpu())
        return SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED;
    return SRK_MIDI_68K_RUNTIME_RUNNING;
}
