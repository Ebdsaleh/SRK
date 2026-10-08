"""Synthetic tests for SRK's armed post-entry runtime execution proof."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_execution_proof_integration import (
    SarooRuntimeExecutionProofIntegrationError,
    prepare_runtime_execution_proof_tree,
)
from rikai_kotoba.tools.saroo_runtime_execution_proof_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_capture_helper.o  \\
\t\tobj/srk_runtime_input.o  \\
\t\tobj/srk_runtime_menu_state.o  \\
\t\tobj/srk_runtime_video_state.o  \\
\t\tobj/srk_runtime_video_canary.o  \\
\t\tobj/game_load.o\n"""

MAIN_C = '''#include "main.h"
#include "smpc.h"
#include "srk_capture_helper.h"

int update_index;
int srk_wraml_index = -1;
int srk_wramh_index = -1;

void build_menu(void)
{
\tsrk_wramh_index = main_menu.num;
\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");
}

int menu_handler(int index)
{
\tif(index==srk_wramh_index){
\t\treturn 0;
\t}else if(index==update_index){
\t\treturn 1;
\t}
\treturn 0;
}
'''

GAME_LOAD = '''#include "main.h"
#include "smpc.h"
#include "srk_runtime_input.h"
#include "srk_runtime_menu_state.h"
#include "srk_runtime_video_state.h"
#include "srk_runtime_video_canary.h"

static void (*orig_func)(void);
static int sk0, sk1;

static void cdp_hook(void)
{
\tsk0 = *(u16*)0x06020232;
\tsk1 = *(u16*)0x06020236;
\torig_func();
}


static void hook_getkey(void)
{
\t(void)sk0;
}

void launch(void)
{
\tif(game_break_pc){
\t\tset_break_pc(game_break_pc, 0);
\t\tinstall_ubr_isr();
\t}
}
'''

PROOF_H = '''#ifndef SRK_RUNTIME_EXECUTION_PROOF_H
#define SRK_RUNTIME_EXECUTION_PROOF_H
#define SRK_RUNTIME_EXECUTION_PROOF_OK 0
int srk_runtime_execution_proof_arm(void);
int srk_runtime_execution_proof_prepare(void);
void srk_runtime_execution_proof_on_controller_hook(void);
#endif
'''

PROOF_C = '''#include "main.h"
#include "vdp2.h"
#include "srk_runtime_execution_proof.h"
#define SRK_RUNTIME_PROOF_HOOK_SAMPLES 600
#define SRK_RUNTIME_PROOF_BLACK_FRAMES 120
int srk_runtime_execution_proof_arm(void) { return 0; }
int srk_runtime_execution_proof_prepare(void) { return 1; }
void srk_runtime_execution_proof_on_controller_hook(void) { TVMD = TVMD; }
'''


class SarooRuntimeExecutionProofIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, marker: bool = True, game_load: str = GAME_LOAD) -> Path:
        source = root / "SAROO-SRK-RUNTIME-CANARY-R4"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "main.c").write_text(MAIN_C, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(game_load, encoding="utf-8", newline="\n")
        if marker:
            (source / "SRK_RUNTIME_VIDEO_CANARY.txt").write_text(
                "validated R4 canary tree\n", encoding="utf-8"
            )
        return source

    @staticmethod
    def _helpers(root: Path) -> Path:
        helpers = root / "helpers"
        helpers.mkdir()
        (helpers / "srk_runtime_execution_proof.h").write_text(PROOF_H, encoding="utf-8")
        (helpers / "srk_runtime_execution_proof.c").write_text(PROOF_C, encoding="utf-8")
        return helpers

    def test_generates_separate_proof_tree_without_modifying_r4(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            before_main = (source / "Firm_Saturn" / "main.c").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_execution_proof_tree(
                source, root / "out", helper_root=helpers
            )

            self.assertEqual((source / "Firm_Saturn" / "main.c").read_bytes(), before_main)
            self.assertEqual((source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game)
            self.assertTrue(result.helper_source_path.is_file())
            self.assertTrue(result.helper_header_path.is_file())
            self.assertTrue(result.marker_path.is_file())
            self.assertEqual(
                result.makefile_path.read_text(encoding="utf-8").count(
                    "obj/srk_runtime_execution_proof.o"
                ),
                1,
            )

    def test_arm_action_entry_gate_and_post_refresh_hook_are_wired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_execution_proof_tree(
                self._source(root), root / "out", helper_root=self._helpers(root)
            )
            main = result.main_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")

            self.assertIn("SRK Arm Runtime Proof", main)
            self.assertIn("srk_runtime_execution_proof_arm()", main)
            self.assertIn("srk_runtime_execution_proof_prepare()", game)
            self.assertLess(
                game.index("srk_runtime_execution_proof_prepare()"),
                game.index("if(game_break_pc)"),
            )
            self.assertLess(
                game.index("orig_func();"),
                game.index("srk_runtime_execution_proof_on_controller_hook();"),
            )

    def test_real_proof_helper_is_input_independent_bounded_and_exactly_restores_tvmd(self):
        helper = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
            / "srk_runtime_execution_proof.c"
        )
        text = helper.read_text(encoding="utf-8")

        self.assertIn("SRK_RUNTIME_PROOF_HOOK_SAMPLES        600", text)
        self.assertIn("SRK_RUNTIME_PROOF_BLACK_FRAMES        120", text)
        self.assertIn("game_break_handle = srk_runtime_execution_proof_entry_handler", text)
        self.assertIn("saved_tvmd = TVMD;", text)
        self.assertIn("saved_tvmd & (unsigned short)(~DISP)", text)
        self.assertIn("TVMD = saved_tvmd;", text)
        self.assertNotIn("PAD_LT", text)
        self.assertNotIn("PAD_RT", text)
        self.assertNotIn("write_file", text)
        self.assertNotIn("smpc_cmd", text)
        self.assertNotIn("VDP2_VRAM", text)
        self.assertNotIn("VDP2_CRAM", text)
        self.assertNotIn("VDP1_", text)

    def test_refuses_existing_nested_missing_marker_and_bad_hook_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            existing = root / "existing"
            existing.mkdir()

            with self.assertRaisesRegex(SarooRuntimeExecutionProofIntegrationError, "already exists"):
                prepare_runtime_execution_proof_tree(source, existing, helper_root=helpers)
            with self.assertRaisesRegex(SarooRuntimeExecutionProofIntegrationError, "outside"):
                prepare_runtime_execution_proof_tree(source, source / "nested", helper_root=helpers)

            no_marker = self._source(root / "a", marker=False)
            with self.assertRaisesRegex(SarooRuntimeExecutionProofIntegrationError, "marker"):
                prepare_runtime_execution_proof_tree(no_marker, root / "out-a", helper_root=helpers)
            self.assertFalse((root / "out-a").exists())

            broken = self._source(
                root / "b",
                game_load=GAME_LOAD.replace("orig_func();", "other();"),
            )
            with self.assertRaisesRegex(SarooRuntimeExecutionProofIntegrationError, "controller-hook tail"):
                prepare_runtime_execution_proof_tree(broken, root / "out-b", helper_root=helpers)
            self.assertFalse((root / "out-b").exists())

    def test_module_command_prepares_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            real_helpers = (
                Path(__file__).resolve().parents[1]
                / "integrations"
                / "saroo"
                / "Firm_Saturn"
            )
            self.assertTrue((real_helpers / "srk_runtime_execution_proof.c").is_file())
            self.assertTrue((real_helpers / "srk_runtime_execution_proof.h").is_file())

            output = root / "cli-out"
            self.assertEqual(prepare_main([str(source), str(output)]), 0)
            self.assertTrue((output / "SRK_RUNTIME_EXECUTION_PROOF.txt").is_file())


if __name__ == "__main__":
    unittest.main()
