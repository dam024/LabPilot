from __future__ import annotations

import datetime
import os
from typing import List
import traceback

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget, QLabel

import logging

logger = logging.getLogger(__name__)

from labpilot import config, globalState

from labpilot.GUI.binding import CBinding, SavedBinding, SimulationSavedBinding, Status
from labpilot.GUI.parameters import GUIParametrable, GUIParameter
import labpilot.GUI.objects as objects
from labpilot.analysis import View
from labpilot.recording_manager import RecordingManager
import labpilot.measurement_procedure as mp


class InvalidCall(Exception):
    pass


class ApplicationParameters(GUIParametrable):
    title = "Application Parameters"

    def __init__(
        self,
        associated_view: View,
        update_interval: CBinding[int],
        active_view: CBinding[str],
        is_experiment_running: CBinding[bool],
        experiment_button_text: CBinding[str],
    ) -> None:
        """
        This is a special class.
        NEVER add additional constructor parameters.

        Args:
            associated_view (View): View to which these parameters are associated to
            update_interval (CBinding[int]): Binding that controls the plot update time interval
            active_view (CBinding[str]): Binding that controls which view is active
            is_experiment_running (CBinding[bool]): Binding that controls if an experiment is running
            experiment_button_text (CBinding[str]): Binding that controls the text of the experiment toggling button
        """
        self.associated_view = associated_view
        self.update_interval = update_interval
        self.active_view = active_view
        self.is_experiment_running = is_experiment_running
        self.exp_button_text = experiment_button_text

        super().__init__()

    @Status
    def is_recording(self) -> bool:
        return False

    @Status
    def recording_button_text(self) -> str:
        return "Record"

    def get_parameters(self, frame: QWidget, view: View | None) -> List[GUIParameter]:
        if self.window is None:
            raise InvalidCall("get_parameters() called while window is None.")

        self.active_view_combo = objects.Combobox(
            frame,
            "View:",
            list(self.window.views_dic.keys()),
            self.active_view,
        )

        refresh_interval = objects.NumericalValueInput(
            frame,
            from_=100,
            to=2000,
            value=self.update_interval,
            text="Plots refresh rate [ms]",
        )

        self.button_toggle_experiment = objects.ButtonWidget(
            frame, text=self.exp_button_text, action=self.toggle_experiment
        )

        parameters = [
            GUIParameter(self.active_view_combo),
            GUIParameter(refresh_interval),
            GUIParameter(self.button_toggle_experiment),
        ]

        if not config.simulation and not isinstance(
            self.associated_view, mp.MeasurementProcedure
        ):
            self.button_recording = objects.ButtonWidget(
                frame,
                text=self.recording_button_text,
                action=self.toggle_recording,
            )

            parameters.append(GUIParameter(self.button_recording))

        return parameters

    def toggle_experiment(self) -> None:
        logger.debug("Toggle experiment...")
        if self.window is None:
            raise InvalidCall("toggle_experiment() called while window is None.")

        if self.is_experiment_running.get():
            # Check if a measurement procedure is running. Stop it in case
            if (
                mp.MeasurementProcedure.procedure_running
                and mp.MeasurementProcedure.running_procedure is not None
            ):
                reply = QMessageBox.question(
                    None,
                    "Measurement Running",
                    "A measurement is running. Do you want to continue? It will cancel it.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.No:
                    return

                # Stop the measurement if the user says so
                mp.MeasurementProcedure.running_procedure.stop()

            # Stop the recording
            self.window.stop_updates()
        else:
            if (
                config.simulation
                and RecordingManager.main().reading_recording_subfolder is None
            ):
                self.window.ask_recording_folder()

            # Clear all the plots
            self.window.clear_all_plots()

            self.window.start_updates()

    def toggle_recording(self) -> None:
        if self.window is None:
            raise InvalidCall("toggle_recording() called while window is None.")

        if not self.is_experiment_running.get():
            logger.error("Please start the experiment before recording.")
            return

        if self.is_recording.get():
            self.is_recording = False
            self.recording_button_text = "Record"

            # Stop the recording
            RecordingManager.main().end_recording(
                self, save_data=True, mainWindow=self.window
            )

        else:
            # Start the recording
            RecordingManager.main().start_recording(self)

            self.is_recording = True
            self.recording_button_text = "Stop Recording..."


class StatusInterface(GUIParametrable):
    title = "Status"

    @Status
    # @SimulationSavedBinding -> to save the value from session to session
    def recording(self) -> str | None:
        return None

    @recording.onchange
    def __recording(self, value: str | None):
        RecordingManager.main().reading_recording_subfolder = value

    @Status
    def measurement(self) -> str | None:
        return None

    @Status
    def experiment(self) -> str | None:
        return None

    @SavedBinding
    def stream_values(self) -> bool:
        """This variable indicates if the data from `StreamDataReaders` must be streamed during simulation mode.

        If data are not streamed, the full plot is shown"""
        return True

    @stream_values.onchange
    def __stream_values(self, value: bool):
        globalState.stream_values = value

        if (
            config.simulation
            and RecordingManager.main().reading_recording_subfolder is None
        ):
            return

        if self.window is None:
            raise RuntimeError(
                "The `window` has not been created. This is an unexpected error! This should not happen..."
            )

        if self.window.is_experiment_running.get():
            self.window.stop_updates()

        self.window.mainGuiLoop.clear_readers_data()
        if not value:
            self.window.mainGuiLoop.reload_readers_data()

    def get_parameters(self, frame: QWidget, view: View | None) -> List[GUIParameter]:
        parameters: List[GUIParameter] = []

        exp_param = objects.Label(
            frame,
            label="Experiment:",
            text=self.experiment
            # textvariable=self.experiment.qt_variable(),
        )

        parameters.append(GUIParameter(exp_param))

        meas_param = objects.Label(frame, label="Measurement:", text=self.measurement)

        parameters.append(GUIParameter(meas_param))

        if config.simulation:
            record_param = objects.Label(frame, label="Recording:", text=self.recording)

            parameters.append(GUIParameter(record_param))

            stream_value = objects.Switch(
                frame, label="Stream Data:", current_value=self.stream_values
            )
            parameters.append(GUIParameter(stream_value))

        if not config.simulation and self.window is not None:
            for reader in self.window.mainGuiLoop.readers:
                widget = reader.get_status_interface(frame)
                parameters.append(GUIParameter(objects.Widget(widget)))

        return parameters
