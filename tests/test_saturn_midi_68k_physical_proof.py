from pathlib import Path

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof import (
    SaturnMidi68KPhysicalProofState,
    begin_srk_saturn_midi_68k_physical_proof,
    poll_srk_saturn_midi_68k_physical_proof,
    render_srk_saturn_midi_68k_physical_proof_header,
    render_srk_saturn_midi_68k_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_runtime import (
    SaturnMidi68KProtocolSnapshot,
    SaturnMidi68KRuntimeStatus,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDALONE = REPO_ROOT / "integrations" / "saturn" / "standalone"


def test_physical_proof_renderers_match_committed_c_files():
    header = (STANDALONE / "srk_saturn_midi_68k_physical_proof.h").read_text(
        encoding="utf-8"
    )
    source = (STANDALONE / "srk_saturn_midi_68k_physical_proof.c").read_text(
        encoding="utf-8"
    )

    assert header == render_srk_saturn_midi_68k_physical_proof_header()
    assert source == render_srk_saturn_midi_68k_physical_proof_source()


def test_physical_proof_begin_is_bounded_to_one_attempt_until_reset():
    state = SaturnMidi68KPhysicalProofState()

    assert begin_srk_saturn_midi_68k_physical_proof(
        state, SaturnMidi68KRuntimeStatus.RUNNING
    ) == SaturnMidi68KRuntimeStatus.RUNNING
    assert state.attempted is True

    assert begin_srk_saturn_midi_68k_physical_proof(
        state, SaturnMidi68KRuntimeStatus.INSTALL_FAILED
    ) == SaturnMidi68KRuntimeStatus.RUNNING


def test_physical_proof_nonblocking_poll_reaches_acknowledged_once_mailbox_matches():
    state = SaturnMidi68KPhysicalProofState()
    begin_srk_saturn_midi_68k_physical_proof(
        state, SaturnMidi68KRuntimeStatus.RUNNING
    )
    snapshot = SaturnMidi68KProtocolSnapshot(
        flags=SATURN_MIDI_MAILBOX_FLAG_READY,
        read_sequence=1,
        read_index=1,
        last_error=0,
    )

    assert poll_srk_saturn_midi_68k_physical_proof(
        state, snapshot
    ) == SaturnMidi68KRuntimeStatus.ACKNOWLEDGED
    assert state.poll_count == 1
    assert state.telemetry == snapshot


def test_physical_proof_nonblocking_poll_surfaces_consumer_error():
    state = SaturnMidi68KPhysicalProofState()
    begin_srk_saturn_midi_68k_physical_proof(
        state, SaturnMidi68KRuntimeStatus.RUNNING
    )
    snapshot = SaturnMidi68KProtocolSnapshot(
        flags=SATURN_MIDI_MAILBOX_FLAG_READY,
        read_sequence=0,
        read_index=0,
        last_error=4,
    )

    assert poll_srk_saturn_midi_68k_physical_proof(
        state, snapshot
    ) == SaturnMidi68KRuntimeStatus.CONSUMER_ERROR
    assert state.poll_count == 1
    assert state.telemetry.last_error == 4


def test_physical_proof_controller_has_no_direct_mmio_or_busy_wait():
    source = render_srk_saturn_midi_68k_physical_proof_source()

    assert "srk_saturn_midi_68k_protocol_begin(" in source
    assert "srk_saturn_midi_68k_protocol_poll(" in source
    assert "srk_saturn_midi_68k_hardware_adapter_ops()" in source
    assert "while(" not in source
    assert "for(" not in source
    assert "0x2010001F" not in source
    assert "0x25A00000" not in source
    assert "0x25B00000" not in source
    assert "SCSP" not in source
