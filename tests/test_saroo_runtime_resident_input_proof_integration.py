"""Synthetic tests for SRK's R9 resident runtime-input proof."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_input_proof import (
    SarooRuntimeResidentInputProofError,
    inspect_runtime_resident_input_proof,
)
from rikai_kotoba.hardware.saturn.saroo.runtime_resident_input_proof_integration import (
    SarooRuntimeResidentInputProofIntegrationError,
    prepare_runtime_resident_input_proof_tree,
)
from rikai_kotoba.tools.saroo_runtime_resident_input_proof_inspect import main as inspect_main
from rikai_kotoba.tools.saroo_runtime_resident_input_proof_prepare import main as prepare_main


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/srk_capture_helper.o  \\
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

static void read_1st(void)
{
\tpatch_game((char*)0x06002020);
\tif(need_bup){
\t\treturn;
\t}
}
'''


def _put_be16(buf: bytearray, offset: int, value: int) -> None:
    buf[offset : offset + 2] = int(value).to_bytes(2, "big")


def _put_be32(buf: bytearray, offset: int, value: int) -> None:
    buf[offset : offset + 4] = int(value).to_bytes(4, "big")


def _slot(
    stage: int,
    buttons: int,
    callbacks: int,
    samples: int,
    timer: int,
    elapsed: int,
) -> bytes:
    data = bytearray(32)
    data[0:4] = b"SRKI"
    data[4] = stage
    data[5] = 1
    _put_be16(data, 6, buttons)
    _put_be32(data, 8, callbacks)
    _put_be32(data, 12, samples)
    _put_be32(data, 16, timer)
    _put_be32(data, 20, elapsed)
    _put_be32(data, 24, 20_000)
    _put_be32(data, 28, 50)
    return bytes(data)


class SarooRuntimeResidentInputProofIntegrationTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, *, marker: bool = True) -> Path:
        source = root / "SAROO-SRK-CAPTURE"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
        (firm / "main.c").write_text(MAIN_C, encoding="utf-8", newline="\n")
        (firm / "game_load.c").write_text(GAME_LOAD, encoding="utf-8", newline="\n")
        (firm / "srk_capture_helper.c").write_text("capture\n", encoding="utf-8")
        (firm / "srk_capture_helper.h").write_text("capture\n", encoding="utf-8")
        if marker:
            (source / "SRK_CAPTURE_MENU.txt").write_text(
                "validated capture-menu tree\n", encoding="utf-8"
            )
        return source

    @staticmethod
    def _helpers(root: Path) -> Path:
        helpers = root / "helpers"
        helpers.mkdir()
        names = (
            "srk_runtime_input.c",
            "srk_runtime_input.h",
            "srk_runtime_resident_input_proof.c",
            "srk_runtime_resident_input_proof.h",
            "srk_runtime_resident_input_trampoline.S",
        )
        for name in names:
            (helpers / name).write_text(f"/* {name} */\n", encoding="utf-8")
        return helpers

    def test_generates_separate_r9_tree_without_modifying_capture_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            before_main = (source / "Firm_Saturn" / "main.c").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_resident_input_proof_tree(
                source, root / "out", helper_root=helpers
            )

            self.assertEqual((source / "Firm_Saturn" / "main.c").read_bytes(), before_main)
            self.assertEqual((source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game)
            self.assertTrue(result.runtime_input_source_path.is_file())
            self.assertTrue(result.proof_source_path.is_file())
            self.assertTrue(result.trampoline_source_path.is_file())
            makefile = result.makefile_path.read_text(encoding="utf-8")
            self.assertEqual(makefile.count("obj/srk_runtime_input.o"), 1)
            self.assertEqual(makefile.count("obj/srk_runtime_resident_input_proof.o"), 1)
            self.assertEqual(makefile.count("obj/srk_runtime_resident_input_trampoline.o"), 1)

    def test_arm_menu_and_post_1st_read_install_are_wired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_resident_input_proof_tree(
                self._source(root), root / "out", helper_root=self._helpers(root)
            )
            main = result.main_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")

            self.assertIn("SRK Arm Runtime Input", main)
            self.assertIn("srk_runtime_resident_input_proof_arm()", main)
            self.assertIn('#include "srk_runtime_resident_input_proof.h"', game)
            self.assertIn("srk_runtime_resident_input_proof_install()", game)
            self.assertLess(
                game.index("patch_game((char*)0x06002020);"),
                game.index("srk_runtime_resident_input_proof_install()"),
            )

    def test_real_helper_rate_limits_bios_snapshot_without_direct_smpc_or_vdp(self):
        helper_dir = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
        )
        text = (helper_dir / "srk_runtime_resident_input_proof.c").read_text(encoding="utf-8")
        header = (helper_dir / "srk_runtime_resident_input_proof.h").read_text(encoding="utf-8")

        self.assertIn("0x06020232u", text)
        self.assertIn("SRK_RUNTIME_RESIDENT_INPUT_SAMPLE_US    20000u", header)
        self.assertIn("SRK_RUNTIME_RESIDENT_INPUT_HOLD_SAMPLES 50u", header)
        self.assertIn("srk_runtime_input_sample", text)
        self.assertIn("SS_TIMER", text)
        self.assertIn("SRK_RUNTIME_INPUT_PROOF.BIN", text)
        self.assertNotIn("COMREG", text)
        self.assertNotIn("IREG", text)
        self.assertNotIn("TVMD", text)
        self.assertNotIn("VDP", text)

    def test_real_trampoline_preserves_r7_live_registers_and_calls_r9_tick(self):
        helper_dir = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
        )
        text = (helper_dir / "srk_runtime_resident_input_trampoline.S").read_text(
            encoding="utf-8"
        )

        for token in (
            "sts.l\tpr,@-r15",
            "mov.l\tr0,@-r15",
            "mov.l\tr6,@-r15",
            "mov.l\tr7,@-r15",
            "sts.l\tmach,@-r15",
            "sts.l\tmacl,@-r15",
            "stc.l\tgbr,@-r15",
            "_srk_runtime_resident_input_proof_tick",
            "0x0600091a",
        ):
            self.assertIn(token, text)

    def test_refuses_existing_nested_and_missing_capture_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            existing = root / "existing"
            existing.mkdir()

            with self.assertRaisesRegex(
                SarooRuntimeResidentInputProofIntegrationError, "already exists"
            ):
                prepare_runtime_resident_input_proof_tree(source, existing, helper_root=helpers)
            with self.assertRaisesRegex(
                SarooRuntimeResidentInputProofIntegrationError, "outside"
            ):
                prepare_runtime_resident_input_proof_tree(
                    source, source / "nested", helper_root=helpers
                )

            no_marker = self._source(root / "a", marker=False)
            with self.assertRaisesRegex(
                SarooRuntimeResidentInputProofIntegrationError, "marker"
            ):
                prepare_runtime_resident_input_proof_tree(
                    no_marker, root / "out-a", helper_root=helpers
                )

    def test_inspector_reports_activated_three_stage_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            card = Path(temp_dir) / "CARD"
            saroo = card / "SAROO"
            saroo.mkdir(parents=True)
            payload = (
                _slot(1, 0, 0, 0, 1_000_000, 0)
                + _slot(2, 0, 0, 0, 1_250_000, 250_000)
                + _slot(3, 0x0088, 8_000, 1_500, 31_250_000, 30_250_000)
            )
            (saroo / "SRK_RUNTIME_INPUT_PROOF.BIN").write_bytes(payload)

            report = inspect_runtime_resident_input_proof(card)
            self.assertTrue(report.activated)
            self.assertEqual(len(report.slots), 3)
            self.assertEqual(report.slots[2].buttons, 0x0088)
            self.assertEqual(report.slots[2].sample_period_us, 20_000)
            self.assertEqual(report.slots[2].hold_samples, 50)
            self.assertEqual(inspect_main([str(card)]), 0)

    def test_prepare_command_and_malformed_proof_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "cli-out"
            self.assertEqual(prepare_main([str(source), str(output)]), 0)
            self.assertTrue((output / "SRK_RUNTIME_RESIDENT_INPUT_PROOF.txt").is_file())

            card = root / "CARD"
            saroo = card / "SAROO"
            saroo.mkdir(parents=True)
            (saroo / "SRK_RUNTIME_INPUT_PROOF.BIN").write_bytes(b"bad")
            with self.assertRaisesRegex(
                SarooRuntimeResidentInputProofError, "unexpected size"
            ):
                inspect_runtime_resident_input_proof(card)


if __name__ == "__main__":
    unittest.main()
