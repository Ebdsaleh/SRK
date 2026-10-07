"""Synthetic tests for title-neutral one-shot in-game capture preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.ingame_entry_integration import (
    SarooInGameEntryIntegrationError,
    prepare_ingame_entry_capture_tree,
)
from rikai_kotoba.tools.saroo_ingame_entry_prepare import main as prepare_main


MAIN_CAPTURE = '''#include "main.h"
#include "smpc.h"
#include "srk_capture_helper.h"

int update_index;
int srk_wraml_index = -1;
int srk_wramh_index = -1;

int main_handle(int ctrl)
{
\tint index = main_menu.current;
\tif(index==srk_wramh_index){
\t\treturn 0;
\t}else if(index==update_index){
\t\treturn 0;
\t}
\treturn 0;
}

void menu_init(void)
{
\tint i;
\tfor(i=0; i<menu_str_nr; i++){
\t\tadd_menu_item(&main_menu, TT(menu_str[i]));
\t}
\tsrk_wraml_index = main_menu.num;
\tadd_menu_item(&main_menu, "SRK Capture WRAM-L");
\tsrk_wramh_index = main_menu.num;
\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");
}
'''

GAME_LOAD = '''#include "main.h"
#include "smpc.h"

void patch_game(void)
{
\tif(game_break_pc){
\t\tset_break_pc(game_break_pc, 0);
\t\tinstall_ubr_isr();
\t}
}
'''

HELPER_H = '''#ifndef SRK_CAPTURE_HELPER_H
#define SRK_CAPTURE_HELPER_H
#define SRK_CAPTURE_OK 0
int srk_capture_work_ram_high(char *path);
#endif
'''

HELPER_C = '''#include "main.h"
#include "srk_capture_helper.h"
int srk_capture_work_ram_high(char *path) { (void)path; return 0; }
'''


class SarooInGameEntryIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, capture_menu: bool = True) -> Path:
        source = root / "SAROO-SRK-CAPTURE"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        main_text = MAIN_CAPTURE if capture_menu else MAIN_CAPTURE.replace(
            'SRK Capture WRAM-H', 'Not a capture tree'
        )
        (firm / "main.c").write_text(main_text, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(GAME_LOAD, encoding="utf-8", newline="\n")
        (firm / "srk_capture_helper.h").write_text(HELPER_H, encoding="utf-8", newline="\n")
        (firm / "srk_capture_helper.c").write_text(HELPER_C, encoding="utf-8", newline="\n")
        (source / "SRK_CAPTURE_MENU.txt").write_text("validated menu tree\n", encoding="utf-8")
        return source

    def test_creates_separate_tree_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            before = {
                path.name: path.read_bytes()
                for path in (source / "Firm_Saturn").iterdir()
                if path.is_file()
            }
            output = root / "SAROO-SRK-INGAME-FIRSTREAD"

            result = prepare_ingame_entry_capture_tree(source, output)

            after = {
                path.name: path.read_bytes()
                for path in (source / "Firm_Saturn").iterdir()
                if path.is_file()
            }
            self.assertEqual(after, before)
            self.assertIsNone(result.capture_pc)
            self.assertTrue(result.marker_path.is_file())
            main = result.main_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")
            helper = result.helper_source_path.read_text(encoding="utf-8")
            header = result.helper_header_path.read_text(encoding="utf-8")
            self.assertIn("SRK Arm 1st-Read Capture", main)
            self.assertIn("srk_arm_first_read_capture", main)
            self.assertIn("srk_prepare_first_read_capture", game)
            self.assertIn('#include "srk_capture_helper.h"', game)
            self.assertIn("SRK_IP_MEMORY_BASE          0x06002000u", helper)
            self.assertIn("SRK_IP_FIRST_READ_OFFSET    0x000000f0u", helper)
            self.assertIn("BE32((void*)(SRK_IP_MEMORY_BASE + SRK_IP_FIRST_READ_OFFSET))", helper)
            self.assertIn('"/SAROO/SRK_GAME_WRAMH.BIN"', helper)
            self.assertIn("set_break_pc(0, 0);", helper)
            self.assertIn("game_break_handle = 0;", helper)
            self.assertIn("SRK_CAPTURE_ERR_FIRST_READ", header)

    def test_generated_helper_rejects_invalid_or_out_of_wramh_first_read_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            result = prepare_ingame_entry_capture_tree(source, root / "out")
            helper = result.helper_source_path.read_text(encoding="utf-8")

            self.assertIn("first_read_pc<0x06002000u", helper)
            self.assertIn("first_read_pc>=SRK_WRAMH_END_EXCLUSIVE", helper)
            self.assertIn("(first_read_pc&1u)!=0u", helper)
            self.assertIn("game_break_pc = 0;", helper)

    def test_explicit_pc_is_local_generator_data_and_changes_trigger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "explicit"

            result = prepare_ingame_entry_capture_tree(
                source,
                output,
                capture_pc=0x06012000,
            )

            self.assertEqual(result.capture_pc, 0x06012000)
            main = result.main_path.read_text(encoding="utf-8")
            helper = result.helper_source_path.read_text(encoding="utf-8")
            marker = result.marker_path.read_text(encoding="utf-8")
            self.assertIn("SRK Arm PC Capture", main)
            self.assertNotIn("SRK Arm 1st-Read Capture", main)
            self.assertIn("#define SRK_EXPLICIT_CAPTURE_PC     0x06012000u", helper)
            self.assertIn("first_read_pc = SRK_EXPLICIT_CAPTURE_PC;", helper)
            self.assertIn("first_read_pc<SRK_WRAMH_START", helper)
            self.assertNotIn(
                "first_read_pc = BE32((void*)(SRK_IP_MEMORY_BASE + SRK_IP_FIRST_READ_OFFSET));",
                helper,
            )
            self.assertIn("caller-supplied SH-2 PC 0x06012000", marker)
            self.assertIn("no commercial-title-specific breakpoint constant", marker)

    def test_explicit_pc_is_validated_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)

            for value in (0x05FFFFFE, 0x06100000, 0x06012001):
                output = root / f"out-{value:08x}"
                with self.assertRaises(SarooInGameEntryIntegrationError):
                    prepare_ingame_entry_capture_tree(
                        source,
                        output,
                        capture_pc=value,
                    )
                self.assertFalse(output.exists())

    def test_module_command_accepts_hex_capture_pc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "explicit-cli"

            exit_code = prepare_main(
                [
                    str(source),
                    str(output),
                    "--capture-pc",
                    "0x06012000",
                ]
            )

            self.assertEqual(exit_code, 0)
            helper = (output / "Firm_Saturn" / "srk_capture_helper.c").read_text(
                encoding="utf-8"
            )
            self.assertIn("0x06012000u", helper)

    def test_existing_output_is_refused_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "SAROO-SRK-INGAME-FIRSTREAD"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(SarooInGameEntryIntegrationError, "already exists"):
                prepare_ingame_entry_capture_tree(source, output)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_output_inside_source_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)

            with self.assertRaisesRegex(SarooInGameEntryIntegrationError, "outside"):
                prepare_ingame_entry_capture_tree(source, source / "nested-output")

    def test_non_capture_menu_source_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root, capture_menu=False)
            output = root / "out"

            with self.assertRaisesRegex(SarooInGameEntryIntegrationError, "capture-menu"):
                prepare_ingame_entry_capture_tree(source, output)

            self.assertFalse(output.exists())

    def test_marker_documents_boot_spec_limit_and_one_shot_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "out"

            result = prepare_ingame_entry_capture_tree(source, output)
            marker = result.marker_path.read_text(encoding="utf-8")

            self.assertIn("0x060020F0", marker)
            self.assertIn("not guaranteed to execute", marker)
            self.assertIn("after the first instruction", marker)
            self.assertIn("one-shot", marker)
            self.assertIn("SRK_GAME_WRAMH.BIN", marker)


if __name__ == "__main__":
    unittest.main()
