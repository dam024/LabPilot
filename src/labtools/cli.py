"""Command line interface for project management"""
import argparse
import os
from pathlib import Path
import shutil

# Code to place in the main.py file
CODE_MAIN_PY = """
#!/usr/bin/env python
import os


def main():
    \"\"\"Run administrative tasks.\"\"\"
    os.environ.setdefault("LABTOOLS_PROJECT_DESCRIPTION", "!!DESC!!")
    try:
        import labtools
    except ImportError as exc:
        raise ImportError(
            "Couldn't import LabTools. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    labtools.main()


if __name__ == "__main__":
    main()

"""


def project_init(path: str | Path = "", desc: str | None = None):
    """Initialize a project in the current working directory"""

    def create_file(path: Path, content: str):
        with open(path, "w+") as f:
            f.write(content)

    # Ask for a description if not given
    if desc is None:
        desc = input("Please, enter a description for your project:")

    # Works with Path objects
    if not isinstance(path, Path):
        path = Path(path)

    # Create the main file
    main_path = path / "main.py"
    data = CODE_MAIN_PY.replace("!!DESC!!", desc)
    create_file(main_path, data)

    # Create the config file
    config_file = path / "config.ini"
    config_source = "config.ini"
    shutil.copyfile(config_source, config_file)


def main():
    parser = argparse.ArgumentParser(
        description="LabTools Administration tools. This command line tool interface allows you to manage your project"
    )

    subparsers = parser.add_subparsers(dest="command", help="Specific commands: ")

    # Init parser
    init_parser = subparsers.add_parser(
        "init", help="Initialize a project in the current working directory"
    )

    # Parse the arguments
    args = parser.parse_args()

    # Execute
    if args.command == "init":
        project_init()
    else:
        print(f"Error: Unknown command `{args.command}`")
        exit()
