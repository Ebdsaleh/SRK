"""Read and validate SRK's R9 persistent resident runtime-input proof artifact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


SRK_RUNTIME_INPUT_PROOF_RELATIVE_PATH = Path("SAROO") / "SRK_RUNTIME_INPUT_PROOF.BIN"
SRK_RUNTIME_INPUT_PROOF_FILE_SIZE = 96
SRK_RUNTIME_INPUT_PROOF_SLOT_SIZE = 32
SRK_RUNTIME_INPUT_PROOF_MAGIC = b"SRKI"
SRK_RUNTIME_INPUT_PROOF_VERSION = 1

_STAGE_NAMES = {
    1: "armed",
    2: "installed",
    3: "activated",
    0x7F: "rejected",
}


class SarooRuntimeResidentInputProofError(RuntimeError):
    """Raised when an R9 runtime-input proof artifact cannot be validated."""


@dataclass(frozen=True)
class SarooRuntimeResidentInputProofSlot:
    index: int
    stage: int
    stage_name: str
    buttons: int
    callback_count: int
    sample_count: int
    timer_ticks: int
    elapsed_ticks: int
    sample_period_us: int
    hold_samples: int


@dataclass(frozen=True)
class SarooRuntimeResidentInputProofReport:
    card_root: Path
    proof_path: Path
    slots: tuple[SarooRuntimeResidentInputProofSlot, ...]

    @property
    def activated(self) -> bool:
        return any(slot.stage == 3 for slot in self.slots)


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _be16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], byteorder="big", signed=False)


def _be32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], byteorder="big", signed=False)


def inspect_runtime_resident_input_proof(
    card_root: os.PathLike[str] | str,
) -> SarooRuntimeResidentInputProofReport:
    """Read the R9 proof artifact without modifying the mounted SAROO card."""

    card = _canonical(card_root)
    proof = card / SRK_RUNTIME_INPUT_PROOF_RELATIVE_PATH
    if not proof.is_file():
        raise SarooRuntimeResidentInputProofError(
            f"runtime input proof file not found: {proof}"
        )

    try:
        data = proof.read_bytes()
    except OSError as exc:
        raise SarooRuntimeResidentInputProofError(
            f"cannot read runtime input proof file {proof}: {exc}"
        ) from exc

    if len(data) != SRK_RUNTIME_INPUT_PROOF_FILE_SIZE:
        raise SarooRuntimeResidentInputProofError(
            "runtime input proof file has unexpected size: "
            f"{len(data)} != {SRK_RUNTIME_INPUT_PROOF_FILE_SIZE}"
        )

    slots: list[SarooRuntimeResidentInputProofSlot] = []
    for index in range(3):
        start = index * SRK_RUNTIME_INPUT_PROOF_SLOT_SIZE
        slot = data[start : start + SRK_RUNTIME_INPUT_PROOF_SLOT_SIZE]
        if slot == bytes(SRK_RUNTIME_INPUT_PROOF_SLOT_SIZE):
            continue
        if slot[:4] != SRK_RUNTIME_INPUT_PROOF_MAGIC:
            raise SarooRuntimeResidentInputProofError(
                f"runtime input proof slot {index} has invalid magic: {slot[:4]!r}"
            )
        if slot[5] != SRK_RUNTIME_INPUT_PROOF_VERSION:
            raise SarooRuntimeResidentInputProofError(
                f"runtime input proof slot {index} has unsupported version: {slot[5]}"
            )

        stage = slot[4]
        if stage not in _STAGE_NAMES:
            raise SarooRuntimeResidentInputProofError(
                f"runtime input proof slot {index} has unknown stage: {stage}"
            )

        slots.append(
            SarooRuntimeResidentInputProofSlot(
                index=index,
                stage=stage,
                stage_name=_STAGE_NAMES[stage],
                buttons=_be16(slot, 6),
                callback_count=_be32(slot, 8),
                sample_count=_be32(slot, 12),
                timer_ticks=_be32(slot, 16),
                elapsed_ticks=_be32(slot, 20),
                sample_period_us=_be32(slot, 24),
                hold_samples=_be32(slot, 28),
            )
        )

    if not slots:
        raise SarooRuntimeResidentInputProofError(
            "runtime input proof file contains no populated slots"
        )
    if slots[0].index != 0 or slots[0].stage != 1:
        raise SarooRuntimeResidentInputProofError(
            "runtime input proof does not begin with a valid armed slot"
        )

    return SarooRuntimeResidentInputProofReport(
        card_root=card,
        proof_path=proof,
        slots=tuple(slots),
    )
