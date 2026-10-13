"""R26 16-voice, multi-timbre MC68EC000 MIDI -> SCSP service.

R26 deliberately reuses the physically accepted R25 scheduler, full seven-opcode
MIDI state decoder, due-time clock, and release lifecycle. The delta is musical:
16 owned SCSP slots and a deterministic program-family timbre selector, with a
separate channel-10 percussion timbre.

The synthetic bank is a hardware bring-up bank, not a claim of GM soundfont
fidelity. It exists so real multi-channel/program MIDI can be audibly
distinguished while preserving the already-proven transport path.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from . import midi_68k_r25_resident_audio_service as _r25
from . import midi_68k_resident_audio_service as _r23
from .midi_68k_r25_envelope import build_saturn_midi_68k_r25_envelope_plan
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_SCSP_SLOT_SA_LOW,
)
from .midi_68k_r26_timbre_bank import (
    SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE,
    SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS,
    SATURN_MIDI_68K_R26_TIMBRE_COUNT,
    SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES,
    build_srk_saturn_midi_68k_r26_timbre_bank,
)


SATURN_MIDI_68K_R26_OWNED_SLOTS = 16
SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS = 0x00002300
SATURN_MIDI_68K_R26_VOICE_STATE_BYTES = 0x00000400
SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS = 0x00002700
SATURN_MIDI_68K_R26_MIXER_TABLE_BYTES = 0x00000100
SATURN_MIDI_68K_R26_AUDIO_OWNERSHIP_END = 0x00003100
SATURN_MIDI_68K_R26_RESIDENT_AUDIO_MAX_END = 0x00018000


class SaturnMidi68KR26ResidentAudioServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaturnMidi68KR26ResidentAudioServiceImage:
    release_rate: int
    eg1_word: int
    eg2_word: int
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return self.word_count * 2

    @property
    def end_address(self) -> int:
        return _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


_ORIGINAL_VALIDATE = _r25.validate_saturn_midi_68k_r25_resident_audio_layout
_ORIGINAL_INITIALIZATION = _r25._emit_r25_initialization
_ORIGINAL_KEY_ON_SLOT = _r25._emit_r25_key_on_slot


def validate_srk_saturn_midi_68k_r26_resident_audio_layout() -> None:
    if SATURN_MIDI_68K_R26_OWNED_SLOTS < 1 or SATURN_MIDI_68K_R26_OWNED_SLOTS > 32:
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 slot ownership is invalid")
    if SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + 0x100 != SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS:
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 pitch/voice boundary changed")
    if (
        SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS + SATURN_MIDI_68K_R26_VOICE_STATE_BYTES
        != SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS
    ):
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 voice/mixer boundary changed")
    if (
        SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS + SATURN_MIDI_68K_R26_MIXER_TABLE_BYTES
        != SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
    ):
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 mixer/timbre boundary changed")
    if (
        SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
        + SATURN_MIDI_68K_R26_TIMBRE_COUNT * SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES
        != SATURN_MIDI_68K_R26_AUDIO_OWNERSHIP_END
    ):
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 timbre ownership changed")
    final_slot_word = (
        _r25.SATURN_MIDI_68K_R25_SLOT_BASE_WORD
        + SATURN_MIDI_68K_R26_OWNED_SLOTS * _r25.SATURN_MIDI_68K_R25_SLOT_WORDS
    )
    if final_slot_word * 2 > SATURN_MIDI_68K_R26_VOICE_STATE_BYTES:
        raise SaturnMidi68KR26ResidentAudioServiceError("R26 voice ledger is too small")
    if SATURN_MIDI_68K_R26_AUDIO_OWNERSHIP_END > _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS:
        raise SaturnMidi68KR26ResidentAudioServiceError(
            "R26 audio data overlaps resident program"
        )


def _emit_r26_initialization(
    asm: _r23._AudioAssembler68K, *, eg1: int, eg2: int, rr: int
) -> None:
    _ORIGINAL_INITIALIZATION(asm, eg1=eg1, eg2=eg2, rr=rr)
    for timbre in build_srk_saturn_midi_68k_r26_timbre_bank():
        for index, word in enumerate(timbre.words):
            asm.move_imm_absw(word, timbre.address + index * 2)


def _emit_r26_select_source(
    asm: _r23._AudioAssembler68K, slot: int, prefix: str
) -> None:
    percussion = f"{prefix}_r26_percussion"
    selected = f"{prefix}_r26_source_selected"

    asm.cmpi_w(9, 1)
    asm.branch_word(0x6700, percussion)
    asm.move_d16_an_to_dn(
        1,
        _r23._state_displacement(_r23.SATURN_MIDI_68K_CH_PROGRAM),
        0,
    )

    family_labels = []
    for family in range(7):
        label = f"{prefix}_r26_family_{family}"
        family_labels.append(label)
        asm.cmpi_w((family + 1) * 16, 0)
        asm.branch_word(0x6500, label)

    asm.move_imm_to_dn(
        SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
        + 7 * SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES,
        0,
    )
    asm.branch_word(0x6000, selected)

    for family, label in enumerate(family_labels):
        asm.label(label)
        asm.move_imm_to_dn(
            SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
            + family * SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES,
            0,
        )
        asm.branch_word(0x6000, selected)

    asm.label(percussion)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
        + SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE
        * SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES,
        0,
    )
    asm.label(selected)
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_SA_LOW, slot),
        4,
    )


def _emit_r26_key_on_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    allocation: str,
) -> None:
    _emit_r26_select_source(asm, slot, prefix)
    _ORIGINAL_KEY_ON_SLOT(
        asm,
        slot,
        prefix=prefix,
        allocation=allocation,
    )


def build_srk_saturn_midi_68k_r26_resident_audio_service_image(
    *, release_rate: int
) -> SaturnMidi68KR26ResidentAudioServiceImage:
    validate_srk_saturn_midi_68k_r26_resident_audio_layout()
    plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=release_rate)

    patched_names = (
        "SATURN_MIDI_68K_R25_OWNED_SLOTS",
        "SATURN_MIDI_68K_R25_VOICE_STATE_BYTES",
        "SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS",
        "SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END",
        "SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END",
        "validate_saturn_midi_68k_r25_resident_audio_layout",
        "_emit_r25_initialization",
        "_emit_r25_key_on_slot",
    )
    original = {name: getattr(_r25, name) for name in patched_names}
    try:
        _r25.SATURN_MIDI_68K_R25_OWNED_SLOTS = SATURN_MIDI_68K_R26_OWNED_SLOTS
        _r25.SATURN_MIDI_68K_R25_VOICE_STATE_BYTES = SATURN_MIDI_68K_R26_VOICE_STATE_BYTES
        _r25.SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS = SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS
        _r25.SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END = SATURN_MIDI_68K_R26_AUDIO_OWNERSHIP_END
        _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END = SATURN_MIDI_68K_R26_RESIDENT_AUDIO_MAX_END
        _r25.validate_saturn_midi_68k_r25_resident_audio_layout = (
            validate_srk_saturn_midi_68k_r26_resident_audio_layout
        )
        _r25._emit_r25_initialization = _emit_r26_initialization
        _r25._emit_r25_key_on_slot = _emit_r26_key_on_slot
        derived = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=release_rate
        )
    finally:
        for name, value in original.items():
            setattr(_r25, name, value)

    image = SaturnMidi68KR26ResidentAudioServiceImage(
        release_rate=release_rate,
        eg1_word=plan.eg1_word,
        eg2_word=plan.eg2_word,
        words=derived.words,
    )
    if image.end_address > SATURN_MIDI_68K_R26_RESIDENT_AUDIO_MAX_END:
        raise SaturnMidi68KR26ResidentAudioServiceError(
            "R26 resident image exceeds the 0x4000-0x18000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_r26_resident_audio_service_header(
    *, release_rate: int
) -> str:
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(
        release_rate=release_rate
    )
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R26_RESIDENT_AUDIO_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_R26_RESIDENT_AUDIO_SERVICE_H",
            "",
            f"#define SRK_MIDI_68K_R26_OWNED_SLOTS {SATURN_MIDI_68K_R26_OWNED_SLOTS}u",
            f"#define SRK_MIDI_68K_R26_RELEASE_RATE {release_rate}u",
            f"#define SRK_MIDI_68K_R26_EG1_WORD 0x{image.eg1_word:04X}u",
            f"#define SRK_MIDI_68K_R26_EG2_WORD 0x{image.eg2_word:04X}u",
            f"#define SRK_MIDI_68K_R26_PROGRAM_ADDRESS 0x{_r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R26_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_R26_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_R26_VOICE_STATE_ADDRESS 0x{SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R26_MIXER_TABLE_ADDRESS 0x{SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R26_TIMBRE_BANK_ADDRESS 0x{SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS:08X}UL",
            "",
            "extern const unsigned short srk_saturn_midi_68k_r26_resident_audio_service_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r26_resident_audio_service_source(
    *, release_rate: int
) -> str:
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(
        release_rate=release_rate
    )
    lines = [
        '#include "srk_saturn_midi_68k_r26_resident_audio_service.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_r26_resident_audio_service_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        lines.append(
            "    "
            + ", ".join(f"0x{word:04X}u" for word in image.words[index : index + 8])
            + ","
        )
    lines.extend(("};", ""))
    return "\n".join(lines)
