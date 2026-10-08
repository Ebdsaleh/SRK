"""Synthetic tests for SRK's persistent resident-runtime SAROO proof."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_proof import (
    SarooRuntimeResidentProofError,
    inspect_runtime_resident_proof,
)
from rikai_kotoba.hardware.saturn.saroo.runtime_resident_proof_integration import (
    SarooRuntimeResidentProofIntegrationError,
    prepare_runtime_resident_proof_tree,
)
from rikai_kotoba.tools.saroo_runtime_resident_proof_inspect import main as inspect_main
from rikai_kotoba.tools.saroo_runtime_resident_proof_prepare import main as prepare_main


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

RESIDENT_H = '''#ifndef SRK_RUNTIME_RESIDENT_PROOF_H
#define SRK_RUNTIME_RESIDENT_PROOF_H
#define SRK_RUNTIME_RESIDENT_PROOF_OK 0
int srk_runtime_resident_proof_arm(void);
int srk_runtime_resident_proof_install(void);
void srk_runtime_resident_proof_vector_entry(void);
#endif
'''

RESIDENT_C = '''#include "main.h"
#include "srk_runtime_resident_proof.h"
#define SRK_RUNTIME_RESIDENT_PROOF_CALLBACKS 600u
int srk_runtime_resident_proof_arm(void) { return 0; }
int srk_runtime_resident_proof_install(void) { return 0; }
void srk_runtime_resident_proof_tick(void) { }
'''

RESIDENT_S = '''\t.text
\t.global _srk_runtime_resident_proof_vector_entry
_srk_runtime_resident_proof_vector_entry:
\tmov.l\tr6,@-r15
\tmov.l\t.Ltick,r1
\tjsr\t@r1
\tnop
\tmov.l\t@r15+,r6
\trts
\tnop
.Ltick:
\t.long\t_srk_runtime_resident_proof_tick
'''


def _put_be32(buf: bytearray, offset: int, value: int) -> None:
    buf[offset : offset + 4] = int(value).to_bytes(4, "big")


def _slot(stage: int, count: int, timer: int, elapsed: int) -> bytes:
    data = bytearray(32)
    data[0:4] = b"SRKP"
    data[4] = stage
    data[5] = 1
    _put_be32(data, 8, count)
    _put_be32(data, 12, timer)
    _put_be32(data, 16, elapsed)
    _put_be32(data, 20, 0x0600090C)
    _put_be32(data, 24, 0x0600091A)
    _put_be32(data, 28, 600)
    return bytes(data)


class SarooRuntimeResidentProofIntegrationTests(unittest.TestCase):
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
        (helpers / "srk_runtime_resident_proof.h").write_text(
            RESIDENT_H, encoding="utf-8"
        )
        (helpers / "srk_runtime_resident_proof.c").write_text(
            RESIDENT_C, encoding="utf-8"
        )
        (helpers / "srk_runtime_resident_trampoline.S").write_text(
            RESIDENT_S, encoding="utf-8"
        )
        return helpers

    def test_generates_separate_resident_proof_tree_without_modifying_capture_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            before_main = (source / "Firm_Saturn" / "main.c").read_bytes()
            before_game = (source / "Firm_Saturn" / "game_load.c").read_bytes()

            result = prepare_runtime_resident_proof_tree(
                source, root / "out", helper_root=helpers
            )

            self.assertEqual((source / "Firm_Saturn" / "main.c").read_bytes(), before_main)
            self.assertEqual((source / "Firm_Saturn" / "game_load.c").read_bytes(), before_game)
            self.assertTrue(result.helper_source_path.is_file())
            self.assertTrue(result.helper_header_path.is_file())
            self.assertTrue(result.trampoline_source_path.is_file())
            self.assertTrue(result.marker_path.is_file())
            makefile = result.makefile_path.read_text(encoding="utf-8")
            self.assertEqual(makefile.count("obj/srk_runtime_resident_proof.o"), 1)
            self.assertEqual(makefile.count("obj/srk_runtime_resident_trampoline.o"), 1)

    def test_arm_menu_and_post_1st_read_install_are_wired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = prepare_runtime_resident_proof_tree(
                self._source(root), root / "out", helper_root=self._helpers(root)
            )
            main = result.main_path.read_text(encoding="utf-8")
            game = result.game_load_path.read_text(encoding="utf-8")

            self.assertIn("SRK Arm Resident Proof", main)
            self.assertIn("srk_runtime_resident_proof_arm()", main)
            self.assertIn('#include "srk_runtime_resident_proof.h"', game)
            self.assertIn("srk_runtime_resident_proof_install()", game)
            self.assertLess(
                game.index("patch_game((char*)0x06002020);"),
                game.index("srk_runtime_resident_proof_install()"),
            )

    def test_real_helper_uses_verified_vector_context_safe_assembly_and_persistent_slot(self):
        helper_dir = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
        )
        helper = helper_dir / "srk_runtime_resident_proof.c"
        header = helper_dir / "srk_runtime_resident_proof.h"
        trampoline = helper_dir / "srk_runtime_resident_trampoline.S"
        text = helper.read_text(encoding="utf-8")
        header_text = header.read_text(encoding="utf-8")
        trampoline_text = trampoline.read_text(encoding="utf-8")

        self.assertIn('#include "srk_runtime_resident_proof.h"', text)
        self.assertIn("SRK_RUNTIME_RESIDENT_PROOF_CALLBACKS 600u", header_text)
        self.assertIn("SRK_RUNTIME_RESIDENT_PROOF_FILE_SIZE   96", text)
        self.assertIn("0x0600090cu", text)
        self.assertIn("0x0600091au", text)
        self.assertIn("0x6433, 0x4329, 0x430e, 0x644f, 0x224b, 0x2122, 0x2522", text)
        self.assertIn("*(volatile u32*)0x0600090c = 0xd401442b;", text)
        self.assertIn("*(volatile u16*)0x06000910 = 0x0009;", text)
        self.assertIn("srk_runtime_resident_restore_vector();", text)
        self.assertIn("SRK_RUNTIME_RESIDENT_PROOF_SLOT_SIZE * 2", text)
        self.assertNotIn("void srk_runtime_resident_proof_vector_entry(void)\n{", text)

        self.assertIn(".global _srk_runtime_resident_proof_vector_entry", trampoline_text)
        self.assertIn("sts.l\tpr,@-r15", trampoline_text)
        self.assertIn("mov.l\tr0,@-r15", trampoline_text)
        self.assertIn("mov.l\tr6,@-r15", trampoline_text)
        self.assertIn("mov.l\tr7,@-r15", trampoline_text)
        self.assertIn("sts.l\tmach,@-r15", trampoline_text)
        self.assertIn("sts.l\tmacl,@-r15", trampoline_text)
        self.assertIn("stc.l\tgbr,@-r15", trampoline_text)
        self.assertIn("or\t#0xf0,r0", trampoline_text)
        self.assertIn("_srk_runtime_resident_proof_tick", trampoline_text)
        self.assertIn("ldc\tr2,sr", trampoline_text)
        self.assertIn(".long\t0x0600091a", trampoline_text)
        self.assertLess(
            trampoline_text.index("mov.l\tr6,@-r15"),
            trampoline_text.index("mov\tr3,r4"),
        )

        self.assertNotIn("PAD_LT", text)
        self.assertNotIn("PAD_RT", text)
        self.assertNotIn("TVMD", text)
        self.assertNotIn("game_break_pc", text)

    def test_refuses_existing_nested_and_missing_capture_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            helpers = self._helpers(root)
            existing = root / "existing"
            existing.mkdir()

            with self.assertRaisesRegex(SarooRuntimeResidentProofIntegrationError, "already exists"):
                prepare_runtime_resident_proof_tree(source, existing, helper_root=helpers)
            with self.assertRaisesRegex(SarooRuntimeResidentProofIntegrationError, "outside"):
                prepare_runtime_resident_proof_tree(source, source / "nested", helper_root=helpers)

            no_marker = self._source(root / "a", marker=False)
            with self.assertRaisesRegex(SarooRuntimeResidentProofIntegrationError, "marker"):
                prepare_runtime_resident_proof_tree(
                    no_marker, root / "out-a", helper_root=helpers
                )
            self.assertFalse((root / "out-a").exists())

    def test_inspector_reports_proven_three_stage_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            saroo = card / "SAROO"
            saroo.mkdir(parents=True)
            payload = (
                _slot(1, 0, 1_000_000, 0)
                + _slot(2, 0, 1_250_000, 250_000)
                + _slot(3, 600, 8_250_000, 7_250_000)
            )
            (saroo / "SRK_RUNTIME_PROOF.BIN").write_bytes(payload)

            report = inspect_runtime_resident_proof(card)
            self.assertTrue(report.proven)
            self.assertEqual(len(report.slots), 3)
            self.assertEqual(report.slots[2].count, 600)
            self.assertEqual(report.slots[2].elapsed_ticks, 7_250_000)
            self.assertEqual(inspect_main([str(card)]), 0)

    def test_prepare_command_and_malformed_proof_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            real_helpers = (
                Path(__file__).resolve().parents[1]
                / "integrations"
                / "saroo"
                / "Firm_Saturn"
            )
            self.assertTrue((real_helpers / "srk_runtime_resident_proof.c").is_file())
            self.assertTrue((real_helpers / "srk_runtime_resident_proof.h").is_file())
            self.assertTrue((real_helpers / "srk_runtime_resident_trampoline.S").is_file())

            output = root / "cli-out"
            self.assertEqual(prepare_main([str(source), str(output)]), 0)
            self.assertTrue((output / "SRK_RUNTIME_RESIDENT_PROOF.txt").is_file())
            self.assertTrue(
                (output / "Firm_Saturn" / "srk_runtime_resident_trampoline.S").is_file()
            )

            card = root / "CARD"
            saroo = card / "SAROO"
            saroo.mkdir(parents=True)
            (saroo / "SRK_RUNTIME_PROOF.BIN").write_bytes(b"bad")
            with self.assertRaisesRegex(SarooRuntimeResidentProofError, "unexpected size"):
                inspect_runtime_resident_proof(card)


if __name__ == "__main__":
    unittest.main()
