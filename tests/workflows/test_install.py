"""This file tests that the installation of the package works as expected"""
import os
import shutil
import sys
import unittest
from pathlib import Path
import subprocess
import re

import labpilot
from labpilot._tools import checks


class TestInstall(unittest.TestCase):
    def setUp(self) -> None:
        # Prepare a directory for the tests
        self.project_dir = Path("tests/.install_test")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        return super().setUp()

    def tearDown(self) -> None:
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir)
        return super().tearDown()

    def test_install(self):
        venv_name = ".env"

        # Make the virtual environment
        result = subprocess.run(
            ["python", "-m", "venv", venv_name],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Get the path of the python version in the virtual environment
        venv = Path(venv_name) / "bin"

        # Install the package
        result = subprocess.run(
            [
                venv / "pip",
                "install",
                os.getcwd(),
            ],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        # Check that the installation happened
        result = subprocess.run(
            [
                venv / "pip",
                "-q",
                "show",
                "labpilot",
            ],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Initilize the project
        result = subprocess.run(
            [venv / "labpilot", "init", "-d", "Test installation project"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        # self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Check that the installation is correct
        result = subprocess.run(
            [venv / "python", "main.py", "check", "-c", "config.ini"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Check that the tests are running
        result = subprocess.run(
            [venv / "python", "main.py", "test"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        self.assertIn("NO TESTS RAN", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_version(self):
        # Get the version from pip show
        result = subprocess.run(
            ["pip", "show", "labpilot"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )
        values = result.stdout

        # Now, extract the version number
        rstl = re.search("Version: (.*)", values)
        if rstl is not None:
            version_number = rstl.group(1)
        else:
            version_number = None

        self.assertEqual(labpilot.get_version(), version_number)
