"""Project-level contracts: version alignment, release script guards, docs."""
import os
import re
import subprocess
import unittest

from app import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ProjectContract(unittest.TestCase):
    def test_version_file_matches_package_version(self):
        with open(os.path.join(ROOT, "VERSION"), "r", encoding="utf-8") as fh:
            file_version = fh.read().strip()
        self.assertEqual(file_version, __version__)
        self.assertRegex(file_version, r"^[0-9]+\.[0-9]+\.[0-9]+$")

    def test_release_script_refuses_malformed_version_without_side_effects(self):
        releases_dir = os.path.join(ROOT, "releases")
        state_path = os.path.join(releases_dir, "state")
        history_path = os.path.join(releases_dir, "history.log")
        existed_before = os.path.isdir(releases_dir)

        def snapshot(path):
            if not os.path.isfile(path):
                return None
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()

        state_before = snapshot(state_path)
        history_before = snapshot(history_path)

        proc = subprocess.run(
            ["bash", os.path.join(ROOT, "scripts", "release.sh"), "1.0/evil"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertNotEqual(proc.returncode, 0)
        if existed_before:
            # A legit earlier release may have created releases/; prove this
            # bad input left every artifact byte-for-byte untouched.
            self.assertEqual(snapshot(state_path), state_before,
                             "release state must be untouched on bad input")
            self.assertEqual(snapshot(history_path), history_before,
                             "release history must be untouched on bad input")
        else:
            self.assertFalse(os.path.exists(releases_dir),
                             "no release dir created on bad input")

    def test_core_scripts_exist_and_are_executable(self):
        for name in ("backup.sh", "restore.sh", "release.sh", "rollback.sh", "healthcheck.py"):
            path = os.path.join(ROOT, "scripts", name)
            self.assertTrue(os.path.isfile(path), "missing script: %s" % name)

    def test_docs_have_no_em_or_en_dashes(self):
        for rel in (
            "README.md",
            os.path.join("docs", "implementation-vs-planned.md"),
            os.path.join("docs", "decision-case-study.md"),
            os.path.join("docs", "support-handoff.md"),
            os.path.join("docs", "ai-training-guide.md"),
            os.path.join("docs", "cloud-reference-paths.md"),
        ):
            path = os.path.join(ROOT, rel)
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            for bad in ("\u2014", "\u2013", "\u201c", "\u201d", "\u2019"):
                self.assertNotIn(bad, text, "forbidden dash or quote char in %s" % rel)
