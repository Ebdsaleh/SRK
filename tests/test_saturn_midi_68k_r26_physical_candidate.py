from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn import midi_68k_r24_physical_candidate as r24
from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_physical_candidate import (
    _R24_DEFINE,
    _r26_telemetry_block,
    derive_r26_double_impact_candidate_main,
    derive_r26_double_impact_candidate_menu,
    render_srk_saturn_midi_68k_r26_physical_proof_header,
    render_srk_saturn_midi_68k_r26_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_player import (
    render_saturn_midi_68k_r26_player_header,
    render_saturn_midi_68k_r26_player_source,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_r26_space_spectre_player_renders_all_287_batches():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    header = render_saturn_midi_68k_r26_player_header()
    source = render_saturn_midi_68k_r26_player_source(profile.program)
    assert "SRK_MIDI_R26_PLAYER_STATE" in header
    assert "#define SRK_R26_BATCH_COUNT 287u" in source
    assert "srk_r26_space_spectre_batch_287" in source


def test_r26_physical_proof_waits_for_release_drain_and_locks_real_song():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    header = render_srk_saturn_midi_68k_r26_physical_proof_header()
    source = render_srk_saturn_midi_68k_r26_physical_proof_source(profile, release_rate=16)
    assert "SRK_SATURN_MIDI_68K_R26_PHYSICAL_PROOF_STATE" in header
    assert "SRK_R26_DURATION_US 148093750UL" in source
    assert "voice_release_cancelled < 12u" in source
    assert "voice_peak_held != 10u" in source
    assert "voice_peak_owned != 16u" in source
    assert "state->telemetry.phase = 3u;" in source
    assert "srk_saturn_midi_stream_clock_publish(now_us);" in source
    assert "voice_owned_count == 0u" in source


def _minimal_r24_main() -> str:
    include = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        '#include "srk_saturn_midi_68k_r24_physical_proof.h"',
        "#endif",
    ))
    alias = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        "typedef SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE",
        "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
        "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u",
        '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K REAL SONG"',
        '#define SRK_MIDI_68K_PROOF_SUBTITLE "310 events - FRT clock - two SCSP voices"',
        '#define SRK_MIDI_68K_PROOF_SUCCESS "Song PASS: 310 events / peak voices 2"',
        "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r24_physical_proof_reset",
        "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r24_physical_proof_begin",
        "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r24_physical_proof_poll",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    success = "\n".join((
        "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
    ))
    return "\n".join((
        _R24_DEFINE,
        r24._R24_GUARD,
        r24._R24_GUARD,
        include,
        alias,
        r24._r24_telemetry_block(),
        success,
        "",
    ))


def test_r26_main_and_menu_derivation_rebind_only_the_active_proof_surface():
    main = derive_r26_double_impact_candidate_main(_minimal_r24_main())
    assert main.startswith("#define SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE 1\n")
    assert '"MIDI / 68K DOUBLE IMPACT"' in main
    assert "telemetry.voice_release_cancelled" in main
    assert _r26_telemetry_block() in main
    menu = derive_r26_double_impact_candidate_menu('before "MIDI 68K Song Proof" after')
    assert menu == 'before "MIDI R26 Space Spectre" after'
