import shutil
import unittest
from pathlib import Path

# import tests.utils as utils
from labtools import config
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

        # Initialize a project
        project_init(desc=project_test_desc, path=self.project_dir)

        # Check that main.py exists
        main_path = self.project_dir / "main.py"
        self.assertTrue(main_path.exists())

        # Check that the config file exists
        config_path = self.project_dir / "config.ini"
        self.assertTrue(config_path.exists())
