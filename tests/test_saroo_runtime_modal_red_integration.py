"""Synthetic tests for SRK's first modal runtime red-shell preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_modal_red_integration import (
    SarooRuntimeModalRedIntegrationError,
    prepare_runtime_modal_red_tree,
)
from rikai_kotoba.tools.saroo_runtime_modal_red_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_runtime_input.o  \\
\t\tobj/srk_runtime_menu_state.o  \\
\t\tobj/srk_runtime_video_state.o  \\
\t\tobj/srk_runtime_video_canary.o  \\
\t\tobj/game_load.o\n"""

GAME_LOAD = '''#include "main.h"
#include "smpc.h"
#include "srk_runtime_input.h"
#include "srk_runtime_menu_state.h"
#include "srk_runtime_video_state.h"
#include "srk_runtime_video_canary.h"

static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;
static SRK_RUNTIME_MENU_STATE srk_runtime_menu_state;
static SRK_RUNTIME_VIDEO_STATE srk_runtime_video_state;

static void (*orig_func)(void);
static int sk0, sk1;

static void cdp_hook(void)
{
\tint srk_event;
\tint srk_menu_event;
\tsk0 = *(u16*)0x06020232;
\tsk1 = *(u16*)0x06020236;
\tsrk_event = srk_runtime_input_sample(
\t\t&srk_runtime_input_state,
\t\t(unsigned int)sk0
\t);
\tsrk_menu_event = SRK_RUNTIME_MENU_EVENT_NONE;
\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU){
\t\tsrk_menu_event = srk_runtime_menu_request_open(&srk_runtime_menu_state);
\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED){
\t\t\tif(srk_runtime_video_state_capture(&srk_runtime_video_state))
\t\t\t\tsrk_runtime_video_canary_pulse(&srk_runtime_video_state);
\t\t}
\t}
\tif(srk_runtime_menu_state.active){
\t\tsrk_menu_event = srk_runtime_menu_state_sample(
\t\t\t&srk_runtime_menu_state,
\t\t\t(unsigned int)sk0
\t\t);
\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_RESUMED)
\t\t\tsrk_runtime_video_state_reset(&srk_runtime_video_state);
\t}
\torig_func();
}
'''

MODAL_H = '''#ifndef SRK_RUNTIME_MODAL_RED_H
#define SRK_RUNTIME_MODAL_RED_H
typedef void (*SRK_RUNTIME_CONTROLLER_REFRESH)(void);
int srk_runtime_modal_red_run(void*, void*, const void*, SRK_RUNTIME_CONTROLLER_REFRESH, volatile unsigned short*);
#endif
'''

MODAL_C = '''#include "srk_runtime_modal_red.h"
#define SRK_RUNTIME_MODAL_RED_MAX_FRAMES 600
int srk_runtime_modal_red_run(void *a, void *b, const void *c, SRK_RUNTIME_CONTROLLER_REFRESH refresh_controller, volatile unsigned short *controller_buttons)
{
    int frame = 0;
    (void)a; (void)b; (void)c;
    refresh_controller();
    frame += *controller_buttons;
    return frame;
}
'''

CANARY_H = '''#ifndef SRK_RUNTIME_VIDEO_CANARY_H
#define SRK_RUNTIME_VIDEO_CANARY_H
int srk_runtime_video_canary_apply_solid_red(const void *state);
int srk_runtime_video_canary_restore(const void *state);
int srk_runtime_video_canary_pulse(const void *state);
#endif
'''

CANARY_C = '''#include "srk_runtime_video_canary.h"
int srk_runtime_video_canary_apply_solid_red(const void *state) { return state != 0; }
int srk_runtime_video_canary_restore(const void *state) { return state != 0; }
int srk_runtime_video_canary_pulse(const void *state) { return state != 0; }
'''


class SarooRuntimeModalRedIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, marker: bool = True, game_load: str = GAME_LOAD) -> Path:
        source = root / "SAROO-SRK-RUNTIME-CANARY-R4"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(game_load, encoding="utf-8", newline="\n")
        (firm / "srk_runtime_video_canary.c").write_text("R4 canary source\n", encoding="utf-8")
        (firm / "srk_runtime_video_canary.h").write_text("R4 canary header\n", encoding="utf-8")
        if marker:
            (source / "SRK_RUNTIME_VIDEO_CANARY.txt").write_text(
                "validated R4 runtime canary tree\n", encoding="utf-8"
            )
        return source

    @staticmethod
    def _helpers(root: Path) -> Path:
        helpers = root / "helpers"
        helpers.mkdir()
        (helpers / "srk_runtime_modal_red.h").write_text(MODAL_H, encoding="utf-8")
        (helpers / "srk_runtime_modal_red.c").write_text(MODAL_C, encoding="utf-8")
        (helpers / "srk_runtime_video_canary.h").write_text(CANARY_H, encoding="utf-8")
        (helpers / "srk_runtime_video_canary.c").write_text(CANARY_C, encoding="utf-8")
        return helpers

    def test_generates_separate_modal_tree_without_modifying_r4(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            before_make = (source / "Firm_Saturn" / "Makefile").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_modal_red_tree(
                source, root / "out", helper_root=helpers
            )

            self.assertEqual((source / "Firm_Saturn" / "Makefile").read_bytes(), before_make)
            self.assertEqual((source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game)
            self.assertTrue(result.modal_source_path.is_file())
            self.assertTrue(result.modal_header_path.is_file())
            self.assertTrue(result.canary_source_path.is_file())
            self.assertTrue(result.canary_header_path.is_file())
            self.assertTrue(result.marker_path.is_file())

    def test_generated_hook_enters_modal_loop_and_returns_before_outer_refresh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_modal_red_tree(
                self._source(root), root / "out", helper_root=self._helpers(root)
            )
            makefile = result.makefile_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")

            self.assertEqual(makefile.count("obj/srk_runtime_modal_red.o"), 1)
            self.assertIn('#include "srk_runtime_modal_red.h"', game)
            self.assertIn("srk_runtime_modal_red_run(", game)
            self.assertIn("&srk_runtime_input_state", game)
            self.assertIn("&srk_runtime_menu_state", game)
            self.assertIn("&srk_runtime_video_state", game)
            self.assertIn("orig_func,", game)
            self.assertIn("(volatile unsigned short*)0x06020232", game)
            self.assertIn("return;", game)
            self.assertEqual(game.count("orig_func();"), 1)

    def test_real_modal_helper_is_bounded_release_gated_and_restores(self):
        helper = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
            / "srk_runtime_modal_red.c"
        )
        text = helper.read_text(encoding="utf-8")

        self.assertIn("SRK_RUNTIME_MODAL_RED_MAX_FRAMES 600", text)
        self.assertIn("srk_runtime_video_canary_apply_solid_red(video_state)", text)
        self.assertIn("refresh_controller();", text)
        controller_read = "buttons = (unsigned int)(*controller_buttons);"
        self.assertIn(controller_read, text)
        self.assertLess(text.index("refresh_controller();"), text.index(controller_read))
        self.assertLess(
            text.index(controller_read),
            text.index("srk_runtime_input_sample(input_state, buttons)"),
        )
        self.assertIn("SRK_RUNTIME_INPUT_OPEN_MENU", text)
        self.assertIn("srk_runtime_video_canary_restore(video_state)", text)
        self.assertIn("srk_runtime_menu_state_reset(menu_state)", text)
        self.assertNotIn("smpc_cmd", text)
        self.assertNotIn("write_file", text)
        self.assertNotIn("VDP2_VRAM", text)
        self.assertNotIn("VDP2_CRAM", text)
        self.assertNotIn("VDP1_", text)

    def test_real_canary_helper_can_force_solid_red_and_restore_exact_state(self):
        helper = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
            / "srk_runtime_video_canary.c"
        )
        text = helper.read_text(encoding="utf-8")

        self.assertIn("SRK_RUNTIME_VIDEO_SOLID_RED_POSITIVE   0x00ffu", text)
        self.assertIn("SRK_RUNTIME_VIDEO_SOLID_RED_NEGATIVE   0x0101u", text)
        self.assertIn("srk_runtime_video_canary_apply_solid_red", text)
        self.assertIn("srk_runtime_video_canary_restore", text)
        for register, field in (
            ("CLOFEN", "clofen"),
            ("CLOFSL", "clofsl"),
            ("COAR", "coar"),
            ("COAG", "coag"),
            ("COAB", "coab"),
            ("COBR", "cobr"),
            ("COBG", "cobg"),
            ("COBB", "cobb"),
        ):
            self.assertIn(f"{register} = state->{field};", text)

    def test_refuses_existing_nested_missing_marker_and_bad_r4_anchor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            existing = root / "existing"
            existing.mkdir()

            with self.assertRaisesRegex(SarooRuntimeModalRedIntegrationError, "already exists"):
                prepare_runtime_modal_red_tree(source, existing, helper_root=helpers)
            with self.assertRaisesRegex(SarooRuntimeModalRedIntegrationError, "outside"):
                prepare_runtime_modal_red_tree(source, source / "nested", helper_root=helpers)

            no_marker = self._source(root / "a", marker=False)
            with self.assertRaisesRegex(SarooRuntimeModalRedIntegrationError, "marker"):
                prepare_runtime_modal_red_tree(no_marker, root / "out-a", helper_root=helpers)
            self.assertFalse((root / "out-a").exists())

            broken = self._source(
                root / "b",
                game_load=GAME_LOAD.replace(
                    "srk_runtime_video_canary_pulse(&srk_runtime_video_state);",
                    "other();",
                ),
            )
            with self.assertRaisesRegex(SarooRuntimeModalRedIntegrationError, "R4 canary-open"):
                prepare_runtime_modal_red_tree(broken, root / "out-b", helper_root=helpers)
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
            self.assertTrue((real_helpers / "srk_runtime_modal_red.c").is_file())
            self.assertTrue((real_helpers / "srk_runtime_modal_red.h").is_file())
            self.assertTrue((real_helpers / "srk_runtime_video_canary.c").is_file())
            self.assertTrue((real_helpers / "srk_runtime_video_canary.h").is_file())

            output = root / "cli-out"
            self.assertEqual(prepare_main([str(source), str(output)]), 0)
            self.assertTrue((output / "SRK_RUNTIME_MODAL_RED.txt").is_file())


if __name__ == "__main__":
    unittest.main()
