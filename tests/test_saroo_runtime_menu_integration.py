"""Synthetic tests for the safe SRK runtime-menu input-hook tranche."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_menu_integration import (
    SarooRuntimeMenuIntegrationError,
    prepare_runtime_menu_input_tree,
)
from rikai_kotoba.tools.saroo_runtime_menu_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_capture_helper.o  \\
\t\tobj/game_load.o  \\
\t\tobj/version.o\n"""

GAME_LOAD = '''#include "main.h"
#include "smpc.h"

static int (*cdp_boot_game)(void);
static int sk0, sk1;
static int bios_ver;

static void (*orig_func)(void);

static void cdp_hook(void)
{
\tsk0 = *(u16*)0x06020232;
\tsk1 = *(u16*)0x06020236;
\torig_func();
}

void my_cdplayer(void)
{
\tvoid (*go)(int);

\tgo = (void*)0x06000680;
\tgo(0);
}
'''


class SarooRuntimeMenuIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(
        root: Path,
        *,
        game_load: str = GAME_LOAD,
        marker: bool = True,
    ) -> Path:
        source = root / "SAROO-SRK-CAPTURE"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(game_load, encoding="utf-8", newline="\n")
        if marker:
            (source / "SRK_CAPTURE_MENU.txt").write_text(
                "validated capture-menu tree\n",
                encoding="utf-8",
            )
        return source

    def test_generates_separate_input_hook_tree_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            before_makefile = (source / "Firm_Saturn" / "Makefile").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()
            output = root / "SAROO-SRK-RUNTIME-MENU"

            result = prepare_runtime_menu_input_tree(source, output)

            self.assertEqual(
                (source / "Firm_Saturn" / "Makefile").read_bytes(),
                before_makefile,
            )
            self.assertEqual(
                (source / "Firm_Saturn" / "game_load.c").read_bytes(),
                before_game,
            )
            self.assertTrue(result.runtime_source_path.is_file())
            self.assertTrue(result.runtime_header_path.is_file())
            self.assertTrue(result.marker_path.is_file())

            makefile = result.makefile_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")
            marker = result.marker_path.read_text(encoding="utf-8")

            self.assertEqual(makefile.count("obj/srk_runtime_input.o"), 1)
            self.assertEqual(game.count('#include "srk_runtime_input.h"'), 1)
            self.assertIn("static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;", game)
            self.assertIn("static int srk_runtime_menu_requested = 0;", game)
            self.assertIn("srk_runtime_input_sample(", game)
            self.assertIn("(unsigned int)sk0", game)
            self.assertIn("srk_runtime_menu_requested = 1;", game)
            self.assertIn("srk_runtime_input_reset(&srk_runtime_input_state);", game)
            self.assertIn("srk_runtime_menu_requested = 0;", game)
            self.assertIn("internal runtime-menu request latch only", marker)
            self.assertIn("No SD writes", marker)
            self.assertIn("No runtime menu renderer", marker)

    def test_generated_hook_does_not_add_active_smpc_io_capture_or_vdp_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_menu_input_tree(
                self._source(root),
                root / "out",
            )

            game = result.game_load_path.read_text(encoding="utf-8")
            runtime = result.runtime_source_path.read_text(encoding="utf-8")
            combined = game + "\n" + runtime

            self.assertNotIn("pad_read(", combined)
            self.assertNotIn("smpc_cmd(", combined)
            self.assertNotIn("write_file(", combined)
            self.assertNotIn("srk_capture_work_ram", combined)
            self.assertNotIn("VDP1", combined)
            self.assertNotIn("VDP2", combined)
            self.assertNotIn("COMREG", combined)

    def test_completed_controller_hook_keeps_original_callback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_menu_input_tree(
                self._source(root),
                root / "out",
            )
            game = result.game_load_path.read_text(encoding="utf-8")

            sample_pos = game.index("srk_runtime_input_sample(")
            callback_pos = game.index("\torig_func();", sample_pos)
            self.assertGreater(callback_pos, sample_pos)
            self.assertEqual(game.count("\torig_func();"), 1)

    def test_existing_output_is_refused_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "already-there"
            output.mkdir()
            keep = output / "keep.txt"
            keep.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(SarooRuntimeMenuIntegrationError, "already exists"):
                prepare_runtime_menu_input_tree(source, output)

            self.assertEqual(keep.read_text(encoding="utf-8"), "keep")

    def test_output_inside_source_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)

            with self.assertRaisesRegex(SarooRuntimeMenuIntegrationError, "outside"):
                prepare_runtime_menu_input_tree(source, source / "nested-output")

    def test_incompatible_controller_hook_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            broken = GAME_LOAD.replace(
                "\tsk0 = *(u16*)0x06020232;",
                "\t/* changed upstream hook */",
            )
            source = self._source(root, game_load=broken)
            output = root / "out"

            with self.assertRaisesRegex(
                SarooRuntimeMenuIntegrationError,
                "completed controller hook",
            ):
                prepare_runtime_menu_input_tree(source, output)

            self.assertFalse(output.exists())

    def test_missing_capture_menu_marker_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root, marker=False)
            output = root / "out"

            with self.assertRaisesRegex(SarooRuntimeMenuIntegrationError, "marker"):
                prepare_runtime_menu_input_tree(source, output)

            self.assertFalse(output.exists())

    def test_module_command_prepares_runtime_input_hook_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "cli-out"

            exit_code = prepare_main([str(source), str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "SRK_RUNTIME_MENU.txt").is_file())
            game = (output / "Firm_Saturn" / "game_load.c").read_text(
                encoding="utf-8"
            )
            self.assertIn("SRK_RUNTIME_INPUT_OPEN_MENU", game)
            self.assertIn("(unsigned int)sk0", game)


if __name__ == "__main__":
    unittest.main()
