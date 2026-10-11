"""Regression contracts for R23 monophonic MIDI -> SCSP allocation."""

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_OWNERSHIP_END,
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_HOLD_US,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_COMMON_ADDRESS,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_SCSP_SLOT_BYTES,
    SATURN_MIDI_68K_SCSP_SLOT_COUNT,
    SATURN_MIDI_68K_VOICE_ERROR_BUSY,
    SATURN_MIDI_68K_VOICE_MAGIC,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
    build_srk_saturn_midi_68k_pitch_table,
    build_srk_saturn_midi_68k_r23_first_note_program,
    build_srk_saturn_midi_68k_r23_first_note_snapshot,
    build_srk_saturn_midi_68k_r23_waveform_words,
    default_saturn_midi_68k_voice_allocator_state,
    midi_note_to_scsp_pitch,
    midi_velocity_to_scsp_mixer,
    note_on_srk_saturn_midi_68k_voice,
    pack_srk_saturn_midi_68k_voice_state_words,
    render_srk_saturn_midi_68k_voice_state_header,
    validate_srk_saturn_midi_68k_voice_layout,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KVoiceAllocatorTests(unittest.TestCase):
    def test_scsp_map_and_r23_sound_ram_ownership_are_exact(self):
        validate_srk_saturn_midi_68k_voice_layout()
        self.assertEqual(SATURN_MIDI_68K_SCSP_REGISTER_BASE, 0x00100000)
        self.assertEqual(SATURN_MIDI_68K_SCSP_COMMON_ADDRESS, 0x00100400)
        self.assertEqual(SATURN_MIDI_68K_SCSP_SLOT_COUNT, 32)
        self.assertEqual(SATURN_MIDI_68K_SCSP_SLOT_BYTES, 0x20)
        self.assertEqual(SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS, 0x2000)
        self.assertEqual(SATURN_MIDI_68K_VOICE_STATE_ADDRESS, 0x2100)
        self.assertEqual(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 0x2200)
        self.assertEqual(SATURN_MIDI_68K_AUDIO_OWNERSHIP_END, 0x2300)

    def test_pitch_encoding_matches_existing_octave_proofs(self):
        self.assertEqual(midi_note_to_scsp_pitch(48), 0x7800)
        self.assertEqual(midi_note_to_scsp_pitch(60), 0x0000)
        self.assertEqual(midi_note_to_scsp_pitch(72), 0x0800)
        table = build_srk_saturn_midi_68k_pitch_table()
        self.assertEqual(len(table), 128)
        self.assertEqual(table[60], 0x0000)

    def test_waveform_reuses_reviewed_100_sample_loop(self):
        words = build_srk_saturn_midi_68k_r23_waveform_words()
        self.assertEqual(len(words), 101)
        self.assertEqual(words[:50], (0x2000,) * 50)
        self.assertEqual(words[50:100], (0xE000,) * 50)
        self.assertEqual(words[100], 0x2000)

    def test_first_note_program_is_one_second_monophonic_hold(self):
        program = build_srk_saturn_midi_68k_r23_first_note_program()
        self.assertEqual(len(program.records), 2)
        on, off = program.records
        self.assertEqual(
            (on.time_us, on.opcode, on.channel, on.data0, on.data1),
            (0, SaturnMidiOpcode.NOTE_ON, SATURN_MIDI_68K_R23_CHANNEL, SATURN_MIDI_68K_R23_NOTE, SATURN_MIDI_68K_R23_VELOCITY),
        )
        self.assertEqual(
            (off.time_us, off.opcode, off.channel, off.data0),
            (SATURN_MIDI_68K_R23_HOLD_US, SaturnMidiOpcode.NOTE_OFF, SATURN_MIDI_68K_R23_CHANNEL, SATURN_MIDI_68K_R23_NOTE),
        )
        self.assertEqual(program.duration_us, 1_000_000)

    def test_first_note_allocates_keys_and_releases_slot_zero(self):
        snapshot = build_srk_saturn_midi_68k_r23_first_note_snapshot()
        on = snapshot.after_note_on
        slot = on.owned_slot
        self.assertTrue(slot.active)
        self.assertEqual(slot.slot, 0)
        self.assertEqual(slot.channel, 3)
        self.assertEqual(slot.note, 60)
        self.assertEqual(slot.velocity, 100)
        self.assertEqual(slot.generation, 1)
        self.assertEqual(slot.pitch, 0x0000)
        self.assertEqual(slot.mixer, midi_velocity_to_scsp_mixer(100))
        self.assertEqual(slot.control, SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB)
        self.assertEqual(on.key_on_count, 1)
        self.assertEqual(on.key_off_count, 0)

        off = snapshot.after_note_off
        self.assertFalse(off.owned_slot.active)
        self.assertEqual(off.owned_slot.velocity, 0)
        self.assertEqual(off.owned_slot.mixer, 0)
        self.assertEqual(off.key_on_count, 1)
        self.assertEqual(off.key_off_count, 1)
        self.assertEqual(off.last_error, 0)

    def test_r23_does_not_steal_an_active_different_note(self):
        state = default_saturn_midi_68k_voice_allocator_state()
        state = note_on_srk_saturn_midi_68k_voice(state, 3, 60, 100)
        busy = note_on_srk_saturn_midi_68k_voice(state, 3, 64, 100)
        self.assertEqual(busy.last_error, SATURN_MIDI_68K_VOICE_ERROR_BUSY)
        self.assertEqual(busy.owned_slot.note, 60)
        self.assertTrue(busy.owned_slot.active)
        self.assertEqual(busy.key_on_count, 1)

    def test_packed_voice_telemetry_and_header_are_stable(self):
        snapshot = build_srk_saturn_midi_68k_r23_first_note_snapshot()
        words = pack_srk_saturn_midi_68k_voice_state_words(snapshot.after_note_on)
        self.assertEqual(len(words), 15)
        self.assertEqual(words[0], SATURN_MIDI_68K_VOICE_MAGIC)
        self.assertEqual(words[3], 1)
        self.assertEqual(words[4:8], (0, 3, 60, 100))
        self.assertEqual(words[12:15], (1, 0, 0))

        header = render_srk_saturn_midi_68k_voice_state_header()
        self.assertIn("SRK_MIDI_68K_SCSP_REGISTER_BASE 0x00100000UL", header)
        self.assertIn("SRK_MIDI_68K_VOICE_STATE_ADDRESS 0x00002100UL", header)
        self.assertIn("SRK_MIDI_68K_PITCH_TABLE_ADDRESS 0x00002200UL", header)
        self.assertIn("SRK_MIDI_68K_R23_HOLD_US 1000000UL", header)


if __name__ == "__main__":
    unittest.main()
