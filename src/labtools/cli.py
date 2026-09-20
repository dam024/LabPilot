"""Command line interface for project management"""
import argparse
import os
from pathlib import Path
import shutil
from importlib.resources import files, as_file

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


def project_init(
    path: str | Path = "",
    desc: str | None = None,
    source_files: str | None = None,
    force: bool = False,
) -> bool:
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

    if source_files is None:
        # Data folder of the package - where are stored all the pre-written files
        resource = files("labtools")

        with as_file(resource) as p:
            data_folder = Path(p).parent / "labtools_data"
    else:
        data_folder = Path(source_files)

    main_path = path / "main.py"

    if not force and main_path.exists():
        return False

    # Create the main file
    main_path = path / "main.py"
    data = CODE_MAIN_PY.replace("!!DESC!!", desc)
    create_file(main_path, data)

    # Create the config file
    config_file = path / "config.ini"
    content = data_folder / "config.ini"
    create_file(config_file, content.read_text())

    code_folder = path / "src"
    code_folder.mkdir(exist_ok=True, parents=True)
    # Copy all example python files in an 'src/' folder
    for f in os.listdir(data_folder):
        p = data_folder / Path(f)
        if p.suffix == ".py":
            shutil.copyfile(p, code_folder / f)

    # Create the tests directory and set an empty __init__.py
    test_dir = path / "tests"
    test_dir.mkdir(exist_ok=True)
    create_file(test_dir / "__init__.py", "")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="LabTools Administration tools. This command line tool interface allows you to manage your project"
    )

    subparsers = parser.add_subparsers(dest="command", help="Specific commands: ")

    # Init parser
    init_parser = subparsers.add_parser(
        "init", help="Initialize a project in the current working directory"
    )
    init_parser.add_argument(
        "-d",
        "--description",
        required=False,
        type=str,
        help="Description of the project",
    )

    init_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force the initialization of the project. IMPORTANT: Use this option with care, because it will overrite files already presents and can lead to data loss",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Execute
    if args.command == "init":
        if args.description != "":
            ret = project_init(desc=args.description, force=args.force)
        else:
            ret = project_init(force=args.force)

        if ret:
            print("Your project has been initialized!")
        else:
            print(
                "The project has already been initialized. Consider forcing a new initialization if this is really what you want."
            )
    else:
        print(f"Error: Unknown command `{args.command}`")
        exit()
