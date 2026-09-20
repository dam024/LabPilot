import shutil
import unittest
from pathlib import Path
import subprocess

# import tests.utils as utils
from labtools import config
import labtools
from labtools.cli import project_init


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        # Prepare a directory for the tests
        self.project_dir = Path("tests/.project")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        return super().setUp()

    def tearDown(self) -> None:
        # if self.project_dir.exists():
        #    shutil.rmtree(self.project_dir)
        return super().tearDown()

    def test_init(self):
        """Test that the initialization of a project works as expected"""

        project_test_desc = "Description of a test project"
        # Takes into account the normal installation (files in 'labtools_data/') and the editable installation (files in 'src/')
        source_destination = (
            "src"
            if not (Path(labtools.__file__).parent / "labtools_data").exists()
            else None
        )

        # Initialize a project
        project_init(
            desc=project_test_desc,
            path=self.project_dir,
            source_files=source_destination,
        )

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
            ["python", "main.py", "check", "-c", "config.ini"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

        # Check that the tests are running
        result = subprocess.run(
            ["python", "main.py", "test"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        self.assertIn("NO TESTS RAN", result.stderr)
        self.assertEqual(result.stdout, "")
