"""Small title-neutral Sega Saturn memory-map constants used by SRK tooling.

Only regions required by current capture workflows belong here.  The complete
Saturn bus map is larger and includes mirrors, device registers, VRAM, sound
RAM, and cartridge space; those should be added only when a concrete SRK
feature needs them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SaturnMemoryRegion:
    name: str
    start_address: int
    size: int
    description: str = ""

    @property
    def end_address_exclusive(self) -> int:
        return self.start_address + self.size


# Physical work-RAM windows used by Saturn software.  WRAM-H is mirrored across
# a larger bus range; SRK captures the canonical 1 MiB window at 0x06000000.
WORK_RAM_LOW = SaturnMemoryRegion(
    name="Work RAM-L",
    start_address=0x00200000,
    size=0x00100000,
    description="1 MiB low work RAM",
)

WORK_RAM_HIGH = SaturnMemoryRegion(
    name="Work RAM-H",
    start_address=0x06000000,
    size=0x00100000,
    description="1 MiB high work RAM (canonical window)",
)

WORK_RAM_REGIONS = (WORK_RAM_LOW, WORK_RAM_HIGH)
