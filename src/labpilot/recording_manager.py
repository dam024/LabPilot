from __future__ import annotations
import datetime
import os
import traceback
from typing import TYPE_CHECKING, List, Self

from PySide6.QtWidgets import QInputDialog

import logging

from labpilot.data_management.background_thread_save import BackgroundSaveThread

logger = logging.getLogger(__name__)
from labpilot import config
from labpilot.data_management.database_manager import DB
from labpilot.data_management.datamodel import Recording
from labpilot.data_management.measurement_information import RecordingInfos
import labpilot._tools.utility_classes as uc

if TYPE_CHECKING:
    from labpilot.GUI.mainGUI import MainWindow


class RMRecordingInProgress(Exception):
    """Exception that indicates that a recording is already in progress"""

    pass


class RMNoRecording(Exception):
    """Exception happening when a recording is supposed to be running"""

    pass


class RecordingManager(uc.GlobalUniqueInstance):
    _recording_subfolder: str = "recording"
    reading_recording_subfolder: str | None = None
    """When the application is in simulation mode, indicates the path to the current recording folder. This is not used when the application is NOT in simulation mode"""
    stream_values: bool = True

    def __init__(self) -> None:
        self.recorder = None
        self.record_reader_data = True
        self.measurement_id: int | None = None
        super().__init__()

    @property
    def is_recording(self) -> bool:
        """Indicates if the application is being recording"""
        return self.recorder is not None

    @property
    def recording_subfolder(self) -> str:
        """Name of the folder where to save the collected data"""
        return self._recording_subfolder

    @property
    def recording_path(self) -> str:
        """Returns the path to the folder where the current recordings are"""
        path = os.path.join(config.output_dir_data, self.recording_subfolder)
        return path

    def start_recording(
        self, recorder: object, record_reader_data: bool = True
    ) -> RecordingInfos:
        if self.is_recording:
            raise RMRecordingInProgress(
                f"{recorder.__class__.__name__} is already recording data. You cannot start a new recording!!!"
            )
        self.record_reader_data = record_reader_data
        self.recorder = recorder
        self._recording = RecordingInfos()
        self._recording["start"] = datetime.datetime.now()

        return self._recording

    def end_recording(
        self,
        calling: object,
        save_data: bool = True,
        mainWindow: MainWindow | None = None,
        foldername: str | None = None,
        description: str | None = None,
    ) -> RecordingInfos | None:
        if (
            not self.is_recording
            or self.recorder is not calling
            or self._recording is None
        ):
            raise RMNoRecording(
                f"{calling.__class__.__name__} requested to stop a recording it hasn't started!"
            )
        recording = self._recording
        self._recording = None
        self.recorder = None

        # Stop if we're not saving the data
        if not save_data:
            return None

        # Save the plots if the mainWindow is given
        if mainWindow:
            plots_location = self.recording_path
            for canvas in mainWindow.view_plots[mainWindow.active_view.name]:
                canvas.graph.figure.save(
                    os.path.join(
                        plots_location,
                        canvas.graph.filename,
                    )
                )

            # Find the readers
            r: List[str] = []
            for reader in mainWindow.mainGuiLoop.readers:
                if reader.is_running:
                    r.append(reader.name)

            recording["readers"] = f"[{", ".join(r)}]"
        else:
            recording["readers"] = "[]"

        # Fill the missing values
        recording["end"] = datetime.datetime.now()

        if not foldername:
            foldername, ok = QInputDialog.getText(
                None, "Recording", "Name of the folder"
            )
            logger.dev_warning(
                "I need to add something here to validate the folder name!!! While it is empty or if it already exists..."
            )
            if not ok or not foldername:
                return

        if description:
            recording["description"] = description
        else:
            description, ok = QInputDialog.getText(None, "Recording", "Description:")

            # If the user did not select 'ok', ignore
            if not ok:
                return None

            recording["description"] = description

        recording.dump_parameters()

        ## TODO: Set the measurement_id!!!
        recording["measurement_id"] = self.measurement_id

        # Save the recording informations
        # with DB() as session:
        #    rec = recording.as_recording(session)
        #    session.add(rec)

        # Save the data in the json file
        try:
            os.makedirs(self.recording_path, exist_ok=True)
            # Save the recording information
            recording.save(self.recording_path)

            # Rename the folder so that it doesn't get overriden
            # os.rename(
            BackgroundSaveThread.main().addMoveAction(
                self.recording_path,
                os.path.join(
                    config.output_dir_data,
                    foldername,
                ),
            )
        except Exception as e:
            logger.error(e)
            traceback.print_exception(e)

        return recording
