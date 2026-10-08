from __future__ import annotations
import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QInputDialog
from sqlalchemy.engine.default import datetime

from labtools import logger
from labtools.data_management.database_manager import DB
from labtools.data_management.datamodel import Recording

if TYPE_CHECKING:
    from labtools.GUI.mainGUI import MainWindow


class RMInstantiationException(Exception):
    """Error to indicate that only a single instance of the recording manager can be instantiated"""

    pass


class RMRecordingInProgress(Exception):
    """Exception that indicates that a recording is already in progress"""

    pass


class RMNoRecording(Exception):
    """Exception happening when a recording is supposed to be running"""

    pass


class RecordingManager:
    _recording_subfolder: str = "recording"
    reading_recording_subfolder: str | None = None
    stream_values: bool = True
    _main: "RecordingManager | None" = None

    def __init__(self) -> None:
        if RecordingManager._main is not None:
            raise RMInstantiationException(
                "You can only instantiate ONCE the recording manager! Please, use `RecordingManager.main()` to access it!!!"
            )

        RecordingManager._main = self
        self.recorder = None

    @property
    def is_recording(self) -> bool:
        """Indicates if the application is being recording"""
        return self.recorder is not None

    @property
    def recording_subfolder(self) -> str:
        """Folder where to save the collected data"""
        return self._recording_subfolder

    @classmethod
    def main(cls) -> "RecordingManager":
        if RecordingManager._main is None:
            RecordingManager._main = RecordingManager()

        return RecordingManager._main

    def start_recording(self, recorder: object) -> Recording:
        if self.is_recording:
            raise RMRecordingInProgress(
                f"{recorder.__class__.__name__} is already recording data. You cannot start a new recording!!!"
            )

        self.recorder = recorder
        self._recording = Recording(start=datetime.datetime.now())

        return self._recording

    def end_recording(
        self,
        calling: object,
        save_data: bool = True,
        mainWindow: MainWindow | None = None,
        foldername: str | None = None,
        description: str | None = None,
    ) -> Recording | None:
        if not self.is_recording or self.recorder != calling or self._recording is None:
            raise RMNoRecording(
                f"{calling.__class__.__name__} requested to stop a recording it hasn't started! "
            )
        recording = self._recording
        self._recording = None
        self.recorder = None

        # Stop if we're not saving the data
        if not save_data:
            return None
        raise NotImplementedError("...")
        # Save the plots if the mainWindow is given
        if mainWindow:
            plots_location = os.path.join(
                config.output_dir_data,
                globalState.recording_subfolder,
            )
            for canvas in mainWindow.view_plots[mainWindow.active_view.name]:
                canvas.graph.figure.save(
                    os.path.join(
                        plots_location,
                        canvas.graph.filename,
                    )
                )

        # Fill the missing values
        recording.end = datetime.datetime.now()

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
            recording.description = description
        else:
            description, ok = QInputDialog.getText(None, "Recording", "Description:")

            # If the user did not select 'ok', ignore
            if not ok:
                return None

            recording.description = description

        recording.dump_parameters()
        raise NotImplementedError("Need to register the `Measurement` property")
        recording.measurement = ...

        with DB() as session:
            session.add(recording)

        # Save the data in the json file
        try:
            # Save the recording information
            recording.save(
                os.path.join(
                    config.output_dir_data,
                    globalState.recording_subfolder,
                )
            )

            # Rename the folder so that it doesn't get overriden
            os.rename(
                os.path.join(
                    config.output_dir_data,
                    globalState.recording_subfolder,
                ),
                os.path.join(
                    config.output_dir_data,
                    folder_name,
                ),
            )
        except Exception as e:
            logger.error(e)
            traceback.print_exception(e)

        return recording
