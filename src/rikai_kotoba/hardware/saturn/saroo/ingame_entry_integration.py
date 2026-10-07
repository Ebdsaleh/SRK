"""Create a separate SAROO tree for one-shot first-read execution capture.

The source tree is expected to be the already hardware-validated SRK capture-menu
build tree. A new output tree is created and patched; the source tree is never
edited in place.

The first in-game checkpoint deliberately avoids title-specific addresses. When
the user arms the feature from the SAROO menu, the Saturn-side helper reads the
1st-read transfer address from the in-memory Saturn System ID/IP header at
0x060020F0 (IP offset 0xF0), then uses SAROO's existing SH-2 UBR support to stop
if/when execution reaches that address. The handler writes one 1 MiB WRAM-H
snapshot, disarms itself, and returns to the game.

Saturn's boot specification only guarantees that the 1st-read file is loaded to
this address; it does not guarantee that every title executes it. Therefore this
is called a first-read execution checkpoint rather than a universal game-entry
checkpoint. Later SRK stages can accept an explicit caller-supplied PC.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


class SarooInGameEntryIntegrationError(RuntimeError):
    """Raised when the first-read capture tree cannot be prepared safely."""


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
_MAIN_INDEX_PATCH = _MAIN_INDEX_ANCHOR + "int srk_first_read_index = -1;\n"
_MAIN_MENU_ANCHOR = '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
_MAIN_MENU_PATCH = (
    _MAIN_MENU_ANCHOR
    + "\tsrk_first_read_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Arm 1st-Read Capture");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_PATCH = r'''	}else if(index==srk_first_read_index){
		int retv;
		retv = srk_arm_first_read_capture();
		if(retv==SRK_CAPTURE_OK){
			menu_status(&main_menu, "SRK: 1st-read WRAM-H capture armed");
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
    "\t\tint srk_prepare_ret = srk_prepare_first_read_capture();\n"
    "\t\tif(srk_prepare_ret<0)\n"
    '\t\t\tprintk("SRK 1st-read capture prepare failed: %d\\n", srk_prepare_ret);\n'
    "\t}\n\n"
    + _GAME_BREAK_ANCHOR
)

_HELPER_HEADER_ANCHOR = "#endif\n"
_HELPER_HEADER_PATCH = r'''
/* One-shot, title-neutral execution capture at the IP.BIN 1st-read address. */
#define SRK_CAPTURE_ERR_FIRST_READ    -103

int srk_arm_first_read_capture(void);
int srk_prepare_first_read_capture(void);

#endif
'''

_HELPER_SOURCE_MARKER = "/* SRK one-shot 1st-read execution capture support. */"
_HELPER_SOURCE_APPEND = r'''

/* SRK one-shot 1st-read execution capture support. */
#define SRK_IP_MEMORY_BASE          0x06002000u
#define SRK_IP_FIRST_READ_OFFSET    0x000000f0u
#define SRK_WRAMH_START             0x06000000u
#define SRK_WRAMH_END_EXCLUSIVE     0x06100000u
#define SRK_GAME_WRAMH_PATH         "/SAROO/SRK_GAME_WRAMH.BIN"

extern void (*game_break_handle)(REGS *reg);

static int srk_first_read_capture_armed = 0;

static void srk_first_read_capture_handler(REGS *reg)
{
    (void)reg;

    /* One shot: disarm UBR before SD I/O and before returning to the title. */
    set_break_pc(0, 0);
    game_break_pc = 0;
    game_break_handle = 0;
    srk_first_read_capture_armed = 0;

    /*
     * Exception entry necessarily uses the title's current stack, so a small
     * portion of WRAM-H reflects the paused debug context. The rest is a direct
     * 1 MiB snapshot through SRK's already hardware-validated 64 KiB SAROO
     * write path.
     */
    srk_capture_work_ram_high(SRK_GAME_WRAMH_PATH);
}

int srk_arm_first_read_capture(void)
{
    srk_first_read_capture_armed = 1;
    return SRK_CAPTURE_OK;
}

int srk_prepare_first_read_capture(void)
{
    unsigned int first_read_pc;

    if(!srk_first_read_capture_armed)
        return 0;

    first_read_pc = BE32((void*)(SRK_IP_MEMORY_BASE + SRK_IP_FIRST_READ_OFFSET));
    if(first_read_pc<0x06002000u ||
       first_read_pc>=SRK_WRAMH_END_EXCLUSIVE ||
       (first_read_pc&1u)!=0u){
        srk_first_read_capture_armed = 0;
        game_break_pc = 0;
        game_break_handle = 0;
        return SRK_CAPTURE_ERR_FIRST_READ;
    }

    game_break_pc = (int)first_read_pc;
    game_break_handle = srk_first_read_capture_handler;
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
    """Copy the capture-menu tree and add a one-shot first-read WRAM-H capture."""

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
    if _HELPER_SOURCE_MARKER in helper_c or "SRK Arm 1st-Read Capture" in main_text:
        raise SarooInGameEntryIntegrationError(
            "source tree already contains first-read capture support"
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
            "SRK title-neutral one-shot 1st-read execution capture\n"
            f"Source capture-menu tree: {source}\n"
            "The source tree was not modified.\n"
            "Menu action: SRK Arm 1st-Read Capture\n"
            "Breakpoint source: big-endian IP.BIN 1st-read address at 0x060020F0\n"
            "Boot-spec note: 1st-read is loaded there, but not guaranteed to execute\n"
            "Trigger semantics: UBR handler runs after the first instruction if reached\n"
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
