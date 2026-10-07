"""Synthetic tests for the controller-accessible SAROO capture-menu layer."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.capture_menu_integration import (
    SarooCaptureMenuIntegrationError,
    prepare_capture_menu_tree,
)


MAIN = '''#include "main.h"
#include "smpc.h"

char *menu_str[] = {
    "one",
};
int menu_str_nr = sizeof(menu_str)/sizeof(char*);
char *update_str = "update";
int update_index;

MENU_DESC main_menu;

int main_handle(int ctrl)
{
    int index = main_menu.current;
    if(index==4){
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
    if(check_update()){
        add_menu_item(&main_menu, TT(update_str));
        update_index = i;
    }
}
'''.replace("    ", "\t")


class SarooCaptureMenuIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, main_text: str = MAIN, include_helpers: bool = True) -> Path:
        source = root / "SAROO-SRK"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "main.c").write_text(main_text, encoding="utf-8", newline="\n")
        if include_helpers:
            (firm / "srk_capture_helper.c").write_text("/* helper */\n", encoding="utf-8")
            (firm / "srk_capture_helper.h").write_text(
                "#define SRK_CAPTURE_OK 0\n"
                "int srk_capture_work_ram_low(char *path);\n"
                "int srk_capture_work_ram_high(char *path);\n",
                encoding="utf-8",
            )
        (source / "SRK_INTEGRATION.txt").write_text("base\n", encoding="utf-8")
        return source

    def test_creates_second_tree_and_leaves_validated_source_untouched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            before = (source / "Firm_Saturn" / "main.c").read_bytes()
            output = root / "SAROO-SRK-CAPTURE"

            result = prepare_capture_menu_tree(source, output)

            self.assertEqual((source / "Firm_Saturn" / "main.c").read_bytes(), before)
            self.assertTrue(result.marker_path.is_file())
            patched = result.main_path.read_text(encoding="utf-8")
            self.assertEqual(patched.count('#include "srk_capture_helper.h"'), 1)
            self.assertEqual(patched.count("SRK Capture WRAM-L"), 1)
            self.assertEqual(patched.count("SRK Capture WRAM-H"), 1)
            self.assertEqual(patched.count("srk_capture_work_ram_low"), 1)
            self.assertEqual(patched.count("srk_capture_work_ram_high"), 1)
            self.assertIn("/SAROO/SRK_WRAML.BIN", patched)
            self.assertIn("/SAROO/SRK_WRAMH.BIN", patched)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "SAROO-SRK-CAPTURE"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(SarooCaptureMenuIntegrationError, "already exists"):
                prepare_capture_menu_tree(source, output)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_missing_capture_helpers_are_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root, include_helpers=False)
            output = root / "out"

            with self.assertRaisesRegex(SarooCaptureMenuIntegrationError, "helper"):
                prepare_capture_menu_tree(source, output)

            self.assertFalse(output.exists())

    def test_incompatible_main_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root, main_text='#include "main.h"\n')
            output = root / "out"

            with self.assertRaisesRegex(SarooCaptureMenuIntegrationError, "main.c"):
                prepare_capture_menu_tree(source, output)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
