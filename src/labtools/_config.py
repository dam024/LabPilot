import configparser
import logging
import os


class GeneralConfig(configparser.ConfigParser):
    simulation: bool = False
    use_gui: bool = False
    _output_dir_data: str | None = None

    @property
    def output_dir(self):
        """Output directory containing all the outputs"""

        return self.get("GENERAL", "output_directory")

    @property
    def output_dir_data(self):
        """Path to the directory where to store the data"""
        if self._output_dir_data is not None:
            return self._output_dir_data
        return os.path.join(self.output_dir, "data")

    @output_dir_data.setter
    def output_dir_data(self, value: str):
        if not self.simulation:
            raise RuntimeError(
                "You cannot assign `output_dir_data` while taking measurement!"
            )

        self._output_dir_data = value

    @property
    def output_dir_plots(self) -> str:
        """Path to the directory where the plots will be stored"""
        return self.get("GENERAL", "plots_output_dir")

    @property
    def database_url(self) -> str:
        """Returns the URL that will allow connexion to the database"""
        return self.get("DATABASE", "database_url")

    @property
    def experiment_name(self):
        return self.get("GENERAL", "experiment_folder")

    @property
    def log_level(self):
        return logging.DEBUG

    @property
    def show_errors(self) -> bool:
        if not self.use_gui:
            return False
        return self.get("GENERAL", "error_alert") == "true"


class GlobalState:
    _recording: bool = False
    _recording_subfolder: str = "recording"
    reading_recording_subfolder: str | None = None
    stream_values: bool = True

    @property
    def recording(self) -> bool:
        """Indicates if the application is being recording"""
        return self._recording

    @recording.setter
    def recording(self, value: bool):
        self._recording = value

    @property
    def recording_subfolder(self) -> str:
        """Folder where to save the collected data"""
        return self._recording_subfolder


generalConfig = GeneralConfig()
globalState = GlobalState()
