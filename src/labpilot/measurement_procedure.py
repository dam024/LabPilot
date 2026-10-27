from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
import datetime
from pathlib import Path
import re
import threading
import traceback
from typing import TYPE_CHECKING, List
from labpilot.GUI.binding import Status
import numpy as np
import os
from PySide6.QtWidgets import QWidget


import logging

logger = logging.getLogger(__name__)

from labpilot import config
import labpilot.DataReceiver as dr
import labpilot.analysis as ana
from labpilot.GUI.parameters import GUIParameter, GUIParametrable
import labpilot.GUI.objects as gui_obj
from labpilot.recording_manager import RecordingManager
from labpilot.utils import concurrently

if TYPE_CHECKING:
    import labpilot.GUI.mainGUI as mainGUI


class StopProcedureRequest(Exception):
    pass


class MeasurementProcedure(ana.DataAnalysis, ana.View):
    """This class represents a procedure that will take automatic measurements and generate a set of plots out of it

    A procedure is both responsible to collect its data from readers, analyse them and generate a set of plots
    """

    # Name of the directory where to save the data, if there is one. An empty string will save in the same directory as the rest
    dirname: str
    procedure_running: bool = False
    running_procedure: "MeasurementProcedure | None" = None
    running_threadpool: ThreadPoolExecutor | None = None
    record_all_readers: bool = True
    """If `True`, all readers will log all the data they collect. If `False`, the readers WON'T log their data at all"""

    @Status
    def foldername(self) -> str:
        """Name of the folder where to save the data at the end of a measurement procedure"""
        return self.dirname

    @Status
    def description(self) -> str:
        """Description to write in the info.json at the end of the procedure"""
        return f"Measurement procedure: {self.name}"

    def __init__(self) -> None:
        self._check_for_property("dirname", str)
        self.data_lock = threading.Lock()
        self._current_data = None
        self.execute_stop_event = threading.Event()
        super().__init__()

    @property
    def measurement_data_folder(self) -> str:
        """Returns the path to the file where the measurement is saved"""
        recording_manager = RecordingManager.main()
        if (
            config.simulation
            and recording_manager.reading_recording_subfolder is not None
        ):
            folder = os.path.join(
                config.output_dir_data,
                recording_manager.reading_recording_subfolder,
            )
        else:
            # folder = os.path.join(config.output_dir_data, self.dirname)
            folder = RecordingManager.main().recording_path
        os.makedirs(folder, exist_ok=True)

        return folder

    @property
    def measurement_data_file(self):
        path = os.path.join(self.measurement_data_folder, "measurements.npy")

        return path

    def set_readers(self, readers: List[dr.LiveDataReader]):
        # This method needs to be overriden, because it has an hybrid behavior between DataAnalysis and View. Otherwise, it will use the one from DataAnalysis, which is wrong in general...
        ana.View.set_readers(self, readers)

    def load_components(self):
        super().load_components()
        # Ensures that `self` is in `self.analysis`
        if self not in self.analysis:
            self.analysis.insert(0, self)

    def load_plot_data(self):
        super().load_plot_data()

        # Load the data saved by the measurement procedure
        measurement_file = self.measurement_data_file
        if os.path.exists(measurement_file):
            # Load the data
            data = np.load(measurement_file)

            self._current_data = data

    # @abstractmethod
    def refresh_plots(self):
        # Refresh all plots from all analysis that are NOT this current class!
        for analysis in self.analysis:
            if analysis is not self:
                analysis.refresh_plots()
        return super().refresh_plots()

    def get_analysis(self) -> List[ana.DataAnalysis]:
        l = super().get_analysis()
        l.append(self)
        return l

    def get_parameters(
        self, frame: QWidget, view: ana.View | None
    ) -> List[GUIParameter]:
        self.find_free_foldername()

        parameters = ana.DataAnalysis.get_parameters(self, frame, view)
        parameters += ana.View.get_parameters(self, frame, view)

        parameters.append(
            GUIParameter(
                widget=gui_obj.Entry(frame, label="Folder name:", text=self.foldername)
            )
        )
        parameters.append(
            GUIParameter(
                widget=gui_obj.Entry(frame, label="Description:", text=self.description)
            )
        )
        parameters.append(
            GUIParameter(
                widget=gui_obj.ButtonWidget(
                    frame,
                    text=self.title,
                    action=self.execute_procedure,
                )
            )
        )

        return parameters

    def get_parametrables_deprecated(self) -> List[GUIParametrable]:
        parametrables = super().get_parametrables()

        if self not in parametrables:
            # Add its readers and plots
            parametrables.insert(0, self)
            parametrables += self.readers
            parametrables += [
                graph
                for graph in self.graphs
                if graph.show and isinstance(graph, GUIParametrable)
            ]

        return parametrables

    def execute_procedure(self):
        """Reinitialize all the plots and execute the procedure"""
        if MeasurementProcedure.procedure_running:
            logger.error(
                f"A measurement is already in progress. You cannot run a second one at the same time!"
            )
            return

        # Makes sure the experiment is running
        if self.window is not None and not self.window.is_experiment_running.get():
            self.window.start_updates()

        # Update all the recording informations
        RecordingManager.main().start_recording(self, self.record_all_readers)
        MeasurementProcedure.procedure_running = True
        MeasurementProcedure.running_procedure = self
        self.execute_stop_event.clear()

        # Clear all the data from the dependent readers
        for reader in self.readers:
            reader.clear()

        pool = self._treat_procedure()
        MeasurementProcedure.running_threadpool = pool

    @concurrently
    def _treat_procedure(self, **kwargs):
        """Code that actually executes the procedure"""
        save_data = False
        try:
            data = self.execute()
            # Save the data
            if not self.execute_stop_event.is_set():
                self.save(data)
                save_data = True
        except StopProcedureRequest:
            pass
        except Exception as e:
            logger.error(e)
            traceback.print_exception(e)

        logger.info(f"Measurement Procedure {self.name} Completed!")

        try:
            self.find_free_foldername()
            RecordingManager.main().end_recording(
                self,
                save_data=save_data,
                mainWindow=self.window,
                foldername=self.foldername.get(),
                description=self.description.get(),
            )
            self.find_free_foldername(current_not_free=save_data)
        except Exception as e:
            logger.error(e)
            traceback.print_exception(e)

        MeasurementProcedure.procedure_running = False
        MeasurementProcedure.running_procedure = None
        MeasurementProcedure.running_threadpool = None

    def find_free_foldername(self, current_not_free: bool = False):
        """Find a free foldername if the one given is not free

        A folder name is considered as "free" if there is no folder with that name in the data folder

        Args:
            current_not_free (bool, optional): Set to `True` for the current value of `self.foldername` to be considered as not free
        """
        data_folder = Path(config.output_dir_data)
        i = 1
        name = self.foldername.get()
        current_value = data_folder / name
        while (data_folder / name).exists() or (
            current_not_free and str(current_value) == str(data_folder / name)
        ):
            # Removes the "_xx" pattern from the end of the string
            result = re.sub(r"_\d+$", "", name)

            name = result + f"_{i}"
            i += 1

        self.foldername = name

    def stop(self):
        """Stops the current procedure if it is running

        If you call this method, no data will be saved!"""
        self.execute_stop_event.set()

    def save(self, data: np.ndarray):
        """Saves the data collected during the procedure"""
        path = self.measurement_data_file
        np.save(path, data)

    def log_data(self, data: np.ndarray, progress: int | None = None):
        """Call this method when new data are collected during the procedure. You can pass the entire data set. They will then be available when the plots will be refreshed

        Args:
            data (np.ndarray): Data to log
            progress (int | None): Progress. The maximum progress is the size of `data`. If not given, data will be plotted until the end

        Raises:
            StopProcedureRequest: Description
        """
        if self.execute_stop_event.is_set():
            raise StopProcedureRequest(
                f"The procedure `{self.name}` was requested to stop!"
            )
        with self.data_lock:
            if progress is not None:
                self._current_data = data[:, : progress + 1].copy()
            else:
                self._current_data = data.copy()

    def get_procedure_data(self) -> np.ndarray | None:
        """Returns the logged data for the procedure"""
        if self._current_data is not None:
            return self._current_data.copy()
        else:
            return None

    @abstractmethod
    def execute(self) -> np.ndarray:
        """This method implements the core of the procedure.

        You must subclass this method to execute the procedure. It will then be responsible to:
                - Control the setup to make it reach a desired state
                - Wait until that state has been reached
                - Detect that the state has been reached
                - Take the desired measurements
                - Log the current data

        These results will be automatically saved and treated by other methods.

        Note:
                - The plots of the `View` will be updated normally. However, all the data will be reinitialized when starting the procedure. Therefore, data collected by all `LiveDataReader` will be reinitialized
                - This code will be run concurrently on the main thread!

        Returns:
            (np.ndarray) The full data collected by the procedure. They will be saved as is.

        Important:
            - YOU MUST CALL `self.log_data()` TO BE ABLE TO HAVE LIVE UPDATE

            ```python
            def execute(self):
                # initialization
                parameters = ...
                try:
                    for i in range(parameters):
                        # Adjust the setup parameters and wait for stabilization
                        ...

                        # Collect the data
                        data = ...

                        # log the data
                        self.log_data(data)
                except StopProcedureRequest:
                    # The measurement was stopped.
                    # Execute cleaning specific to early stopping
                    ...
                finally:
                    # Cleaning that needs to be executed in all cases
                    ...

                return data
            ```
        """
