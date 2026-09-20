#!/usr/bin/env python
import os


def main():
    """Run administrative tasks."""
    os.environ.setdefault("LABTOOLS_PROJECT_NAME", "Test of the LabTools module")
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
