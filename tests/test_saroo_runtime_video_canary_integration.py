"""Synthetic tests for SRK's bounded runtime-video canary preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_video_canary_integration import (
    SarooRuntimeVideoCanaryIntegrationError,
    prepare_runtime_video_canary_tree,
)
from rikai_kotoba.tools.saroo_runtime_video_canary_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_runtime_input.o  \\
\t\tobj/srk_runtime_menu_state.o  \\
\t\tobj/srk_runtime_video_state.o  \\
\t\tobj/game_load.o\n"""

GAME_LOAD = '''#include "main.h"
#include "smpc.h"
#include "srk_runtime_input.h"
#include "srk_runtime_menu_state.h"
#include "srk_runtime_video_state.h"

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
\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED)
\t\t\tsrk_runtime_video_state_capture(&srk_runtime_video_state);
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

CANARY_H = '''#ifndef SRK_RUNTIME_VIDEO_CANARY_H
#define SRK_RUNTIME_VIDEO_CANARY_H
#include "srk_runtime_video_state.h"
int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state);
#endif
'''

CANARY_C = '''#include "main.h"
#include "vdp2.h"
#include "srk_runtime_video_canary.h"
int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state)
{
    if(!state || !state->valid) return 0;
    COAR = 0x0060u; COAG = 0; COAB = 0;
    COBR = 0x0060u; COBG = 0; COBB = 0;
    CLOFEN = (unsigned short)(state->clofen | 0x007fu);
    COAR = state->coar; COAG = state->coag; COAB = state->coab;
    COBR = state->cobr; COBG = state->cobg; COBB = state->cobb;
    CLOFSL = state->clofsl; CLOFEN = state->clofen;
    return 1;
}
'''


class SarooRuntimeVideoCanaryIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, marker: bool = True, game_load: str = GAME_LOAD) -> Path:
        source = root / "SAROO-SRK-RUNTIME-VIDEO-R3"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(game_load, encoding="utf-8", newline="\n")
        (firm / "srk_runtime_video_state.c").write_text("read-only state helper\n", encoding="utf-8")
        (firm / "srk_runtime_video_state.h").write_text("read-only state header\n", encoding="utf-8")
        if marker:
            (source / "SRK_RUNTIME_VIDEO_STATE.txt").write_text(
                "validated read-only runtime video tree\n", encoding="utf-8"
            )
        return source

    @staticmethod
    def _helpers(root: Path) -> Path:
        helpers = root / "helpers"
        helpers.mkdir()
        (helpers / "srk_runtime_video_canary.h").write_text(CANARY_H, encoding="utf-8")
        (helpers / "srk_runtime_video_canary.c").write_text(CANARY_C, encoding="utf-8")
        return helpers

    def test_generates_separate_canary_tree_without_modifying_r3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            before_make = (source / "Firm_Saturn" / "Makefile").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_video_canary_tree(
                source, root / "out", helper_root=helpers
            )

            self.assertEqual((source / "Firm_Saturn" / "Makefile").read_bytes(), before_make)
            self.assertEqual((source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game)
            self.assertTrue(result.canary_source_path.is_file())
            self.assertTrue(result.canary_header_path.is_file())
            self.assertTrue(result.marker_path.is_file())
            self.assertEqual(
                result.makefile_path.read_text(encoding="utf-8").count(
                    "obj/srk_runtime_video_canary.o"
                ),
                1,
            )

    def test_open_event_captures_then_runs_canary_and_preserves_callback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_video_canary_tree(
                self._source(root), root / "out", helper_root=self._helpers(root)
            )
            game = result.game_load_path.read_text(encoding="utf-8")

            capture = "srk_runtime_video_state_capture(&srk_runtime_video_state)"
            canary = "srk_runtime_video_canary_pulse(&srk_runtime_video_state)"
            self.assertIn('#include "srk_runtime_video_canary.h"', game)
            self.assertIn(capture, game)
            self.assertIn(canary, game)
            self.assertLess(game.index(capture), game.index(canary))
            self.assertEqual(game.count("orig_func();"), 1)

    def test_real_canary_helper_is_narrow_and_restores_owned_registers(self):
        helper = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
            / "srk_runtime_video_canary.c"
        )
        text = helper.read_text(encoding="utf-8")

        self.assertIn("0x007fu", text)
        self.assertRegex(text, r"#define\s+SRK_RUNTIME_VIDEO_CANARY_FRAMES\s+3\b")
        self.assertIn("CLOFEN = (unsigned short)(state->clofen", text)
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
        self.assertNotIn("VDP2_VRAM", text)
        self.assertNotIn("VDP2_CRAM", text)
        self.assertNotIn("VDP1_", text)
        self.assertNotIn("write_file", text)
        self.assertNotIn("smpc_cmd", text)

    def test_existing_nested_missing_marker_and_bad_anchor_are_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            existing = root / "existing"
            existing.mkdir()

            with self.assertRaisesRegex(SarooRuntimeVideoCanaryIntegrationError, "already exists"):
                prepare_runtime_video_canary_tree(source, existing, helper_root=helpers)
            with self.assertRaisesRegex(SarooRuntimeVideoCanaryIntegrationError, "outside"):
                prepare_runtime_video_canary_tree(source, source / "nested", helper_root=helpers)

            no_marker = self._source(root / "a", marker=False)
            with self.assertRaisesRegex(SarooRuntimeVideoCanaryIntegrationError, "marker"):
                prepare_runtime_video_canary_tree(no_marker, root / "out-a", helper_root=helpers)
            self.assertFalse((root / "out-a").exists())

            broken = self._source(
                root / "b",
                game_load=GAME_LOAD.replace(
                    "srk_runtime_video_state_capture(&srk_runtime_video_state);",
                    "other();",
                ),
            )
            with self.assertRaisesRegex(SarooRuntimeVideoCanaryIntegrationError, "capture anchor"):
                prepare_runtime_video_canary_tree(broken, root / "out-b", helper_root=helpers)
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
            self.assertTrue((real_helpers / "srk_runtime_video_canary.c").is_file())
            self.assertTrue((real_helpers / "srk_runtime_video_canary.h").is_file())

            output = root / "cli-out"
            self.assertEqual(prepare_main([str(source), str(output)]), 0)
            self.assertTrue((output / "SRK_RUNTIME_VIDEO_CANARY.txt").is_file())


if __name__ == "__main__":
    unittest.main()
