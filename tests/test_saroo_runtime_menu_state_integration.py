"""Synthetic tests for renderer-independent SAROO runtime-menu state preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_menu_state_integration import (
    SarooRuntimeMenuStateIntegrationError,
    prepare_runtime_menu_state_tree,
)
from rikai_kotoba.tools.saroo_runtime_menu_state_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_capture_helper.o  \\
\t\tobj/srk_runtime_input.o  \\
\t\tobj/game_load.o\n"""

GAME_LOAD = '''#include "main.h"
#include "smpc.h"
#include "srk_runtime_input.h"

static int (*cdp_boot_game)(void);
static int sk0, sk1;
static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;
static int srk_runtime_menu_requested = 0;
static void (*orig_func)(void);

static void cdp_hook(void)
{
\tint srk_event;
\tsk0 = *(u16*)0x06020232;
\tsk1 = *(u16*)0x06020236;
\tsrk_event = srk_runtime_input_sample(
\t\t&srk_runtime_input_state,
\t\t(unsigned int)sk0
\t);
\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU)
\t\tsrk_runtime_menu_requested = 1;
\torig_func();
}

void my_cdplayer(void)
{
\tvoid (*go)(int);

\tsrk_runtime_input_reset(&srk_runtime_input_state);
\tsrk_runtime_menu_requested = 0;
\t(void)go;
}
'''


class SarooRuntimeMenuStateIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, marker: bool = True, game_text: str = GAME_LOAD) -> Path:
        source = root / "SAROO-SRK-RUNTIME-HOOK-R1"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(game_text, encoding="utf-8", newline="\n")
        if marker:
            (source / "SRK_RUNTIME_MENU.txt").write_text(
                "validated runtime hook\n", encoding="utf-8"
            )
        return source

    def test_creates_separate_tree_and_preserves_validated_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            before_makefile = (source / "Firm_Saturn" / "Makefile").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_menu_state_tree(source, root / "R2")

            self.assertEqual(
                (source / "Firm_Saturn" / "Makefile").read_bytes(), before_makefile
            )
            self.assertEqual(
                (source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game
            )
            self.assertTrue(result.state_source_path.is_file())
            self.assertTrue(result.state_header_path.is_file())
            self.assertTrue(result.marker_path.is_file())
            self.assertIn(
                "obj/srk_runtime_menu_state.o",
                result.makefile_path.read_text(encoding="utf-8"),
            )

    def test_generated_hook_feeds_state_machine_without_replacing_original_callback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_menu_state_tree(self._source(root), root / "R2")
            game = result.game_load_path.read_text(encoding="utf-8")

            self.assertIn('#include "srk_runtime_menu_state.h"', game)
            self.assertIn("srk_runtime_menu_request_open(&srk_runtime_menu_state)", game)
            self.assertIn("srk_runtime_menu_state_sample(", game)
            self.assertIn("(unsigned int)sk0", game)
            self.assertEqual(game.count("orig_func();"), 1)
            self.assertNotIn("srk_runtime_menu_requested", game)

    def test_state_helper_is_side_effect_free_hardware_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_menu_state_tree(self._source(root), root / "R2")
            state = result.state_source_path.read_text(encoding="utf-8")

            for forbidden in (
                "write_file(",
                "srk_capture_",
                "smpc_cmd(",
                "COMREG",
                "VDP1",
                "VDP2",
                "0x25e",
            ):
                self.assertNotIn(forbidden, state)
            self.assertIn("PAD_LT | PAD_RT", state)
            self.assertIn("PAD_A | PAD_B | PAD_START", state)

    def test_existing_or_nested_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            existing = root / "existing"
            existing.mkdir()
            marker = existing / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(SarooRuntimeMenuStateIntegrationError, "already exists"):
                prepare_runtime_menu_state_tree(source, existing)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

            nested = source / "nested"
            with self.assertRaisesRegex(SarooRuntimeMenuStateIntegrationError, "outside"):
                prepare_runtime_menu_state_tree(source, nested)
            self.assertFalse(nested.exists())

    def test_missing_marker_or_incompatible_hook_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root, marker=False)
            output = root / "missing-marker"
            with self.assertRaisesRegex(SarooRuntimeMenuStateIntegrationError, "marker"):
                prepare_runtime_menu_state_tree(source, output)
            self.assertFalse(output.exists())

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(
                root,
                game_text=GAME_LOAD.replace("srk_runtime_menu_requested = 1;", "/* changed */"),
            )
            output = root / "bad-hook"
            with self.assertRaisesRegex(SarooRuntimeMenuStateIntegrationError, "request event"):
                prepare_runtime_menu_state_tree(source, output)
            self.assertFalse(output.exists())

    def test_module_command_prepares_state_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "cli-out"

            exit_code = prepare_main([str(source), str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "SRK_RUNTIME_MENU_STATE.txt").is_file())
            self.assertTrue(
                (output / "Firm_Saturn" / "srk_runtime_menu_state.c").is_file()
            )


if __name__ == "__main__":
    unittest.main()
