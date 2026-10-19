#!/usr/bin/env python
import os


def main():
    """Run administrative tasks."""
    os.environ.setdefault("LABPILOT_PROJECT_DESCRIPTION", "Test of the LabPilot module")
    try:
        import labpilot
    except ImportError as exc:
        raise ImportError(
            "Couldn't import LabTools. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    labpilot.main()


if __name__ == "__main__":
    main()
