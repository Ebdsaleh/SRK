"""Dear PyGui typography support for Salix desktop applications."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    import dearpygui.dearpygui as dpg
except ModuleNotFoundError:  # Keep semantic typography helpers testable headlessly.
    dpg = None  # type: ignore[assignment]


UI_FONT_SIZES = (13, 15, 17, 20)
SEMANTIC_FONT_SIZES = tuple(range(11, 32)) + (34,)
DEFAULT_UI_FONT_SIZE = 15
UI_FONT_LABELS = {
    13: "13 px - Compact",
    15: "15 px - Comfortable",
    17: "17 px - Large",
    20: "20 px - Extra Large",
}


def normalise_ui_font_size(value: object) -> int:
    """Return the closest supported UI font size."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = DEFAULT_UI_FONT_SIZE
    return min(UI_FONT_SIZES, key=lambda size: abs(size - numeric))


def ui_font_label(value: object) -> str:
    size = normalise_ui_font_size(value)
    return UI_FONT_LABELS[size]


def ui_font_size_from_label(value: object) -> int:
    text = str(value or "").strip()
    for size, label in UI_FONT_LABELS.items():
        if text == label:
            return size
    try:
        return normalise_ui_font_size(int(text.split()[0]))
    except (TypeError, ValueError, IndexError):
        return DEFAULT_UI_FONT_SIZE


class UiTypography:
    """Global, resolution-friendly typography for Salix Dear PyGui applications."""

    _instance: Optional["UiTypography"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registered = False
            cls._instance._font_path: Optional[Path] = None
            cls._instance._fonts: Dict[int, int] = {}
            cls._instance._current_size = DEFAULT_UI_FONT_SIZE
        return cls._instance

    @classmethod
    def get_instance(cls) -> "UiTypography":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _candidate_font_paths():
        if os.name == "nt":
            windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
            yield windows / "Fonts" / "consola.ttf"
            yield windows / "Fonts" / "lucon.ttf"
            yield windows / "Fonts" / "cour.ttf"
            return

        if sys.platform == "darwin":
            yield Path("/System/Library/Fonts/SFNSMono.ttf")
            yield Path("/System/Library/Fonts/Supplemental/Courier New.ttf")
            return

        yield Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
        yield Path("/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf")
        yield Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf")
        yield Path("/usr/share/fonts/opentype/noto/NotoSansMono-Regular.ttf")
        yield Path("/usr/local/share/fonts/dejavu/DejaVuSansMono.ttf")
        yield Path("/usr/local/share/fonts/LiberationMono-Regular.ttf")

    @classmethod
    def _find_scalable_font(cls) -> Optional[Path]:
        for candidate in cls._candidate_font_paths():
            try:
                if candidate.is_file():
                    return candidate
            except OSError:
                continue
        return None

    def register_fonts(self):
        """Register supported font sizes before Dear PyGui setup."""
        if self._registered:
            return

        if dpg is None:
            self._registered = True
            return

        self._font_path = self._find_scalable_font()
        if self._font_path is not None:
            try:
                with dpg.font_registry(tag="salix_ui_font_registry"):
                    for size in SEMANTIC_FONT_SIZES:
                        self._fonts[size] = dpg.add_font(str(self._font_path), size)
            except Exception as exc:
                print(f"[Salix Notice] Could not load scalable UI font: {exc}")
                self._fonts.clear()
                self._font_path = None

        self._registered = True

    def apply_font_size(self, value: object) -> int:
        """Apply a supported font size globally and return the normalized size."""
        size = normalise_ui_font_size(value)
        self._current_size = size

        font_id = self._fonts.get(size)
        if dpg is None:
            return size
        try:
            if font_id is not None:
                dpg.bind_font(font_id)
                dpg.set_global_font_scale(1.0)
            else:
                dpg.set_global_font_scale(size / 13.0)
        except Exception as exc:
            print(f"[Salix Notice] Could not apply UI font size {size}px: {exc}")
        return size

    def font_for_size(self, value: object):
        if not self._fonts:
            return None
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = self._current_size
        size = min(self._fonts, key=lambda candidate: abs(candidate - requested))
        return self._fonts.get(size)

    def bind_item_font(self, item, value: object) -> bool:
        font_id = self.font_for_size(value)
        if font_id is None or dpg is None:
            return False
        try:
            dpg.bind_item_font(item, font_id)
            return True
        except Exception:
            return False

    def measure_text_width(self, text: object, value: object) -> int:
        rendered = str(text or "")
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = self._current_size
        font_id = self.font_for_size(requested)
        if dpg is None:
            return max(1, int(len(rendered) * max(8, requested) * 0.62))
        try:
            if font_id is not None:
                width, _height = dpg.get_text_size(rendered, font=font_id)
            else:
                width, _height = dpg.get_text_size(rendered)
            return max(1, int(width))
        except Exception:
            return max(1, int(len(rendered) * max(8, requested) * 0.62))

    @property
    def current_size(self) -> int:
        return self._current_size

    @property
    def font_path(self) -> str:
        return str(self._font_path) if self._font_path is not None else "Dear PyGui built-in"
