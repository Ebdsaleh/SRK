"""Title-neutral contracts for the standalone Saturn diagnostics runtime.

The Python side describes the same menu, normalized input states, and flight-
recorder record layout that the Saturn-side C runtime will use.  Hardware-
specific controller encodings remain a host responsibility so the core never
assumes that a BIOS snapshot, direct SMPC packet, or injected-title buffer has
one universal bit layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
import struct


class DiagnosticScreen(IntEnum):
    INPUT_TEST = 0
    VIDEO_PATTERN_TEST = 1
    VDP1_3D_TEST = 2
    AUDIO_TEST = 3
    TIMING_INTERRUPT_TEST = 4
    MEMORY_DUMP_TOOLS = 5
    FLIGHT_RECORDER = 6
    SYSTEM_INFORMATION = 7


DIAGNOSTIC_MENU = (
    (DiagnosticScreen.INPUT_TEST, "Controller / Input Test"),
    (DiagnosticScreen.VIDEO_PATTERN_TEST, "Video Pattern Test"),
    (DiagnosticScreen.VDP1_3D_TEST, "VDP1 / 3D Test"),
    (DiagnosticScreen.AUDIO_TEST, "Audio / SCSP Test"),
    (DiagnosticScreen.TIMING_INTERRUPT_TEST, "Timing / Interrupt Test"),
    (DiagnosticScreen.MEMORY_DUMP_TOOLS, "Memory / Dump Tools"),
    (DiagnosticScreen.FLIGHT_RECORDER, "Flight Recorder"),
    (DiagnosticScreen.SYSTEM_INFORMATION, "System Information"),
)


class NormalizedButton(IntFlag):
    NONE = 0
    UP = 1 << 0
    DOWN = 1 << 1
    LEFT = 1 << 2
    RIGHT = 1 << 3
    A = 1 << 4
    B = 1 << 5
    C = 1 << 6
    X = 1 << 7
    Y = 1 << 8
    Z = 1 << 9
    L = 1 << 10
    R = 1 << 11
    START = 1 << 12


TRACKED_BUTTONS = tuple(
    button for button in NormalizedButton if button is not NormalizedButton.NONE
)


@dataclass
class InputState:
    """Normalized digital-pad state with edge and hold-duration tracking."""

    current: NormalizedButton = NormalizedButton.NONE
    previous: NormalizedButton = NormalizedButton.NONE
    pressed: NormalizedButton = NormalizedButton.NONE
    released: NormalizedButton = NormalizedButton.NONE
    hold_started_us: dict[NormalizedButton, int] = field(default_factory=dict)
    hold_duration_us: dict[NormalizedButton, int] = field(default_factory=dict)

    def update(self, buttons: NormalizedButton | int, now_us: int) -> None:
        if now_us < 0:
            raise ValueError("now_us must be non-negative")

        new_state = NormalizedButton(buttons)
        self.previous = self.current
        self.current = new_state
        self.pressed = new_state & ~self.previous
        self.released = self.previous & ~new_state

        for button in TRACKED_BUTTONS:
            if self.pressed & button:
                self.hold_started_us[button] = now_us
                self.hold_duration_us[button] = 0
            elif self.current & button:
                started = self.hold_started_us.get(button, now_us)
                self.hold_started_us.setdefault(button, started)
                self.hold_duration_us[button] = now_us - started
            elif self.released & button:
                started = self.hold_started_us.pop(button, now_us)
                self.hold_duration_us[button] = now_us - started
            else:
                self.hold_duration_us.setdefault(button, 0)

    def held_for_us(self, button: NormalizedButton) -> int:
        return self.hold_duration_us.get(button, 0)

    def combination_active(self, buttons: NormalizedButton | int) -> bool:
        mask = NormalizedButton(buttons)
        return mask != NormalizedButton.NONE and (self.current & mask) == mask


FLIGHT_RECORDER_SECONDS = 30
FLIGHT_RECORDER_MAX_HZ = 60
FLIGHT_RECORDER_CAPACITY = FLIGHT_RECORDER_SECONDS * FLIGHT_RECORDER_MAX_HZ
FLIGHT_RECORD_MAGIC = b"SRKT"
FLIGHT_RECORD_VERSION = 1

# 32-byte frame/event record:
# timestamp_us, frame, raw_pad, normalized_pad, pressed, released, held,
# diagnostic_id, vbr, value0, value1
_FLIGHT_RECORD = struct.Struct(">IIHHHHHHIII")
FLIGHT_RECORD_SIZE = _FLIGHT_RECORD.size


@dataclass(frozen=True)
class FlightRecord:
    timestamp_us: int
    frame: int
    raw_pad: int
    normalized_pad: int
    pressed: int
    released: int
    held: int
    diagnostic_id: int
    vbr: int
    value0: int = 0
    value1: int = 0

    def pack(self) -> bytes:
        return _FLIGHT_RECORD.pack(
            self.timestamp_us,
            self.frame,
            self.raw_pad,
            self.normalized_pad,
            self.pressed,
            self.released,
            self.held,
            self.diagnostic_id,
            self.vbr,
            self.value0,
            self.value1,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "FlightRecord":
        if len(data) != FLIGHT_RECORD_SIZE:
            raise ValueError(f"flight record must be exactly {FLIGHT_RECORD_SIZE} bytes")
        return cls(*_FLIGHT_RECORD.unpack(data))


class FlightRecorder:
    """Host-side model of the 30-second rolling telemetry ring."""

    def __init__(self, capacity: int = FLIGHT_RECORDER_CAPACITY) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._records: list[FlightRecord] = []
        self._write_index = 0
        self.armed = False
        self.frozen = False

    def arm(self) -> None:
        self._records.clear()
        self._write_index = 0
        self.armed = True
        self.frozen = False

    def append(self, record: FlightRecord) -> None:
        if not self.armed or self.frozen:
            return
        if len(self._records) < self.capacity:
            self._records.append(record)
            self._write_index = len(self._records) % self.capacity
            return
        self._records[self._write_index] = record
        self._write_index = (self._write_index + 1) % self.capacity

    def freeze(self) -> None:
        if self.armed:
            self.frozen = True

    def records(self) -> tuple[FlightRecord, ...]:
        if len(self._records) < self.capacity or self._write_index == 0:
            return tuple(self._records)
        return tuple(self._records[self._write_index :] + self._records[: self._write_index])
