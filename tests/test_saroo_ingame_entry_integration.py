"""Synthetic tests for title-neutral one-shot game-entry capture preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.ingame_entry_integration import (
    SarooInGameEntryIntegrationError,
    prepare_ingame_entry_capture_tree,
)


MAIN_CAPTURE = '''#include "main.h"
#include "smpc.h"
#include "srk_capture_helper.h"

int update_index;
int srk_wraml_index = -1;
int srk_wramh_index = -1;

int main_handle(int ctrl)
{
	int index = main_menu.current;
	if(index==srk_wramh_index){
		return 0;
	}else if(index==update_index){
		return 0;
	}
	return 0;
}

void menu_init(void)
{
	int i;
	for(i=0; i<menu_str_nr; i++){
		add_menu_item(&main_menu, TT(menu_str[i]));
	}
	srk_wraml_index = main_menu.num;
	add_menu_item(&main_menu, "SRK Capture WRAM-L");
	srk_wramh_index = main_menu.num;
	add_menu_item(&main_menu, "SRK Capture WRAM-H");
}
'''

GAME_LOAD = '''#include "main.h"
#include "smpc.h"

void patch_game(void)
{
	if(game_break_pc){
		set_break_pc(game_break_pc, 0);
		install_ubr_isr();
	}
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
            output = root / "SAROO-SRK-INGAME-ENTRY"

            result = prepare_ingame_entry_capture_tree(source, output)

            after = {
                path.name: path.read_bytes()
                for path in (source / "Firm_Saturn").iterdir()
                if path.is_file()
            }
            self.assertEqual(after, before)
            self.assertTrue(result.marker_path.is_file())
            main = result.main_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")
            helper = result.helper_source_path.read_text(encoding="utf-8")
            header = result.helper_header_path.read_text(encoding="utf-8")
            self.assertIn("SRK Arm Game-Entry Capture", main)
            self.assertIn("srk_arm_game_entry_capture", main)
            self.assertIn("srk_prepare_game_entry_capture", game)
            self.assertIn('#include "srk_capture_helper.h"', game)
            self.assertIn("SRK_GAME_ENTRY_POINTER_ADDRESS 0x06000284u", helper)
            self.assertIn('"/SAROO/SRK_GAME_WRAMH.BIN"', helper)
            self.assertIn("set_break_pc(0, 0);", helper)
            self.assertIn("game_break_handle = 0;", helper)
            self.assertIn("SRK_CAPTURE_ERR_GAME_ENTRY", header)

    def test_existing_output_is_refused_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "SAROO-SRK-INGAME-ENTRY"
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

    def test_marker_documents_one_shot_entry_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "out"

            result = prepare_ingame_entry_capture_tree(source, output)
            marker = result.marker_path.read_text(encoding="utf-8")

            self.assertIn("0x06000284", marker)
            self.assertIn("after the first instruction", marker)
            self.assertIn("one-shot", marker)
            self.assertIn("SRK_GAME_WRAMH.BIN", marker)


if __name__ == "__main__":
    unittest.main()
