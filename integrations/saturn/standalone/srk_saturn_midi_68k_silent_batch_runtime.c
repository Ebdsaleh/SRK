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

unsigned int srk_saturn_midi_68k_silent_batch_protocol_poll(
    const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *ops,
    SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY *telemetry
)
{
    unsigned short flags;
    unsigned short read_sequence;
    unsigned short read_index;
    unsigned short last_error;
    unsigned short telemetry_magic;
    unsigned short telemetry_version;
    unsigned short processed_records;
    unsigned short current_record;
    unsigned short final_time_hi;
    unsigned short final_time_lo;
    unsigned short state_ready;

    if(!srk_saturn_midi_68k_silent_batch_runtime_ops_valid(ops))
        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;

    flags = ops->read_mailbox_word(SRK_MIDI_MB_FLAGS);
    read_sequence = ops->read_mailbox_word(SRK_MIDI_MB_READ_SEQUENCE);
    read_index = ops->read_mailbox_word(SRK_MIDI_MB_READ_INDEX);
    last_error = ops->read_mailbox_word(SRK_MIDI_MB_LAST_ERROR);
    telemetry_magic = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC_OFFSET);
    telemetry_version = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION_OFFSET);
    processed_records = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET);
    current_record = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET);
    final_time_hi = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_HI_OFFSET);
    final_time_lo = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_LO_OFFSET);
    state_ready = ops->read_sound_word(SRK_MIDI_68K_TELEMETRY_ADDRESS + SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET);

    if(telemetry){
        telemetry->flags = flags;
        telemetry->read_sequence = read_sequence;
        telemetry->read_index = read_index;
        telemetry->last_error = last_error;
        telemetry->telemetry_magic = telemetry_magic;
        telemetry->telemetry_version = telemetry_version;
        telemetry->processed_records = processed_records;
        telemetry->current_record = current_record;
        telemetry->final_time_hi = final_time_hi;
        telemetry->final_time_lo = final_time_lo;
        telemetry->state_ready = state_ready;
    }

    if(last_error != 0u)
        return SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;

    if((flags & SRK_MIDI_MAILBOX_FLAG_READY) != 0u &&
       read_sequence == SRK_MIDI_PRELOAD_WRITE_SEQUENCE &&
       read_index == SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS &&
       telemetry_magic == SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC &&
       telemetry_version == SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION &&
       processed_records == SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS &&
       current_record == SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS &&
       state_ready == 1u)
        return SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;

    return SRK_MIDI_68K_RUNTIME_RUNNING;
}
