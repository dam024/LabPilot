from pathlib import Path
from typing import Dict, List, Type
from colorama import Fore, Style, just_fix_windows_console

from labpilot.DataReceiver import LiveDataReader
import labpilot._config
import labpilot._tools.dynamic_imports as di
import labpilot.analysis as ana
import labpilot.measurement_procedure as mp

just_fix_windows_console()


def checks(config_p: str, verbose: bool):
    """This method checks that the project is correctly configured and returns the errors"""

    # Check that the config exists
    config_path = Path(config_p)
    if not config_path.exists():
        print(f"Error: The configuration at `{config_p}` does not exist")

    # Load the config
    config = labpilot._config.GeneralConfig()
    config.read(config_path)

    # Imports all the views
    views: List[ana.View] = di.get_all_views(
        module_location=config.get("GENERAL", "extra_code"),
        cls_type=ana.View,
        excluded_modules=["labpilot.DataReceiver"],
        exclude_ignored=False,
    )

    # Checks: all views have a unique name
    names: Dict[str, int] = {}

    view_duplicated_name = False
    for v in views:
        if v.name not in names:
            names[v.name] = 1
        else:
            names[v.name] += 1
            view_duplicated_name = True

    # Get all the readers - There is a check for duplicated names, so don't get the readers if the views have duplicated names...
    files_readers: Dict[str, int] = {}
    if not view_duplicated_name:
        readers = ana.View.get_all_readers_dependencies(views)
        # Check the duplication of reader names and directories
        for reader in readers:
            if reader.name not in names:
                names[reader.name] = 1
            else:
                names[reader.name] += 1

            if reader.dirname not in files_readers:
                files_readers[reader.dirname] = 1
            else:
                files_readers[reader.dirname] += 1
    else:
        readers = []

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
                f"\t{Fore.YELLOW}{v.__class__.__module__}.{v.__class__.__name__}\t(ignore: {v.ignore})\t{name}{Fore.RESET}",
            )

        if not view_duplicated_name:
            _check_print_readers(
                verbose=verbose,
                view=v,
                readers=readers,
                names=names,
                files=files_readers,
            )

    # Measurment procedures
    if verbose:
        print()
        print("Measurement Procedures:")
    for v in views:
        if not isinstance(v, mp.MeasurementProcedure):
            continue

        if names[v.name] > 1:
            name = str(Fore.RED) + v.name + str(Fore.RESET)
        else:
            name = v.name

        if verbose or names[v.name] > 1:
            print(
                f"\t{Fore.YELLOW}{v.__class__.__module__}.{v.__class__.__name__}\t(ignore: {v.ignore})\t{name}{Fore.RESET}",
            )

        if not view_duplicated_name:
            _check_print_readers(
                verbose=verbose,
                view=v,
                readers=readers,
                names=names,
                files=files_readers,
            )


def _check_print_readers(
    verbose: bool,
    view: ana.View,
    readers: List[Type[LiveDataReader]],
    names: Dict[str, int],
    files: Dict[str, int],
):
    # Readers
    if verbose:
        print(Fore.BLUE, "\tReaders:", Fore.RESET)

    for reader in readers:
        if names[reader.name] > 1:
            name = str(Fore.RED) + reader.name + str(Fore.RESET)
        else:
            name = reader.name

        if verbose or names[reader.name] > 1:
            print(f"\t\t{reader.__module__}.{reader.__name__}\t{name}")

    # Analysis
    if verbose:
        print(Fore.BLUE, "\tAnalysis:", Fore.RESET)

    analysis = view.get_analysis()
    for anal in analysis:
        if verbose:
            print(f"\t\t{anal.__class__.__module__}.{anal.__class__.__name__}")

    # Plots
    if verbose:
        print(Fore.BLUE, "\tPlots:", Fore.RESET)

    plots = [plot for a in analysis for plot in a.graphs]

    for plot in plots:
        # if names[reader.name] > 1:
        #    name = str(Fore.RED) + reader.name + str(Fore.RESET)
        # else:
        # We don't check if plots have duplicated names, too lazy for that...
        name = plot.name

        if verbose:
            print(f"\t\t{name}\t(show: {plot.show})")

    if verbose:
        print()
