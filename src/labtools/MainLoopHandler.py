from __future__ import annotations
from abc import ABC, abstractmethod
from threading import Event, Thread
import time
from typing import Dict, List, Type
from pathlib import Path
import numpy as np
import threading
import os

from labtools.data_management.local_storage import LocalStorage
import labtools.DataReceiver as dr
import labtools.analysis as ana
import labtools.measurement_procedure as mp
from labtools import logger
from labtools import config, globalState
import labtools._tools.dynamic_imports as tools


class AppHandler(ABC):
    ## Indicates if the threads must be started automatically
    auto_start_threads: bool = False

    def __init__(self) -> None:
        super().__init__()

    def start(self):
        """Start the main loop for the program"""

        # Get all views. By default, takes abstract classes to cause an error in case of something not correctly defined. Excludes the module where all the base classes are defined.

        self.views = tools.get_all_views(
            module_location=config.get("GENERAL", "extra_code"),
            cls_type=ana.View,
            excluded_modules=["labtools.DataReceiver"],
            exclude_ignored=True,
        )
        # self.views = list(filter(lambda reader: (not reader.ignore), self.views))
        # Recover active view
        localStorage = LocalStorage.main()
        if localStorage.has_value(self, "active_view"):
            view_name: str = localStorage.get(self, "active_view")
            view = list(filter(lambda view: (view.name == view_name), self.views))
            if len(view) > 0:
                self.active_view = view[0]
            else:
                self.active_view = self.views[0]
        else:
            self.active_view = self.views[0]

        # Add the readers
        self.view_setup()

        if self.auto_start_threads:
            self.start_threads()

        # Launch the main loop
        self.launch_main_thread()

    def view_setup(self):
        """Set up the views so that the readers are handled globally"""

        # Get the readers dependencies. Additionnally, check that all readers have a unique name
        readers_types = ana.View.get_all_readers_dependencies(self.views)

        # Instantiate
        self.readers = [reader() for reader in readers_types]

        # Assigne readers
        for view in self.views:
            view.set_readers(self.readers)

    @abstractmethod
    def start_threads(self):
        """Start the background threads"""
        pass

    @abstractmethod
    def launch_main_thread(self):
        """Execute the code that will be running on the main thread"""


class MainLoop(AppHandler):
    ## Indicates if animations needs to be started using the standard matplotlib procedure
    control_plots_animation: bool = True

    ## Indicates if the threads must be started automatically
    auto_start_threads: bool = True

    def __init__(self):
        self.threads: List[Thread] = []
        self.events: List[Event] = []
        self.global_thread: threading.Thread | None = None
        self.global_thread_stop_event = threading.Event()

    def select_active_view(self, view: ana.View, adapt_threads: bool = True):
        """Select the active view corresponding to the given index"""
        self.active_view = view

        self.reload_readers_data()

        if adapt_threads:
            self.regularize_threads()

    def reload_readers_data(self):
        """Loads the data from the active view.

        Note: The data for unused readers are not cleared! So if a reader already has data, they won't be loaded!
        """

        if config.simulation:
            self.active_view.load_plot_data()
            self.active_view.refresh_plots()

    def clear_readers_data(self):
        """Clears the data for all readers"""
        if config.simulation:
            for reader in self.readers:
                reader.clear()

    def regularize_threads(self):
        """Ensure that all running threads are strickly belonging to the current active view. Starts threads from the active view that are not yet running"""
        readers_to_stop: List[dr.LiveDataReader] = []
        readers_to_start: List[dr.LiveDataReader] = []
        for reader in self.readers:
            if self.active_view.has_reader(reader) and (
                (
                    isinstance(
                        reader, dr.StreamDataReader
                    )  # In simulation, only starts the stream readers
                    and globalState.stream_values  # If we don't stream in simulation mode, we don't start the StreamDataReaders
                    and reader.can_stream_data
                )
                or not config.simulation
            ):
                if not reader.is_running:
                    readers_to_start.append(reader)

            else:
                if config.simulation and not reader.can_stream_data:
                    logger.warning(
                        "Some readers cannot be streamed. Therefore, you should disable the stream feature"
                    )
                if reader.is_running:
                    readers_to_stop.append(reader)

        for reader in readers_to_stop:
            reader.pause()

        for reader in readers_to_start:
            reader.resume()

    def start_threads(self):
        """Start the background threads"""
        # Start all the readers
        self.regularize_threads()

        if self.global_thread is None:
            self.global_thread = threading.Thread(target=self.global_background_thread)
            self.global_thread.start()
        # for reader in self.readers:
        #    reader.resume()

    def stop_threads(self):
        """Stops the background threads running"""
        # Stop the threads
        for reader in self.readers:
            reader.pause()

    def launch_main_thread(self):
        """Execute the code that will be continuously running on the main thread"""
        try:
            self.main_thread_loop()
        finally:
            logger.info("Shuting down...")

            # Quite the measurement procedures
            if mp.MeasurementProcedure.procedure_running:
                running = mp.MeasurementProcedure.running_procedure

                if (
                    running is not None
                    and mp.MeasurementProcedure.running_threadpool is not None
                ):
                    running.stop()
                    mp.MeasurementProcedure.running_threadpool.shutdown(wait=True)
                else:
                    raise RuntimeError(
                        "Running procedure is `None`. This should never happen!"
                    )

            self.stop_threads()

            # Join the threads
            for reader in self.readers:
                if hasattr(reader, "collector") and reader.collector is not None:
                    reader.collector.join()

            logger.info("Shutdown complete")

            # Shutdown global background thread
            if self.global_thread is not None:
                logger.info("Completing data saving...")

                self.global_thread_stop_event.set()
                self.global_thread.join()

                logger.info("Data saving completed!")

    @abstractmethod
    def main_thread_loop(self):
        """Code that will execute on the main thread.

        This method is responsible for defining what will happen after everything has been initialized.

        Note:
            When this methods returns, the program will stop. Therefore, it is the responsibility of this method to run the infinite loop
        """

    def global_background_thread(self):
        """This method handles a thread that will manage long run analysis for the different readers.

        For example, saving data takes a long time, so it will be handled here
        """

        while not self.global_thread_stop_event.is_set():
            is_alive = False
            is_queue_empty = True
            for reader in self.readers:
                if reader.is_running:
                    is_alive = True
                ###### Data saving
                data = None
                filename = None
                # Get the data to save
                # if reader.save_all_arrays:
                #    if not reader.save_queue.empty():
                #        data, filename = reader.save_queue.get_nowait()
                #
                # else:
                #    while not reader.save_queue.empty():
                #        data, filename = reader.save_queue.get_nowait()
                should_save = False
                while not reader.save_queue.empty() and not should_save:
                    data, filename, should_save = reader.save_queue.get_nowait()

                is_queue_empty = is_queue_empty and reader.save_queue.empty()

                # Save the values
                if data is not None and filename is not None:
                    path = Path(filename)
                    #
                    path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        np.save(path, data)
                    except PermissionError:
                        logger.error(f"Permission denied for {path}")

            if not is_alive:
                break
            if is_queue_empty:
                time.sleep(0.5)

        self.global_thread = None


class PlotsGUIMainLoop(MainLoop):
    def main_thread_loop(self):
        # plt.show(block=False)
        # plt.show()
        raise NotImplementedError(
            "Needs to show the plots. This must be handled by the plot backend"
        )
        i = 0
        while True:
            # Read parameters change
            print("Main thread...")
            time.sleep(1)
            # Apply parameters change
            if i >= 5:
                break
            i += 1

            # Update user interface

            # Restart


class PlotGeneration(AppHandler):
    auto_start_threads = False
    control_plots_animation = False

    def start_threads(self):
        """We do not start the threads..."""
        pass

    def launch_main_thread(self):
        # Setup the parametrables to guarantee all the bindings were initialized
        for view in self.views:
            for param in view.get_parametrables():
                param._setup(window=None)

        experiment_folder = os.path.join(
            config.get("GENERAL", "data_analysis_folder"), config.experiment_name
        )

        for measurements_folder in os.listdir(experiment_folder):
            if not os.path.isdir(os.path.join(experiment_folder, measurements_folder)):
                continue
            # measurements_folder = "29-04-2026_LIGENTEC_OFDR_CHIP_ALIGNED"
            output_folder = os.path.join(
                config.output_dir_plots, config.experiment_name, measurements_folder
            )
            os.makedirs(output_folder, exist_ok=True)

            path = os.path.join(
                experiment_folder,
                measurements_folder,
            )
            measurement_infos = MeasurementInfos()
            measurement_infos.load(path)

            # For each reader, load all the data
            for reader in self.readers:
                reader.load_data(path)

            # Generates all the plots for all analysis
            done_analysis: Dict[str, bool] = {}
            for view in self.views:
                for analysis in view.analysis:
                    if analysis.__class__.__name__ in done_analysis:
                        continue
                    else:
                        done_analysis[analysis.__class__.__name__] = True
                    for plot in analysis.graphs:
                        plot.show = True
                        plot.init_plots()

                    analysis.refresh_plots()
                    extra_plots = analysis.plot_generation(measurement_infos)

                    for plot in analysis.graphs + extra_plots:
                        plot.save(output_folder)

        return super().launch_main_thread()
