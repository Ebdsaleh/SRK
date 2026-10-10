"""Tests for isolated standalone Saturn diagnostics project generation."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.formats.saturn.ip_bin import parse_saturn_system_id
from rikai_kotoba.formats.saturn.packaged_pcm import (
    PACKAGED_PCM_FILENAME,
    PACKAGED_PCM_SAMPLE_COUNT,
    build_deterministic_packaged_pcm,
    parse_packaged_pcm,
)
from rikai_kotoba.hardware.saturn.standalone_project import (
    SaturnStandaloneProjectError,
    prepare_saturn_standalone_project,
)
from rikai_kotoba.tools.saturn_standalone_prepare import main as prepare_main


def _field(text: str, size: int) -> bytes:
    return text.encode("ascii").ljust(size, b" ")


def _ip_bin() -> bytes:
    data = bytearray(2048)
    data[0x00:0x10] = _field("SEGA SEGASATURN", 16)
    data[0x10:0x20] = _field("LOCAL TEMPLATE", 16)
    data[0x20:0x2A] = _field("OLD-TITLE", 10)
    data[0x2A:0x30] = _field("V9.999", 6)
    data[0x30:0x38] = _field("20000101", 8)
    data[0x38:0x40] = _field("CD-1/1", 8)
    data[0x40:0x4A] = _field("JTUE", 10)
    data[0x50:0x60] = _field("J", 16)
    data[0x60:0xD0] = _field("OLD TEMPLATE TITLE", 112)
    data[0xE0:0xE4] = (0x1800).to_bytes(4, "big")
    data[0xF0:0xF4] = (0x06004000).to_bytes(4, "big")
    data[0x100:0x110] = b"LOCAL-BOOT-CODE!"
    return bytes(data)


def _touch(path: Path, data: bytes = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _fixture(root: Path):
    saturn = root / "Saturn-Dev"
    bin_dir = saturn / "SH_ELF" / "sh-elf" / "bin"
    for name in (
        "sh-elf-gcc.exe",
        "sh-elf-as.exe",
        "sh-elf-objdump.exe",
        "sh-elf-objcopy.exe",
    ):
        _touch(bin_dir / name)
    _touch(saturn / "TOOLS" / "mkisofs.exe")

    segalib = saturn / "SaturnOrbit-Inspect" / "payload" / "app" / "SBL_601" / "SEGALIB"
    _touch(segalib / "INCLUDE" / "SEGA_GFS.H", b"fixture-gfs-header\n")
    for name in ("sega_gfs.a", "SEGA_CDC.A", "sega_dma.a", "sega_csh.a", "sega_int.a"):
        _touch(segalib / "LIB_ELF" / name, ("fixture-" + name + "\n").encode("ascii"))

    template = root / "vdp1ex"
    template.mkdir()
    (template / "vga_font.h").write_text(
        "unsigned char font[2048] = {0};\n",
        encoding="utf-8",
    )

    ip_bin = root / "IP.BIN"
    ip_bin.write_bytes(_ip_bin())
    return saturn, template, ip_bin


def _snapshot(paths):
    return {str(path): path.read_bytes() for path in paths}


class SaturnStandaloneProjectTests(unittest.TestCase):
    def test_generates_isolated_project_without_mutating_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn, template, ip_bin = _fixture(root)
            output = root / "SRK-Diagnostics-R1"
            segalib = saturn / "SaturnOrbit-Inspect" / "payload" / "app" / "SBL_601" / "SEGALIB"
            private_inputs = [
                segalib / "INCLUDE" / "SEGA_GFS.H",
                segalib / "LIB_ELF" / "sega_gfs.a",
                segalib / "LIB_ELF" / "SEGA_CDC.A",
                segalib / "LIB_ELF" / "sega_dma.a",
                segalib / "LIB_ELF" / "sega_csh.a",
                segalib / "LIB_ELF" / "sega_int.a",
            ]
            watched = [template / "vga_font.h", ip_bin, *private_inputs]
            before = _snapshot(watched)

            result = prepare_saturn_standalone_project(
                saturn,
                template,
                ip_bin,
                output,
                release_date="20261009",
            )

            self.assertEqual(_snapshot(watched), before)
            self.assertEqual(result.output_root, output.resolve())
            self.assertTrue((output / "src" / "srk_saturn_host.c").is_file())
            self.assertTrue((output / "src" / "srk_saturn_audio.c").is_file())
            self.assertTrue((output / "src" / "srk_saturn_audio.h").is_file())
            self.assertTrue((output / "src" / "srk_saturn_packaged_pcm.c").is_file())
            self.assertTrue((output / "src" / "srk_saturn_packaged_pcm.h").is_file())
            self.assertTrue((output / "src" / "srk_saturn_runtime.c").is_file())
            self.assertTrue((output / "src" / "srk_diag_app.c").is_file())
            self.assertTrue((output / "src" / "srk_diag_audio.c").is_file())
            self.assertTrue((output / "src" / "srk_diag_audio.h").is_file())
            self.assertTrue((output / "src" / "srk_diag_vdp1.c").is_file())
            self.assertTrue((output / "src" / "srk_diag_vdp1.h").is_file())
            self.assertTrue((output / "src" / "srk_diag_video.c").is_file())
            self.assertTrue((output / "src" / "srk_diag_video.h").is_file())
            self.assertTrue((output / "src" / "vga_font.h").is_file())
            self.assertTrue((output / "srk_saturn.ld").is_file())
            self.assertTrue((output / "build.bat").is_file())
            self.assertTrue((output / "SRK_STANDALONE_PROJECT.json").is_file())

            payload_path = output / "cd" / PACKAGED_PCM_FILENAME
            payload = payload_path.read_bytes()
            expected_payload = build_deterministic_packaged_pcm()
            self.assertEqual(result.packaged_pcm, payload_path.resolve())
            self.assertEqual(payload, expected_payload)
            self.assertEqual(parse_packaged_pcm(payload).sample_count, PACKAGED_PCM_SAMPLE_COUNT)

            manifest = json.loads(
                (output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8")
            )
            pcm = manifest["packaged_pcm"]
            self.assertEqual(pcm["path"], f"cd/{PACKAGED_PCM_FILENAME}")
            self.assertEqual(pcm["size"], len(payload))
            self.assertEqual(pcm["sha256"], sha256(payload).hexdigest())
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            self.assertIn(f"cd/{PACKAGED_PCM_FILENAME}", inventory)
            self.assertIn("src/srk_saturn_runtime.c", inventory)
            self.assertEqual(
                inventory[f"cd/{PACKAGED_PCM_FILENAME}"]["sha256"],
                sha256(payload).hexdigest(),
            )

            gfs = manifest["stage6b_gfs"]
            self.assertFalse(gfs["copied_into_project"])
            self.assertEqual(Path(gfs["include_dir"]), (segalib / "INCLUDE").resolve())
            self.assertEqual(Path(gfs["library_dir"]), (segalib / "LIB_ELF").resolve())
            for key, source in (
                ("gfs_header", private_inputs[0]),
                ("gfs_library", private_inputs[1]),
                ("cdc_library", private_inputs[2]),
                ("dma_library", private_inputs[3]),
                ("csh_library", private_inputs[4]),
                ("int_library", private_inputs[5]),
            ):
                self.assertEqual(Path(gfs[key]["path"]), source.resolve())
                self.assertEqual(gfs[key]["size"], source.stat().st_size)
                self.assertEqual(gfs[key]["sha256"], sha256(source.read_bytes()).hexdigest())
                self.assertNotIn(source.name, inventory)
            self.assertEqual(gfs["link_contract"]["cdc_format"], "coff-sh")
            self.assertEqual(gfs["link_contract"]["post_cdc_format"], "elf32-sh")
            self.assertEqual(
                gfs["link_contract"]["dedicated_library_order"],
                ["sega_gfs.a", "SEGA_CDC.A", "sega_dma.a", "sega_csh.a", "sega_int.a", "-lgcc"],
            )

    def test_generated_ip_bin_is_title_neutral_and_preserves_boot_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn, template, ip_bin = _fixture(root)
            source = ip_bin.read_bytes()
            output = root / "out"

            prepare_saturn_standalone_project(
                saturn,
                template,
                ip_bin,
                output,
                release_date="20261009",
            )
            generated = (output / "IP.BIN").read_bytes()
            metadata = parse_saturn_system_id(generated)

            self.assertEqual(metadata["maker_id"], "SRK PROJECT")
            self.assertEqual(metadata["product_number"], "SRK-DIAG")
            self.assertEqual(metadata["game_version"], "V0.001")
            self.assertEqual(metadata["game_date"], "20261009")
            self.assertEqual(metadata["game_title"], "SRK SATURN DIAGNOSTICS")
            self.assertEqual(metadata["first_read_address"], "0x06004000")
            self.assertEqual(generated[0x100:], source[0x100:])
            self.assertEqual(ip_bin.read_bytes(), source)

    def test_build_wrapper_delegates_to_python_native_builder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn, template, ip_bin = _fixture(root)
            output = root / "out"

            prepare_saturn_standalone_project(
                saturn,
                template,
                ip_bin,
                output,
                release_date="20261009",
            )
            script = (output / "build.bat").read_text(encoding="utf-8")
            readme = (output / "README_BUILD.txt").read_text(encoding="utf-8")
            host = (output / "src" / "srk_saturn_host.c").read_text(encoding="utf-8")
            audio = (output / "src" / "srk_saturn_audio.c").read_text(encoding="utf-8")
            runtime = (output / "src" / "srk_saturn_runtime.c").read_text(encoding="utf-8")
            packaged_runtime = (output / "src" / "srk_saturn_packaged_pcm.c").read_text(encoding="utf-8")
            manifest = json.loads(
                (output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8")
            )

            self.assertIn("python -m rikai_kotoba.tools.saturn_standalone_build", script)
            self.assertIn('--project "%~dp0."', script)
            self.assertNotIn("sh-elf-gcc.exe", script)
            self.assertNotIn("sh-elf-as.exe", script)
            self.assertNotIn("mkisofs.exe", script)
            self.assertNotIn("sat -x", script)
            self.assertEqual(manifest["build_orchestration"], "python-native")
            self.assertEqual(manifest["deployable_format"], "cue-bin-mode1-2352")
            self.assertFalse(manifest["policy"]["private_sdk_dependencies_copied"])
            self.assertIn("SRKPCM.BIN", readme)
            self.assertIn("sega_dma.a -> sega_csh.a -> sega_int.a", readme)
            self.assertIn("coff-sh", readme)
            self.assertIn("SRK-Diagnostics.cue + .bin", readme)
            self.assertIn("Deployment remains a separate guarded operation", readme)
            self.assertIn("0x20100075", host)
            self.assertIn("SRK_DIAG_BUTTON_L", host)
            self.assertIn("SRK_DIAG_BUTTON_R", host)
            self.assertIn("draw_video_pattern", host)
            self.assertIn("present_vdp1_quad", host)
            self.assertIn("0x25C00000", host)
            self.assertIn("0x25D00000", host)
            self.assertIn("0x25A00000", audio)
            self.assertIn("0x25B00000", audio)
            self.assertIn("SRK_AUDIO_SMPC_SNDON", audio)
            self.assertIn("SRK_AUDIO_SMPC_SNDOFF", audio)
            self.assertIn("void *memset", runtime)
            self.assertIn("int memcmp", runtime)
            self.assertIn("int strncmp", runtime)
            self.assertIn("char *strncpy", runtime)
            self.assertIn('#include "SEGA_GFS.H"', packaged_runtime)
            self.assertIn("GFS_NameToId", packaged_runtime)
            self.assertIn("GFS_Load", packaged_runtime)

    def test_refuses_to_merge_into_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn, template, ip_bin = _fixture(root)
            output = root / "out"
            output.mkdir()

            with self.assertRaises(SaturnStandaloneProjectError):
                prepare_saturn_standalone_project(
                    saturn,
                    template,
                    ip_bin,
                    output,
                    release_date="20261009",
                )

    def test_cli_reports_prepare_only_safety_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn, template, ip_bin = _fixture(root)
            output = root / "out"
            rendered = StringIO()

            with redirect_stdout(rendered):
                status = prepare_main(
                    [
                        "--saturn-root", str(saturn),
                        "--template", str(template),
                        "--ip-bin", str(ip_bin),
                        "--output", str(output),
                        "--release-date", "20261009",
                    ]
                )

            text = rendered.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("project prepared", text)
            self.assertIn("read only and were not modified", text)
            self.assertIn("No compiler, linker, ISO builder", text)
            self.assertTrue((output / "build.bat").is_file())


if __name__ == "__main__":
    unittest.main()
