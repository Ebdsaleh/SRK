"""Create a separate SAROO tree for one-shot game-entry Work RAM capture.

The source tree is expected to be the already hardware-validated SRK capture-menu
build tree.  A new output tree is created and patched; the source tree is never
edited in place.

The first in-game checkpoint deliberately avoids title-specific addresses.  When
the user arms the feature from the SAROO menu, the Saturn-side helper waits until
SAROO has populated the BIOS game-entry pointer at 0x06000284, then uses SAROO's
existing SH-2 UBR support to stop immediately after the first instruction at that
entry point, write one 1 MiB WRAM-H snapshot, disarm itself, and resume execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


class SarooInGameEntryIntegrationError(RuntimeError):
    """Raised when the in-game entry-capture tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooInGameEntryIntegrationResult:
    source_root: Path
    output_root: Path
    main_path: Path
    game_load_path: Path
    helper_source_path: Path
    helper_header_path: Path
    marker_path: Path


_MAIN_INDEX_ANCHOR = "int srk_wramh_index = -1;\n"
_MAIN_INDEX_PATCH = _MAIN_INDEX_ANCHOR + "int srk_ingame_entry_index = -1;\n"
_MAIN_MENU_ANCHOR = '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
_MAIN_MENU_PATCH = (
    _MAIN_MENU_ANCHOR
    + "\tsrk_ingame_entry_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Arm Game-Entry Capture");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_PATCH = r'''	}else if(index==srk_ingame_entry_index){
		int retv;
		retv = srk_arm_game_entry_capture();
		if(retv==SRK_CAPTURE_OK){
			menu_status(&main_menu, "SRK: game-entry WRAM-H capture armed");
		}else{
			char buf[64];
			sprintf(buf, "SRK: arm failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
'''

_GAME_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_GAME_INCLUDE_PATCH = _GAME_INCLUDE_ANCHOR + '#include "srk_capture_helper.h"\n'
_GAME_BREAK_ANCHOR = "\tif(game_break_pc){\n\t\tset_break_pc(game_break_pc, 0);\n"
_GAME_BREAK_PATCH = (
    "\t{\n"
    "\t\tint srk_prepare_ret = srk_prepare_game_entry_capture();\n"
    "\t\tif(srk_prepare_ret<0)\n"
    ' \t\t\tprintk("SRK entry capture prepare failed: %d\\n", srk_prepare_ret);\n'
    "\t}\n\n"
    + _GAME_BREAK_ANCHOR
)

_HELPER_HEADER_ANCHOR = "#endif\n"
_HELPER_HEADER_PATCH = r'''
/* One-shot, title-neutral in-game capture at the BIOS-provided game entry PC. */
#define SRK_CAPTURE_ERR_GAME_ENTRY    -103

int srk_arm_game_entry_capture(void);
int srk_prepare_game_entry_capture(void);

#endif
'''

_HELPER_SOURCE_MARKER = "/* SRK one-shot game-entry capture support. */"
_HELPER_SOURCE_APPEND = r'''

/* SRK one-shot game-entry capture support. */
#define SRK_GAME_ENTRY_POINTER_ADDRESS 0x06000284u
#define SRK_GAME_WRAMH_PATH "/SAROO/SRK_GAME_WRAMH.BIN"

extern void (*game_break_handle)(REGS *reg);

static int srk_game_entry_capture_armed = 0;

static void srk_game_entry_capture_handler(REGS *reg)
{
    (void)reg;

    /* One shot: disarm UBR before any SD I/O and before returning to the game. */
    set_break_pc(0, 0);
    game_break_pc = 0;
    game_break_handle = 0;
    srk_game_entry_capture_armed = 0;

    /*
     * The exception entry itself necessarily uses the game's current stack, so
     * a tiny part of WRAM-H reflects the paused debug context.  The capture is
     * otherwise a direct 1 MiB read of canonical WRAM-H via the already
     * hardware-validated 64 KiB SAROO write path.
     */
    srk_capture_work_ram_high(SRK_GAME_WRAMH_PATH);
}

int srk_arm_game_entry_capture(void)
{
    srk_game_entry_capture_armed = 1;
    return SRK_CAPTURE_OK;
}

int srk_prepare_game_entry_capture(void)
{
    unsigned int entry_pc;

    if(!srk_game_entry_capture_armed)
        return 0;

    entry_pc = *(volatile unsigned int*)SRK_GAME_ENTRY_POINTER_ADDRESS;
    if(entry_pc==0 || entry_pc==0xffffffffu || (entry_pc&1u)!=0u){
        srk_game_entry_capture_armed = 0;
        game_break_pc = 0;
        game_break_handle = 0;
        return SRK_CAPTURE_ERR_GAME_ENTRY;
    }

    game_break_pc = (int)entry_pc;
    game_break_handle = srk_game_entry_capture_handler;
    return 1;
}
'''


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SarooInGameEntryIntegrationError(f"cannot read {path}: {exc}") from exc


def _write(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooInGameEntryIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooInGameEntryIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree is not the validated SRK capture-menu shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_ingame_entry_capture_tree(
    capture_menu_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
) -> SarooInGameEntryIntegrationResult:
    """Copy the capture-menu tree and add a one-shot game-entry WRAM-H capture."""

    source = _canonical(capture_menu_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    main_path = firm / "main.c"
    game_load_path = firm / "game_load.c"
    helper_c_path = firm / "srk_capture_helper.c"
    helper_h_path = firm / "srk_capture_helper.h"

    required = (main_path, game_load_path, helper_c_path, helper_h_path)
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise SarooInGameEntryIntegrationError(
            "source capture-menu tree is incomplete: " + ", ".join(str(path) for path in missing)
        )
    if output.exists():
        raise SarooInGameEntryIntegrationError(
            f"output already exists; choose a new in-game capture directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooInGameEntryIntegrationError(
            "output must be outside the existing capture-menu tree"
        )

    main_text = _read(main_path)
    game_text = _read(game_load_path)
    helper_c = _read(helper_c_path)
    helper_h = _read(helper_h_path)

    if "SRK Capture WRAM-H" not in main_text:
        raise SarooInGameEntryIntegrationError(
            "source tree is not the validated controller capture-menu tree"
        )
    if _HELPER_SOURCE_MARKER in helper_c or "SRK Arm Game-Entry Capture" in main_text:
        raise SarooInGameEntryIntegrationError(
            "source tree already contains in-game entry capture support"
        )

    patched_main = _replace_once(
        main_text,
        _MAIN_INDEX_ANCHOR,
        _MAIN_INDEX_PATCH,
        label="main menu index",
    )
    patched_main = _replace_once(
        patched_main,
        _MAIN_MENU_ANCHOR,
        _MAIN_MENU_PATCH,
        label="main menu construction",
    )
    patched_main = _replace_once(
        patched_main,
        _MAIN_HANDLER_ANCHOR,
        _MAIN_HANDLER_PATCH + _MAIN_HANDLER_ANCHOR,
        label="main menu handler",
    )

    patched_game = game_text
    if '#include "srk_capture_helper.h"' not in patched_game:
        patched_game = _replace_once(
            patched_game,
            _GAME_INCLUDE_ANCHOR,
            _GAME_INCLUDE_PATCH,
            label="game_load include",
        )
    patched_game = _replace_once(
        patched_game,
        _GAME_BREAK_ANCHOR,
        _GAME_BREAK_PATCH,
        label="game breakpoint installation",
    )

    patched_h = _replace_once(
        helper_h,
        _HELPER_HEADER_ANCHOR,
        _HELPER_HEADER_PATCH,
        label="capture helper header end",
    )
    patched_c = helper_c.rstrip() + _HELPER_SOURCE_APPEND + "\n"

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        _write(target_firm / "main.c", patched_main)
        _write(target_firm / "game_load.c", patched_game)
        _write(target_firm / "srk_capture_helper.c", patched_c)
        _write(target_firm / "srk_capture_helper.h", patched_h)
        marker = output / "SRK_INGAME_ENTRY_CAPTURE.txt"
        _write(
            marker,
            "SRK title-neutral one-shot game-entry capture\n"
            f"Source capture-menu tree: {source}\n"
            "The source tree was not modified.\n"
            "Menu action: SRK Arm Game-Entry Capture\n"
            "Breakpoint: BIOS game-entry pointer read from 0x06000284 at load time\n"
            "Trigger semantics: UBR handler runs after the first instruction at entry\n"
            "Output: /SAROO/SRK_GAME_WRAMH.BIN (1 MiB, WRAM-H)\n"
            "Capture is one-shot and UBR is disarmed before SD I/O.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooInGameEntryIntegrationResult(
        source_root=source,
        output_root=output,
        main_path=output / "Firm_Saturn" / "main.c",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        helper_source_path=output / "Firm_Saturn" / "srk_capture_helper.c",
        helper_header_path=output / "Firm_Saturn" / "srk_capture_helper.h",
        marker_path=output / "SRK_INGAME_ENTRY_CAPTURE.txt",
    )
