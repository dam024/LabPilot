from pathlib import Path
from typing import Dict, List
from colorama import Fore, Style, just_fix_windows_console

import labtools._config
import labtools._tools.dynamic_imports as di
import labtools.analysis as ana
import labtools.measurement_procedure as mp

just_fix_windows_console()


def checks(config_p: str, verbose: bool):
    """This method checks that the project is correctly configured and returns the errors"""

    # Check that the config exists
    config_path = Path(config_p)
    if not config_path.exists():
        print(f"Error: The configuration at `{config_p}` does not exist")

    # Load the config
    config = labtools._config.GeneralConfig()
    config.read(config_path)

    # Imports all the views
    views: List[ana.View] = di.get_all_views(
        module_location=config.get("GENERAL", "extra_code"),
        cls_type=ana.View,
        excluded_modules=["labtools.DataReceiver"],
        exclude_ignored=False,
    )

    # Checks: all views have a unique name
    names: Dict[str, int] = {}
    for v in views:
        if v.name not in names:
            names[v.name] = 1
        else:
            names[v.name] += 1

    # Views only
    if verbose:
        print("Views:")
    for v in views:
        if isinstance(v, mp.MeasurementProcedure):
            continue

        if names[v.name] > 1:
            name = Fore.RED + v.name + Fore.RESET
        else:
            name = v.name

        if verbose or names[v.name] > 1:
            print(
                "\t",
                f"{v.__class__.__module__}.{v.__class__.__name__}\t(ignore: {v.ignore})\t{name}",
            )

    # Measurment procedures
    if verbose:
        print()
        print("Measurement Procedures:")
    for v in views:
        if not isinstance(v, mp.MeasurementProcedure):
            continue

        if names[v.name] > 1:
            name = Fore.RED + v.name + Fore.RESET
        else:
            name = v.name

        if verbose or names[v.name] > 1:
            print(
                "\t",
                f"{v.__class__.__module__}.{v.__class__.__name__}\t(ignore: {v.ignore})\t{name}",
            )
