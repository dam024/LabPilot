import shutil
import sys
import unittest
from pathlib import Path
import subprocess

# import tests.utils as utils
import labpilot
from labpilot.cli import project_init


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        # Prepare a directory for the tests
        self.project_dir = Path("tests/.project")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        return super().setUp()

    def tearDown(self) -> None:
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir)
        return super().tearDown()

    def test_init(self):
        """Test that the initialization of a project works as expected"""

        project_test_desc = "Description of a test project"
        # Takes into account the normal installation (files in 'labpilot_data/') and the editable installation (files in 'src/')
        source_destination = (
            "src"
            if not (Path(labpilot.__file__).parent / "labpilot_data").exists()
            else None
        )

        # Initialize a project
        ret = project_init(
            desc=project_test_desc,
            path=self.project_dir,
            source_files=source_destination,
        )
        self.assertTrue(ret)

        # Check that main.py exists
        main_path = self.project_dir / "main.py"
        self.assertTrue(main_path.exists())

        # Check that the config file exists
        config_path = self.project_dir / "config.ini"
        self.assertTrue(config_path.exists())

        # Check that the files exists
        files = ["analysis.py", "views.py", "readers.py"]
        for f in files:
            path = self.project_dir / "src" / Path(f)
            self.assertTrue(path.exists(), f"`{path}` does not exists")

        # Check that the installation is correct
        result = subprocess.run(
            [sys.executable, "main.py", "check", "-c", "config.ini"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Check that the tests are running
        result = subprocess.run(
            [sys.executable, "main.py", "test"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        self.assertIn("NO TESTS RAN", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_init_twice(self):
        """Test that if I try to initialize the project twice, it will throw an error"""

        project_test_desc = "Description of a test project"
        # Takes into account the normal installation (files in 'labpilot_data/') and the editable installation (files in 'src/')
        source_destination = (
            "src"
            if not (Path(labpilot.__file__).parent / "labpilot_data").exists()
            else None
        )

        # Initialize a project
        ret = project_init(
            desc=project_test_desc,
            path=self.project_dir,
            source_files=source_destination,
        )
        self.assertTrue(ret)

        # Initilize a 2nd time
        ret = project_init(
            desc=project_test_desc,
            path=self.project_dir,
            source_files=source_destination,
        )
        self.assertFalse(ret)

        # Force the installation
        ret = project_init(
            desc=project_test_desc,
            path=self.project_dir,
            source_files=source_destination,
            force=True,
        )
        self.assertTrue(ret)
