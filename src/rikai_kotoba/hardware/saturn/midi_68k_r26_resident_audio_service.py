"""R26 16-voice, multi-timbre MC68EC000 MIDI -> SCSP service.

R26 deliberately reuses the physically accepted R25 scheduler, full seven-opcode
MIDI state decoder, due-time clock, and release lifecycle. The delta is musical:
16 owned SCSP slots, deterministic release-tail stealing, and a deterministic
program-family timbre selector with a separate channel-10 percussion timbre.

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


class _R26AudioAssembler68K(_r23._AudioAssembler68K):
    """R26-local branch relaxation without changing accepted R23-R25 encoding.

    R25's four-slot image fits signed 16-bit Bcc/BRA displacements. Expanding the
    same proven logic to sixteen slots pushes some forward error branches beyond
    +/-32767 bytes. R26 therefore emits long-safe forms from the beginning:

    * BRA -> JMP (xxx).L
    * Bcc -> B!cc.s +6 ; JMP (xxx).L

    The MC68EC000 supports absolute-long JMP. Labels remain word indices, so the
    absolute destination is resident-program base + label*2.
    """

    def __init__(self) -> None:
        super().__init__()
        self._r26_absolute_branches: list[tuple[int, int, str]] = []

    def branch_word(self, opcode: int, target: str) -> None:
        base = opcode & 0xFF00
        if base == 0x6000:  # BRA
            self.word(0x4EF9)  # JMP (xxx).L
            hi_index = len(self.words)
            self.word(0)
            lo_index = len(self.words)
            self.word(0)
            self._r26_absolute_branches.append((hi_index, lo_index, target))
            return
        if base == 0x6100:
            raise SaturnMidi68KR26ResidentAudioServiceError(
                "R26 long-safe assembler does not accept BSR through branch_word"
            )
        if 0x6200 <= base <= 0x6F00:
            inverse = base ^ 0x0100
            # If the original condition is false, skip the six-byte JMP.
            self.word(inverse | 0x0006)
            self.word(0x4EF9)  # JMP (xxx).L
            hi_index = len(self.words)
            self.word(0)
            lo_index = len(self.words)
            self.word(0)
            self._r26_absolute_branches.append((hi_index, lo_index, target))
            return
        raise SaturnMidi68KR26ResidentAudioServiceError(
            f"unsupported R26 branch opcode 0x{base:04X}"
        )

    def finish(self) -> tuple[int, ...]:
        if self.word_branches:
            raise SaturnMidi68KR26ResidentAudioServiceError(
                "R26 assembler unexpectedly contains legacy word-branch fixups"
            )
        words = list(self.words)
        program_base = _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS
        for hi_index, lo_index, target_name in self._r26_absolute_branches:
            try:
                target_index = self.labels[target_name]
            except KeyError as exc:
                raise SaturnMidi68KR26ResidentAudioServiceError(
                    f"undefined R26 68K branch target: {target_name}"
                ) from exc
            target_address = program_base + target_index * 2
            if target_address < 0 or target_address > 0xFFFFFFFF:
                raise SaturnMidi68KR26ResidentAudioServiceError(
                    f"R26 branch target address out of range: 0x{target_address:X}"
                )
            words[hi_index] = (target_address >> 16) & 0xFFFF
            words[lo_index] = target_address & 0xFFFF
        return tuple(words)


_ORIGINAL_VALIDATE = _r25.validate_saturn_midi_68k_r25_resident_audio_layout
_ORIGINAL_INITIALIZATION = _r25._emit_r25_initialization
_ORIGINAL_KEY_ON_SLOT = _r25._emit_r25_key_on_slot
_ORIGINAL_NOTE_ON = _r25._emit_r25_note_on
_ORIGINAL_ASSEMBLER = _r23._AudioAssembler68K


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


def _emit_r26_note_on(asm: _r23._AudioAssembler68K) -> None:
    """Allocate without dropping a Note On while any release tail can be reused."""

    _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_KEY_ON_COUNT_WORD)
    _r25._emit_retire_expired(asm, "r26_note_on")

    # First preserve R25's exact-key retrigger semantics.
    for slot in range(SATURN_MIDI_68K_R26_OWNED_SLOTS):
        next_label = f"r26_note_on_match_next_{slot}"
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0
        )
        asm.cmpi_w(int(_r25.SaturnMidi68KR25SlotPhase.FREE), 0)
        asm.branch_word(0x6700, next_label)
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD), 0
        )
        asm.cmp_dn_w(1, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_NOTE_WORD), 0
        )
        asm.cmp_dn_w(5, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0
        )
        asm.cmpi_w(int(_r25.SaturnMidi68KR25SlotPhase.RELEASING), 0)
        asm.branch_word(0x6700, f"r26_note_on_slot_{slot}_releasing")
        asm.branch_word(0x6000, f"r26_note_on_slot_{slot}_held")
        asm.label(next_label)

    # Then prefer a truly free voice.
    for slot in range(SATURN_MIDI_68K_R26_OWNED_SLOTS):
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0
        )
        asm.cmpi_w(int(_r25.SaturnMidi68KR25SlotPhase.FREE), 0)
        asm.branch_word(0x6700, f"r26_note_on_slot_{slot}_free")

    # If all 16 are owned only because tails are decaying, preserve the new Note
    # On by cancelling the lowest-numbered releasing slot. The physically useful
    # invariant is therefore: BUSY only when all owned slots are still HELD.
    for slot in range(SATURN_MIDI_68K_R26_OWNED_SLOTS):
        asm.move_absw_to_dn(
            _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0
        )
        asm.cmpi_w(int(_r25.SaturnMidi68KR25SlotPhase.RELEASING), 0)
        asm.branch_word(0x6700, f"r26_note_on_slot_{slot}_releasing")

    _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_BUSY_COUNT_WORD)
    asm.move_imm_absw(
        _r25.SATURN_MIDI_68K_R25_VOICE_ERROR_BUSY,
        _r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD),
    )
    asm.branch_word(0x6000, "r25_audio_note_on_done")

    for slot in range(SATURN_MIDI_68K_R26_OWNED_SLOTS):
        for allocation in ("releasing", "held", "free"):
            prefix = f"r26_note_on_slot_{slot}_{allocation}"
            asm.label(prefix)
            _emit_r26_key_on_slot(
                asm,
                slot,
                prefix=prefix,
                allocation=allocation,
            )
    # _ORIGINAL_KEY_ON_SLOT branches here after every successful allocation.
    asm.label("r25_audio_note_on_done")


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
        "_emit_r25_note_on",
    )
    original = {name: getattr(_r25, name) for name in patched_names}
    original_assembler = _r23._AudioAssembler68K
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
        _r25._emit_r25_note_on = _emit_r26_note_on
        _r23._AudioAssembler68K = _R26AudioAssembler68K
        derived = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=release_rate
        )
    finally:
        _r23._AudioAssembler68K = original_assembler
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
