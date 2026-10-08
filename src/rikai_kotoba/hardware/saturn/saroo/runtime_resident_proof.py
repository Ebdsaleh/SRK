"""Read and validate SRK's persistent SAROO resident-runtime proof artifact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


SRK_RUNTIME_PROOF_RELATIVE_PATH = Path("SAROO") / "SRK_RUNTIME_PROOF.BIN"
SRK_RUNTIME_PROOF_FILE_SIZE = 96
SRK_RUNTIME_PROOF_SLOT_SIZE = 32
SRK_RUNTIME_PROOF_MAGIC = b"SRKP"
SRK_RUNTIME_PROOF_VERSION = 1

_STAGE_NAMES = {
    1: "armed",
    2: "installed",
    3: "proven",
    0x7F: "rejected",
}


class SarooRuntimeResidentProofError(RuntimeError):
    """Raised when a resident-runtime proof artifact cannot be validated."""


@dataclass(frozen=True)
class SarooRuntimeResidentProofSlot:
    index: int
    stage: int
    stage_name: str
    count: int
    timer_ticks: int
    elapsed_ticks: int
    vector_address: int
    return_address: int
    threshold: int


@dataclass(frozen=True)
class SarooRuntimeResidentProofReport:
    card_root: Path
    proof_path: Path
    slots: tuple[SarooRuntimeResidentProofSlot, ...]

    @property
    def proven(self) -> bool:
        return any(slot.stage == 3 for slot in self.slots)


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _be32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], byteorder="big", signed=False)


def inspect_runtime_resident_proof(
    card_root: os.PathLike[str] | str,
) -> SarooRuntimeResidentProofReport:
    """Read the proof artifact without modifying the mounted SAROO card."""

    card = _canonical(card_root)
    proof = card / SRK_RUNTIME_PROOF_RELATIVE_PATH
    if not proof.is_file():
        raise SarooRuntimeResidentProofError(f"runtime proof file not found: {proof}")

    try:
        data = proof.read_bytes()
    except OSError as exc:
        raise SarooRuntimeResidentProofError(f"cannot read runtime proof file {proof}: {exc}") from exc

    if len(data) != SRK_RUNTIME_PROOF_FILE_SIZE:
        raise SarooRuntimeResidentProofError(
            f"runtime proof file has unexpected size: {len(data)} != {SRK_RUNTIME_PROOF_FILE_SIZE}"
        )

    slots: list[SarooRuntimeResidentProofSlot] = []
    for index in range(3):
        start = index * SRK_RUNTIME_PROOF_SLOT_SIZE
        slot = data[start : start + SRK_RUNTIME_PROOF_SLOT_SIZE]
        if slot == bytes(SRK_RUNTIME_PROOF_SLOT_SIZE):
            continue
        if slot[:4] != SRK_RUNTIME_PROOF_MAGIC:
            raise SarooRuntimeResidentProofError(
                f"runtime proof slot {index} has invalid magic: {slot[:4]!r}"
            )
        if slot[5] != SRK_RUNTIME_PROOF_VERSION:
            raise SarooRuntimeResidentProofError(
                f"runtime proof slot {index} has unsupported version: {slot[5]}"
            )

        stage = slot[4]
        if stage not in _STAGE_NAMES:
            raise SarooRuntimeResidentProofError(
                f"runtime proof slot {index} has unknown stage: {stage}"
            )

        slots.append(
            SarooRuntimeResidentProofSlot(
                index=index,
                stage=stage,
                stage_name=_STAGE_NAMES[stage],
                count=_be32(slot, 8),
                timer_ticks=_be32(slot, 12),
                elapsed_ticks=_be32(slot, 16),
                vector_address=_be32(slot, 20),
                return_address=_be32(slot, 24),
                threshold=_be32(slot, 28),
            )
        )

    if not slots:
        raise SarooRuntimeResidentProofError("runtime proof file contains no populated slots")
    if slots[0].index != 0 or slots[0].stage != 1:
        raise SarooRuntimeResidentProofError("runtime proof does not begin with a valid armed slot")

    return SarooRuntimeResidentProofReport(
        card_root=card,
        proof_path=proof,
        slots=tuple(slots),
    )
