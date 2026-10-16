#include "srk_diag_midi_test.h"


static const char *srk_diag_midi_family_names[SRK_DIAG_MIDI_FAMILY_COUNT] = {
    "Piano", "Chromatic Percussion", "Organ", "Guitar",
    "Bass", "Strings", "Ensemble", "Brass",
    "Reed", "Pipe", "Synth Lead", "Synth Pad",
    "Synth Effects", "Ethnic", "Percussive", "Sound Effects"
};


static const char *srk_diag_midi_program_names[SRK_DIAG_MIDI_PROGRAM_COUNT] = {
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar nylon", "Acoustic Guitar steel", "Electric Guitar jazz", "Electric Guitar clean",
    "Electric Guitar muted", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass finger", "Electric Bass pick", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 square", "Lead 2 sawtooth", "Lead 3 calliope", "Lead 4 chiff",
    "Lead 5 charang", "Lead 6 voice", "Lead 7 fifths", "Lead 8 bass+lead",
    "Pad 1 new age", "Pad 2 warm", "Pad 3 polysynth", "Pad 4 choir",
    "Pad 5 bowed", "Pad 6 metallic", "Pad 7 halo", "Pad 8 sweep",
    "FX 1 rain", "FX 2 soundtrack", "FX 3 crystal", "FX 4 atmosphere",
    "FX 5 brightness", "FX 6 goblins", "FX 7 echoes", "FX 8 sci-fi",
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bag Pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot"
};


void srk_diag_midi_test_reset(SRK_DIAG_MIDI_TEST_STATE *state)
{
    unsigned int i;

    if(!state)
        return;
    state->program = 0u;
    state->channel = SRK_DIAG_MIDI_DEFAULT_CHANNEL;
    state->note = SRK_DIAG_MIDI_DEFAULT_NOTE;
    state->velocity = SRK_DIAG_MIDI_DEFAULT_VELOCITY;
    state->pan = SRK_DIAG_MIDI_DEFAULT_PAN;
    state->note_active = 0u;
    state->prepared = 0u;
    state->last_error = 0u;
    state->last_hold_us = 0u;
    for(i=0u; i<4u; i++)
        state->review_bits[i] = 0u;
    state->review_count = 0u;
    state->persisted_review_count = 0u;
}


void srk_diag_midi_test_move_program(SRK_DIAG_MIDI_TEST_STATE *state, int delta)
{
    int value;

    if(!state || delta == 0)
        return;
    value = (int)state->program + delta;
    while(value < 0)
        value += (int)SRK_DIAG_MIDI_PROGRAM_COUNT;
    while(value >= (int)SRK_DIAG_MIDI_PROGRAM_COUNT)
        value -= (int)SRK_DIAG_MIDI_PROGRAM_COUNT;
    state->program = (srk_u8)value;
    state->prepared = 0u;
    state->last_error = 0u;
}


void srk_diag_midi_test_move_pan(SRK_DIAG_MIDI_TEST_STATE *state, int delta)
{
    int value;

    if(!state || delta == 0)
        return;
    value = (int)state->pan + delta;
    if(value < 0)
        value = 0;
    if(value > 127)
        value = 127;
    state->pan = (srk_u8)value;
}


unsigned int srk_diag_midi_test_family(const SRK_DIAG_MIDI_TEST_STATE *state)
{
    if(!state)
        return 0u;
    return (unsigned int)state->program / SRK_DIAG_MIDI_PROGRAMS_PER_FAMILY;
}


const char *srk_diag_midi_program_name(unsigned int program)
{
    if(program >= SRK_DIAG_MIDI_PROGRAM_COUNT)
        return "Unknown";
    return srk_diag_midi_program_names[program];
}


const char *srk_diag_midi_family_name(unsigned int family)
{
    if(family >= SRK_DIAG_MIDI_FAMILY_COUNT)
        return "Unknown";
    return srk_diag_midi_family_names[family];
}


int srk_diag_midi_review_marked(const SRK_DIAG_MIDI_TEST_STATE *state, unsigned int program)
{
    unsigned int word;
    unsigned int bit;

    if(!state || program >= SRK_DIAG_MIDI_PROGRAM_COUNT)
        return 0;
    word = program >> 5;
    bit = program & 31u;
    return (state->review_bits[word] & (1ul << bit)) != 0u;
}


int srk_diag_midi_mark_review(SRK_DIAG_MIDI_TEST_STATE *state)
{
    unsigned int word;
    unsigned int bit;
    srk_u32 mask;

    if(!state)
        return 0;
    word = (unsigned int)state->program >> 5;
    bit = (unsigned int)state->program & 31u;
    mask = (srk_u32)(1ul << bit);
    if(state->review_bits[word] & mask)
        return 0;
    state->review_bits[word] |= mask;
    state->review_count += 1u;
    return 1;
}
