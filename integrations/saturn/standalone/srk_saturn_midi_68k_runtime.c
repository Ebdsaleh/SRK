#include "srk_saturn_midi_68k_runtime.h"
#include "srk_saturn_midi_generated.h"
#include "srk_saturn_midi_mailbox.h"

static int srk_saturn_midi_68k_runtime_ops_valid(
    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops
)
{
    return ops &&
        ops->stop_sound_cpu &&
        ops->install_program &&
        ops->publish_preload &&
        ops->verify_preload &&
        ops->start_sound_cpu &&
        ops->read_mailbox_word;
}

unsigned int srk_saturn_midi_68k_protocol_begin(
    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops
)
{
    if(!srk_saturn_midi_68k_runtime_ops_valid(ops))
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

unsigned int srk_saturn_midi_68k_protocol_poll(
    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,
    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry
)
{
    unsigned short flags;
    unsigned short read_sequence;
    unsigned short read_index;
    unsigned short last_error;

    if(!srk_saturn_midi_68k_runtime_ops_valid(ops))
        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;

    flags = ops->read_mailbox_word(SRK_MIDI_MB_FLAGS);
    read_sequence = ops->read_mailbox_word(SRK_MIDI_MB_READ_SEQUENCE);
    read_index = ops->read_mailbox_word(SRK_MIDI_MB_READ_INDEX);
    last_error = ops->read_mailbox_word(SRK_MIDI_MB_LAST_ERROR);

    if(telemetry){
        telemetry->flags = flags;
        telemetry->read_sequence = read_sequence;
        telemetry->read_index = read_index;
        telemetry->last_error = last_error;
    }

    if(last_error != 0u)
        return SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;
    if((flags & SRK_MIDI_MAILBOX_FLAG_READY) != 0u &&
       read_sequence == SRK_MIDI_PRELOAD_WRITE_SEQUENCE &&
       read_index == 1u)
        return SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;
    return SRK_MIDI_68K_RUNTIME_RUNNING;
}
