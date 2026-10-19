from __future__ import annotations
import argparse
import labpilot._config as config
import unittest
import os
from labpilot import logger, utils


### Optimization:
#       - The new function in utils to resample could be used to smooth the measurements of the oscilloscope, reducing the number of points to display live (and improving refresh time)
#       - Plots are plotted at runtime with less data
#       - Remove the recording button and treat it as a special procedure that is automatically included in every application. It saves code and decrease the cases... Then, I can create a way to subclass it if the user wants to change the plots. For this, I need to have a global parameter that indicates if the data must be saved live or not. Since each reader is independant, there is not way to time from another process the collection and recording of the data. Therefore, each reader must be responsible to save its lively collected data. It can be in the same way it works with the recording.
#       - Improve the simulation feature. All StreamDataReader must have two modes: read all files and stream. LiveDataReader must only show the measured value. `Analysis` must load all their plots at ones and be compatible with `MeasurementProcedure`.
#           Note: LiveDataReaders can also be streamed. I think they are saved anyway for each time step. I need to make sure time is saved... Then, during non-stream, I need to select an aggragation function to apply to the data (mean, last, first, a given frame, etc.). This will allow me to improve the data visualization
#           This modification requires modifying `View.load_plot_data`. Follow the instructions from there. Note that instructions may be contradictory. Think again about what would be the best
#           I also need to add a progress bar to load the files... Because now, it can take ages and there won't be any indication of the progres... I see well a global progress bar to which I can schedule some events and they will show the progress... (This is tracktable in this case, because I can know how many files I've read and how many in total I have)
#       - Complete the `AxisItemCustom` class in pyqt_backend.py. This class is intended to be used to improve the ticks and the labels to be more readable and less capricious...
#       - Optimize loading time. It is due to module loading.
#       - Remove circular imports, it's really annoying... I'm sure there is a way to avoid them...

### Post processing:
#       - Procedures can be used as what will create the plots at the end. Plots shown are constructed live, then, during post processing, an extra method is called to make the plot nice and everything
#       - The user must give the name of the experiment, or the sample to which he wants to compute the plots. Otherwise, it will generate the plots for ALL experiments and ALL samples!

### Tools:
#       - Can add a way to create quickly a project...
#       - Add code snipets or something to quickly create some code

### Interface:
#       - Allow to create plots in a grid (i.e. have 2 columns) in views
#       - Add tools to manage the experiments properties and the samples

# Global parameters:
#   - refresh_delay must be able to be handled globally and locally. If I define it in a View, it will be global. Otherwise, it will be local.
#       - List of classes not clean: PowerMeter, TemperatureHumidityReader, OscilloscopeAveragedMeasurements, LaserController
#   - When I subclass a Reader, its Bindings must be shared globally with the superclasses. The reason for this is that it represents the same instrument, but with a different behavior


def main():
    # ==== ARGUMENT PARSER  ========
    desc = os.environ.get("LABPILOT_PROJECT_DESCRIPTION")
    parser = argparse.ArgumentParser(description=desc)

    subparsers = parser.add_subparsers(dest="command", help="Specific commands: ")

    # Add arguments

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display all the informations in the console.",
    )

    parser.add_argument(
        "--no_logs", action="store_true", help="Prevent to write the logs in a file"
    )

    # Run parser
    run_parser = subparsers.add_parser(
        "run", help="Run the main program as live data reading"
    )

    run_parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Location of the configuration file to use.",
    )

    # Plot parser
    plot_parser = subparsers.add_parser(
        "plots", help="Generate all the plots from the last generated data"
    )

    plot_parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Location of the configuration file to use.",
    )

    # Test parser
    test_parser = subparsers.add_parser("test", help="Execute unit tests")

    test_parser.add_argument(
        "-d",
        "--data",
        action="store_true",
        help="Prevent the temporary data to be deleted at the end of the test pipline",
    )

    test_parser.add_argument(
        "test_module",
        nargs="?",
        help="""Optional test string to allow working on a single test function or test class
        Example: 
            If I want to execute only the `test_load` method of the `DatabaseTest` class located at ./tests/database_test.py, the value of this variable will be `tests.database_tests.DatabaseTest.test_load`
        """,
    )

    # Start parser
    start_parser = subparsers.add_parser(
        "start", help="Start the main GUI of the application"
    )

    start_parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Location of the configuration file to use.",
    )

    start_parser.add_argument(
        "-d",
        "--disk_data",
        action="store_true",
        help="Use data on disk to simulate the instruments being connected",
    )

    # Check parser
    check_parser = subparsers.add_parser(
        "check",
        help="Check that the configuration will correctly launch the application",
    )

    check_parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Location of the configuration file to check",
    )

    check_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Indicates if all the informations should be printed even if the check successful",
    )

    # Parse the arguments
    args = parser.parse_args()

    def run_tests_in_directory(directory, module_name=None):
        """
        Discover and run all unit tests within a specified directory.
        Optionally run tests from a specific Python module or subdirectory.

        Args:
            directory (str): The path to the directory containing test files.
            module_name (str, optional): The name of the Python module containing tests to run. If None, runs all tests in the directory.
                                       Use either a full module path (e.g., "tests.unittests") or a directory path.
        """

        # Create a test loader
        loader = unittest.TestLoader()

        if module_name:
            # If module_name contains dots, treat it as a package/module path
            # Split into base and subpackage: tests.unittests -> tests + /unittests
            if "." in module_name:
                base_module, subpackage = module_name.split(".", 1)
                full_path = os.path.join(directory, subpackage)
                if os.path.isdir(full_path):
                    # It's a package directory - discover tests within it
                    suite = loader.discover(full_path, pattern="*.py")
                else:
                    # Module path doesn't exist as directory - try loadTestsFromName
                    suite = loader.loadTestsFromName(module_name)
            else:
                # Directory path - discover tests in that directory
                suite = loader.discover(directory, pattern="*.py")
        else:
            # Discover all Python files that start with 'test' in the given directory
            suite = loader.discover(directory, pattern="*.py")

        # Create a test runner and run the test suite
        runner = unittest.TextTestRunner()
        runner.run(suite)

    #####################  PROGRAM START   ##################

    ## Preparing the configuration
    if args.command == "start":
        config.generalConfig.use_gui = True
        if args.disk_data:
            config.generalConfig.simulation = True

    ## Importing project modules
    from labpilot.MainLoopHandler import PlotGeneration, PlotsGUIMainLoop
    from labpilot.GUI.mainGUI import MainGUILoop
    from labpilot._tools.checks import checks

    # Test command
    if args.command == "test":
        config.generalConfig.read("tests/config.ini")
        logger.config_logger(config.generalConfig)
        utils._executor = utils.TestThreadExecutor()

        # Remove all the handlers to avoid printing in the console...
        logger.clear_handlers()
        # Run unit tests
        run_tests_in_directory(os.path.join(os.getcwd(), "tests"), args.test_module)
    # Other commands
    elif args.command == "check":
        # Run the checks
        checks(args.config, args.verbose)
    else:
        config.generalConfig.read(args.config)
        logger.config_logger(config.generalConfig)

        if args.command == "run":
            # Start the main loop of the program for live data acquisition
            loop = PlotsGUIMainLoop()

        elif args.command == "plots":
            loop = PlotGeneration()

        elif args.command == "start":
            # Repeated code...
            config.generalConfig.use_gui = True
            if args.disk_data:
                config.generalConfig.simulation = True
            loop = MainGUILoop()

        else:
            print(f"Error: Unknown command `{args.command}`")
            exit()

        loop.start()


if __name__ == "__main__":
    main()
