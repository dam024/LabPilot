from typing import Any, List, Type
import json
import os
from labtools import logger
from labtools.GUI.binding import BindingSupport


class Infos:
    def __init__(self) -> None:
        self._values = {}

    def load(self, path: str):
        try:
            with open(os.path.join(path, "info.json"), "r") as f:
                self._values = json.load(f)
        except Exception as e:
            logger.error(f"Error when opening file {path}")
            logger.exception(e)

    def save(self, path_folder: str):
        """Saves all the informations in the given directory"""
        try:
            with open(os.path.join(path_folder, "info.json"), "w") as f:
                json.dump(self._values, f)
        except Exception as e:
            logger.error(f"Error when saving experiment informations: {path_folder}")
            logger.exception(e)

    def __getitem__(self, index: str) -> Any:
        return self._values[index]

    def __setitem__(self, index: str, value: Any):
        self._values[index] = value


class ParametrizedInfos(Infos):
    def __init__(self) -> None:
        super().__init__()
        self._values["parameters"] = {}

    def _build_key(self, owner: object | Type, key: str) -> str:
        if isinstance(owner, Type):
            return f"{owner.__name__}.{key}"
        else:
            return f"{owner.__class__.__name__}.{key}"

    def set_parameter(self, owner: object | Type, key: str, value: Any):
        full_key = self._build_key(owner, key)
        self._values["parameters"][full_key] = value

    def get_parameter(self, owner: object | Type, key: str) -> object:
        full_key = self._build_key(owner, key)
        return self._values["parameters"][full_key]

    def has_param(self, owner: object | Type, key: str) -> bool:
        full_key = self._build_key(owner, key)
        return full_key in self._values["parameters"]

    def apply_parameters(self):
        """Apply the currently saved parameters to the application"""
        for param in BindingSupport.parametrables.values():
            param.restore_values(self)

    def dump_parameters(self):
        """Read all parameters that must be auto_saved and load them in the current object"""

        for param in BindingSupport.parametrables.values():
            param.save_values(self)

    def load(self, path: str, apply_parameters: bool = False):
        """Loads the parameters and apply them if required

        Args:
            path (str): Path to the recording folder to load parameters from
            apply_parameters (bool, optional): Indicates if we need to apply the parameters to all parametrables
        """
        super().load(path)

        if apply_parameters:
            self.apply_parameters()


# The final system must make sure that all data are given to before saving!
class MeasurementInfos(Infos):
    def __init__(self):
        super().__init__()


class Experiment:
    # Description
    description: str
    # Name
    name: str
    # Folder name
    folder_name: str

    """This class represents an experiment. It contains informations about the different sets of measurements. The goal of this entity is to indicate what is the goal of the given set of measurements
    """


class Sample:
    """Represents a single sample"""

    name: str
    comment: str


class SetupVersion:
    """Version of the setup"""

    # Name of version
    version: str
    # Setup mode
    mode: str
    # Description
    description: str


class Measurement(ParametrizedInfos):
    """A Measurement is a set of recordings on a given sample. These recordings were made on the same shot."""

    # authors
    authors: List[str]
    # Date
    date_start: str
    date_end: str
    # Setup version
    setupVersion: SetupVersion
    # Experiment
    experiment: Experiment
    # Sample
    sample: Sample


class RecordingInfos(ParametrizedInfos):
    # Recording Procedure. This is the name of the class
    name: str  # -> unique value!!!!
    # Description of the recording
    description: str
    # List of readers that were recording data
    readers: List[str]
    # Time
    time_start: str
    time_end: str

    measurement: Measurement
