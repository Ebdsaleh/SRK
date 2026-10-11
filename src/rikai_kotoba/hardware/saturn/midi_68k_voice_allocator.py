"""R23 deterministic MIDI -> SCSP voice-allocation reference model.

R22A physically accepted the resident multi-batch/timestamp service and complete
persistent MIDI state on a real Saturn.  R23 is the first sound-producing
milestone.  This module is host/model code only: it defines the exact Sound-RAM
voice-state contract, SCSP slot fields and deterministic monophonic allocation
policy that the next resident MC68EC000 image must match.

The first hardware proof intentionally owns slot 0 only and performs no voice
stealing.  That keeps first-audio risk separate from later polyphony policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_SCSP_REGISTER_BASE = 0x00100000
SATURN_MIDI_68K_SCSP_COMMON_ADDRESS = 0x00100400
SATURN_MIDI_68K_SCSP_SLOT_COUNT = 32
SATURN_MIDI_68K_SCSP_SLOT_BYTES = 0x20
SATURN_MIDI_68K_SCSP_SLOT_WORDS = SATURN_MIDI_68K_SCSP_SLOT_BYTES // 2

SATURN_MIDI_68K_SCSP_SLOT_CONTROL = 0
SATURN_MIDI_68K_SCSP_SLOT_SA_LOW = 1
SATURN_MIDI_68K_SCSP_SLOT_LSA = 2
SATURN_MIDI_68K_SCSP_SLOT_LEA = 3
SATURN_MIDI_68K_SCSP_SLOT_EG1 = 4
SATURN_MIDI_68K_SCSP_SLOT_EG2 = 5
SATURN_MIDI_68K_SCSP_SLOT_TL = 6
SATURN_MIDI_68K_SCSP_SLOT_FM = 7
SATURN_MIDI_68K_SCSP_SLOT_PITCH = 8
SATURN_MIDI_68K_SCSP_SLOT_LFO = 9
SATURN_MIDI_68K_SCSP_SLOT_DSP = 10
SATURN_MIDI_68K_SCSP_SLOT_MIXER = 11

SATURN_MIDI_68K_SCSP_CONTROL_KYONEX = 0x1000
SATURN_MIDI_68K_SCSP_CONTROL_KYONB = 0x0800
SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP = 0x0020
SATURN_MIDI_68K_SCSP_SOUND_DIRECT = 0x0100
SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE = 0x020F

SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS = 0x00002000
SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END = 100
SATURN_MIDI_68K_AUDIO_SAMPLE_POSITIVE = 0x2000
SATURN_MIDI_68K_AUDIO_SAMPLE_NEGATIVE = 0xE000

SATURN_MIDI_68K_VOICE_STATE_ADDRESS = 0x00002100
SATURN_MIDI_68K_VOICE_STATE_BYTES = 0x00000100
SATURN_MIDI_68K_PITCH_TABLE_ADDRESS = 0x00002200
SATURN_MIDI_68K_PITCH_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_AUDIO_OWNERSHIP_END = 0x00002300

SATURN_MIDI_68K_VOICE_MAGIC = 0x5641  # "VA"
SATURN_MIDI_68K_VOICE_VERSION = 1
SATURN_MIDI_68K_R23_OWNED_SLOTS = 1
SATURN_MIDI_68K_R23_SLOT = 0
SATURN_MIDI_68K_R23_CHANNEL = 3
SATURN_MIDI_68K_R23_NOTE = 60
SATURN_MIDI_68K_R23_VELOCITY = 100
SATURN_MIDI_68K_R23_HOLD_US = 1_000_000

SATURN_MIDI_68K_VOICE_ERROR_NONE = 0
SATURN_MIDI_68K_VOICE_ERROR_BUSY = 1
SATURN_MIDI_68K_VOICE_ERROR_RANGE = 2

# Word offsets inside the 0x2100 voice-state block.
SATURN_MIDI_68K_VOICE_MAGIC_WORD = 0
SATURN_MIDI_68K_VOICE_VERSION_WORD = 1
SATURN_MIDI_68K_VOICE_OWNED_SLOTS_WORD = 2
SATURN_MIDI_68K_VOICE_ACTIVE_WORD = 3
SATURN_MIDI_68K_VOICE_SLOT_WORD = 4
SATURN_MIDI_68K_VOICE_CHANNEL_WORD = 5
SATURN_MIDI_68K_VOICE_NOTE_WORD = 6
SATURN_MIDI_68K_VOICE_VELOCITY_WORD = 7
SATURN_MIDI_68K_VOICE_GENERATION_WORD = 8
SATURN_MIDI_68K_VOICE_PITCH_WORD = 9
SATURN_MIDI_68K_VOICE_MIXER_WORD = 10
SATURN_MIDI_68K_VOICE_CONTROL_WORD = 11
SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD = 12
SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD = 13
SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD = 14
SATURN_MIDI_68K_VOICE_STATE_WORDS = 15


class SaturnMidi68KVoiceAllocatorError(RuntimeError):
    """Raised when R23 voice allocation or SCSP state violates its contract."""


@dataclass(frozen=True)
class SaturnMidi68KScspSlotState:
    slot: int
    active: bool
    channel: int
    note: int
    velocity: int
    generation: int
    source_address: int
    loop_start: int
    loop_end: int
    pitch: int
    mixer: int
    control: int


@dataclass(frozen=True)
class SaturnMidi68KVoiceAllocatorState:
    slots: tuple[SaturnMidi68KScspSlotState, ...]
    generation: int
    key_on_count: int
    key_off_count: int
    last_error: int

    @property
    def owned_slot(self) -> SaturnMidi68KScspSlotState:
        return self.slots[SATURN_MIDI_68K_R23_SLOT]


@dataclass(frozen=True)
class SaturnMidi68KR23FirstNoteSnapshot:
    after_note_on: SaturnMidi68KVoiceAllocatorState
    after_note_off: SaturnMidi68KVoiceAllocatorState


def validate_srk_saturn_midi_68k_voice_layout() -> None:
    """Prove R23 Sound-RAM ownership is bounded below the resident program."""

    sample_end = SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS + (
        SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END + 1
    ) * 2
    if sample_end > SATURN_MIDI_68K_VOICE_STATE_ADDRESS:
        raise SaturnMidi68KVoiceAllocatorError("R23 waveform overlaps voice state")
    if SATURN_MIDI_68K_VOICE_STATE_ADDRESS + SATURN_MIDI_68K_VOICE_STATE_BYTES > SATURN_MIDI_68K_PITCH_TABLE_ADDRESS:
        raise SaturnMidi68KVoiceAllocatorError("R23 voice state overlaps pitch table")
    if SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + SATURN_MIDI_68K_PITCH_TABLE_BYTES != SATURN_MIDI_68K_AUDIO_OWNERSHIP_END:
        raise SaturnMidi68KVoiceAllocatorError("R23 pitch-table ownership boundary changed")
    if SATURN_MIDI_68K_AUDIO_OWNERSHIP_END > 0x00004000:
        raise SaturnMidi68KVoiceAllocatorError("R23 audio data overlaps resident program envelope")
    if SATURN_MIDI_68K_SCSP_SLOT_COUNT != 32 or SATURN_MIDI_68K_SCSP_SLOT_BYTES != 0x20:
        raise SaturnMidi68KVoiceAllocatorError("SCSP slot geometry changed")


def build_srk_saturn_midi_68k_r23_waveform_words() -> tuple[int, ...]:
    """Return the already-reviewed deterministic 100-sample square-wave loop."""

    words = [SATURN_MIDI_68K_AUDIO_SAMPLE_POSITIVE] * 50
    words.extend([SATURN_MIDI_68K_AUDIO_SAMPLE_NEGATIVE] * 50)
    words.append(SATURN_MIDI_68K_AUDIO_SAMPLE_POSITIVE)
    if len(words) != SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END + 1:
        raise SaturnMidi68KVoiceAllocatorError("R23 waveform length changed")
    return tuple(words)


def midi_note_to_scsp_pitch(note: int, *, root_note: int = 60) -> int:
    """Encode one MIDI note as SCSP OCT/FNS relative to root_note at 44.1 kHz.

    This keeps the physically reviewed C4/C5/C6 relationship: note 48 ->
    0x7800, note 60 -> 0x0000, note 72 -> 0x0800.
    """

    if note < 0 or note > 127 or root_note < 0 or root_note > 127:
        raise SaturnMidi68KVoiceAllocatorError("MIDI note is outside 0..127")
    delta = note - root_note
    octave = delta // 12
    semitone = delta - octave * 12
    if octave < -8 or octave > 7:
        raise SaturnMidi68KVoiceAllocatorError("SCSP OCT field cannot represent requested note")
    ratio = 2.0 ** (semitone / 12.0)
    fns = int(((ratio - 1.0) * 1024.0) + 0.5)
    if fns < 0:
        fns = 0
    if fns > 0x03FF:
        fns = 0x03FF
    return ((octave & 0x0F) << 11) | fns


def build_srk_saturn_midi_68k_pitch_table() -> tuple[int, ...]:
    table = tuple(midi_note_to_scsp_pitch(note) for note in range(128))
    if len(table) != 128:
        raise SaturnMidi68KVoiceAllocatorError("R23 pitch table size changed")
    return table


def midi_pan_to_scsp_pan(pan: int) -> int:
    """Map MIDI 0..127 to the SCSP direct-output pan field.

    R23 physical proof uses center (64 -> 0).  The complete deterministic map is
    retained here for later polyphonic/controller work.
    """

    if pan < 0 or pan > 127:
        raise SaturnMidi68KVoiceAllocatorError("MIDI pan is outside 0..127")
    if pan == 64:
        return 0
    if pan < 64:
        amount = ((64 - pan) * 15 + 63) // 64
        return 0x10 | min(15, amount)
    amount = ((pan - 64) * 15 + 62) // 63
    return min(15, amount)


def midi_velocity_to_scsp_mixer(velocity: int, *, pan: int = 64) -> int:
    """Return direct-output level/pan without enabling DSP routing."""

    if velocity < 0 or velocity > 127:
        raise SaturnMidi68KVoiceAllocatorError("MIDI velocity is outside 0..127")
    if velocity == 0:
        level = 0
    else:
        level = max(1, min(7, (velocity * 7 + 126) // 127))
    return (level << 13) | ((midi_pan_to_scsp_pan(pan) & 0x1F) << 8)


def _inactive_slot(slot: int) -> SaturnMidi68KScspSlotState:
    return SaturnMidi68KScspSlotState(
        slot=slot,
        active=False,
        channel=0xFFFF,
        note=0xFFFF,
        velocity=0,
        generation=0,
        source_address=SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
        loop_start=0,
        loop_end=SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END,
        pitch=0,
        mixer=0,
        control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    )


def default_saturn_midi_68k_voice_allocator_state() -> SaturnMidi68KVoiceAllocatorState:
    validate_srk_saturn_midi_68k_voice_layout()
    return SaturnMidi68KVoiceAllocatorState(
        slots=tuple(_inactive_slot(slot) for slot in range(SATURN_MIDI_68K_SCSP_SLOT_COUNT)),
        generation=0,
        key_on_count=0,
        key_off_count=0,
        last_error=SATURN_MIDI_68K_VOICE_ERROR_NONE,
    )


def _next_generation(value: int) -> int:
    result = (value + 1) & 0xFFFF
    return result if result else 1


def note_on_srk_saturn_midi_68k_voice(
    state: SaturnMidi68KVoiceAllocatorState,
    channel: int,
    note: int,
    velocity: int,
    *,
    pan: int = 64,
) -> SaturnMidi68KVoiceAllocatorState:
    """Allocate/retrigger R23 slot 0. Different active notes are not stolen."""

    if channel < 0 or channel > 15 or note < 0 or note > 127 or velocity < 0 or velocity > 127:
        return replace(state, last_error=SATURN_MIDI_68K_VOICE_ERROR_RANGE)
    if velocity == 0:
        return note_off_srk_saturn_midi_68k_voice(state, channel, note)

    slot = state.owned_slot
    if slot.active and (slot.channel != channel or slot.note != note):
        return replace(state, last_error=SATURN_MIDI_68K_VOICE_ERROR_BUSY)

    generation = _next_generation(state.generation)
    new_slot = replace(
        slot,
        active=True,
        channel=channel,
        note=note,
        velocity=velocity,
        generation=generation,
        pitch=midi_note_to_scsp_pitch(note),
        mixer=midi_velocity_to_scsp_mixer(velocity, pan=pan),
        control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    )
    slots = list(state.slots)
    slots[SATURN_MIDI_68K_R23_SLOT] = new_slot
    return SaturnMidi68KVoiceAllocatorState(
        slots=tuple(slots),
        generation=generation,
        key_on_count=state.key_on_count + 1,
        key_off_count=state.key_off_count,
        last_error=SATURN_MIDI_68K_VOICE_ERROR_NONE,
    )


def note_off_srk_saturn_midi_68k_voice(
    state: SaturnMidi68KVoiceAllocatorState,
    channel: int,
    note: int,
) -> SaturnMidi68KVoiceAllocatorState:
    """Release slot 0 only when the MIDI channel/note owns it."""

    if channel < 0 or channel > 15 or note < 0 or note > 127:
        return replace(state, last_error=SATURN_MIDI_68K_VOICE_ERROR_RANGE)
    slot = state.owned_slot
    if not slot.active or slot.channel != channel or slot.note != note:
        return state

    new_slot = replace(
        slot,
        active=False,
        velocity=0,
        mixer=0,
        control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    )
    slots = list(state.slots)
    slots[SATURN_MIDI_68K_R23_SLOT] = new_slot
    return SaturnMidi68KVoiceAllocatorState(
        slots=tuple(slots),
        generation=state.generation,
        key_on_count=state.key_on_count,
        key_off_count=state.key_off_count + 1,
        last_error=SATURN_MIDI_68K_VOICE_ERROR_NONE,
    )


def build_srk_saturn_midi_68k_r23_first_note_program() -> SaturnMidiProgram:
    """Two-record proof: key C4 on at 0 us, hold, key it off at 1 s."""

    return SaturnMidiProgram(
        records=(
            SaturnMidiRecord(
                0,
                SaturnMidiOpcode.NOTE_ON,
                SATURN_MIDI_68K_R23_CHANNEL,
                SATURN_MIDI_68K_R23_NOTE,
                SATURN_MIDI_68K_R23_VELOCITY,
            ),
            SaturnMidiRecord(
                SATURN_MIDI_68K_R23_HOLD_US,
                SaturnMidiOpcode.NOTE_OFF,
                SATURN_MIDI_68K_R23_CHANNEL,
                SATURN_MIDI_68K_R23_NOTE,
                64,
            ),
        ),
        duration_us=SATURN_MIDI_68K_R23_HOLD_US,
    )


def build_srk_saturn_midi_68k_r23_first_note_snapshot() -> SaturnMidi68KR23FirstNoteSnapshot:
    program = build_srk_saturn_midi_68k_r23_first_note_program()
    state = default_saturn_midi_68k_voice_allocator_state()
    on = program.records[0]
    after_on = note_on_srk_saturn_midi_68k_voice(
        state, on.channel, on.data0, on.data1
    )
    off = program.records[1]
    after_off = note_off_srk_saturn_midi_68k_voice(
        after_on, off.channel, off.data0
    )
    return SaturnMidi68KR23FirstNoteSnapshot(after_note_on=after_on, after_note_off=after_off)


def pack_srk_saturn_midi_68k_voice_state_words(
    state: SaturnMidi68KVoiceAllocatorState,
) -> tuple[int, ...]:
    slot = state.owned_slot
    words = (
        SATURN_MIDI_68K_VOICE_MAGIC,
        SATURN_MIDI_68K_VOICE_VERSION,
        SATURN_MIDI_68K_R23_OWNED_SLOTS,
        int(slot.active),
        slot.slot,
        slot.channel,
        slot.note,
        slot.velocity,
        slot.generation,
        slot.pitch,
        slot.mixer,
        slot.control,
        state.key_on_count,
        state.key_off_count,
        state.last_error,
    )
    if len(words) != SATURN_MIDI_68K_VOICE_STATE_WORDS:
        raise SaturnMidi68KVoiceAllocatorError("R23 voice-state word count changed")
    return tuple(value & 0xFFFF for value in words)


def render_srk_saturn_midi_68k_voice_state_header() -> str:
    """Render C89 constants for SH-2 physical-proof inspection."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_VOICE_STATE_H",
            "#define SRK_SATURN_MIDI_68K_VOICE_STATE_H",
            "",
            f"#define SRK_MIDI_68K_SCSP_REGISTER_BASE 0x{SATURN_MIDI_68K_SCSP_REGISTER_BASE:08X}UL",
            f"#define SRK_MIDI_68K_SCSP_COMMON_ADDRESS 0x{SATURN_MIDI_68K_SCSP_COMMON_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_SCSP_SLOT_COUNT {SATURN_MIDI_68K_SCSP_SLOT_COUNT}u",
            f"#define SRK_MIDI_68K_SCSP_SLOT_BYTES 0x{SATURN_MIDI_68K_SCSP_SLOT_BYTES:02X}u",
            f"#define SRK_MIDI_68K_AUDIO_SAMPLE_ADDRESS 0x{SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_AUDIO_SAMPLE_LOOP_END {SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END}u",
            f"#define SRK_MIDI_68K_VOICE_STATE_ADDRESS 0x{SATURN_MIDI_68K_VOICE_STATE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_PITCH_TABLE_ADDRESS 0x{SATURN_MIDI_68K_PITCH_TABLE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R23_OWNED_SLOTS {SATURN_MIDI_68K_R23_OWNED_SLOTS}u",
            f"#define SRK_MIDI_68K_R23_SLOT {SATURN_MIDI_68K_R23_SLOT}u",
            f"#define SRK_MIDI_68K_R23_CHANNEL {SATURN_MIDI_68K_R23_CHANNEL}u",
            f"#define SRK_MIDI_68K_R23_NOTE {SATURN_MIDI_68K_R23_NOTE}u",
            f"#define SRK_MIDI_68K_R23_VELOCITY {SATURN_MIDI_68K_R23_VELOCITY}u",
            f"#define SRK_MIDI_68K_R23_HOLD_US {SATURN_MIDI_68K_R23_HOLD_US}UL",
            "",
            "#endif",
            "",
        )
    )
