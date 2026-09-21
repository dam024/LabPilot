from importlib.metadata import version
import subprocess

from labtools.utils import concurrently


def update():
    # Install the dependencies
    print("Updating the dependencies...")
    result = subprocess.run(
        [
            "pip",
            "install",
            "git+https://github.com/dam024/LabTools.git",
        ],
        capture_output=True,
        text=True,
    )
    if result.stderr != "":
        print(result.stderr)

    # Force installing the latest version
    print("Updating labtools...")
    result = subprocess.run(
        [
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            "git+https://github.com/dam024/LabTools.git",
        ],
        capture_output=True,
        text=True,
    )
    if result.stderr != "":
        print(result.stderr)

    print("Update complete!")


def get_version() -> str:
    """Returns the current version of the `labtools` module"""
    return version("labtools")
