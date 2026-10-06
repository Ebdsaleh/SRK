"""Tests for Mjolnir's shared output-conflict policy."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from rikai_kotoba.core.safe_extractor import ExtractionReport
from rikai_kotoba.tools.mjolnir import (
    _next_numbered_backup_path,
    _write_directory_with_conflict_resolution,
    _write_portable_zip,
    _write_with_conflict_resolution,
)


class _FakeExtractor:
    def extract_all(
        self,
        output_root,
        *,
        overwrite=False,
        continue_on_error=True,
    ):
        del overwrite, continue_on_error
        os.makedirs(output_root, exist_ok=True)
        with open(os.path.join(output_root, "HELLO.TXT"), "wb") as handle:
            handle.write(b"hello")
        return ExtractionReport(output_root=os.path.abspath(output_root))


def _directory_builder(payload):
    def builder(path):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "payload.txt"), "w", encoding="utf-8") as handle:
            handle.write(payload)
        return ExtractionReport(output_root=os.path.abspath(path))

    return builder


class MjolnirOutputConflictTests(unittest.TestCase):
    def test_directory_backup_uses_first_available_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc.Output")
            os.makedirs(output)
            os.makedirs(output + "(1)")
            os.makedirs(output + "(2)")

            self.assertEqual(
                _next_numbered_backup_path(output),
                output + "(3)",
            )

    def test_directory_conflict_cancel_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc")
            os.makedirs(output)
            marker = os.path.join(output, "old.txt")
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("old")

            calls = []

            def builder(path):
                calls.append(path)
                return _directory_builder("new")(path)

            result, report = _write_directory_with_conflict_resolution(
                output,
                builder,
                input_func=lambda _prompt: "1",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "cancelled")
            self.assertIsNone(report)
            self.assertEqual(calls, [])
            with open(marker, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

    def test_directory_conflict_auto_rename_preserves_old_and_writes_new(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc")
            os.makedirs(output)
            with open(os.path.join(output, "old.txt"), "w", encoding="utf-8") as handle:
                handle.write("old")
            os.makedirs(output + "(1)")

            result, report = _write_directory_with_conflict_resolution(
                output,
                _directory_builder("new"),
                input_func=lambda _prompt: "2",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "renamed_existing")
            self.assertEqual(result.backup_path, output + "(2)")
            self.assertIsNotNone(report)
            self.assertTrue(os.path.isfile(os.path.join(output, "payload.txt")))
            self.assertTrue(os.path.isfile(os.path.join(output + "(2)", "old.txt")))

    def test_directory_conflict_overwrite_replaces_instead_of_merging(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc")
            os.makedirs(output)
            with open(os.path.join(output, "old.txt"), "w", encoding="utf-8") as handle:
                handle.write("old")

            result, report = _write_directory_with_conflict_resolution(
                output,
                _directory_builder("new"),
                input_func=lambda _prompt: "3",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "overwritten")
            self.assertIsNotNone(report)
            self.assertFalse(os.path.exists(os.path.join(output, "old.txt")))
            with open(
                os.path.join(output, "payload.txt"),
                "r",
                encoding="utf-8",
            ) as handle:
                self.assertEqual(handle.read(), "new")

    def test_directory_auto_rename_rolls_back_if_final_placement_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc")
            os.makedirs(output)
            marker = os.path.join(output, "old.txt")
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("old")

            real_rename = os.rename
            call_count = [0]

            def flaky_rename(source, destination):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise OSError("simulated directory placement failure")
                return real_rename(source, destination)

            with patch(
                "rikai_kotoba.tools.mjolnir.os.rename",
                side_effect=flaky_rename,
            ):
                with self.assertRaises(OSError):
                    _write_directory_with_conflict_resolution(
                        output,
                        _directory_builder("new"),
                        input_func=lambda _prompt: "2",
                        print_func=lambda _message: None,
                    )

            with open(marker, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")
            self.assertFalse(os.path.exists(output + "(1)"))

    def test_portable_zip_uses_same_auto_rename_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "Disc-dump.zip")
            with open(output, "wb") as handle:
                handle.write(b"old archive")

            session = SimpleNamespace(extractor=_FakeExtractor())
            reports = []

            def writer(path, overwrite):
                created, report = _write_portable_zip(
                    session,
                    path,
                    overwrite=overwrite,
                )
                reports.append(report)
                return created

            result = _write_with_conflict_resolution(
                output,
                writer,
                input_func=lambda _prompt: "2",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "renamed_existing")
            self.assertEqual(result.backup_path, os.path.join(temp_dir, "Disc-dump(1).zip"))
            self.assertEqual(len(reports), 1)
            with open(result.backup_path, "rb") as handle:
                self.assertEqual(handle.read(), b"old archive")
            with zipfile.ZipFile(output, "r") as archive:
                self.assertEqual(archive.namelist(), ["HELLO.TXT"])
                self.assertEqual(archive.read("HELLO.TXT"), b"hello")


if __name__ == "__main__":
    unittest.main()
