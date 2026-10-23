from typing import Any, Dict, List, Type
import json
import os

import logging

logger = logging.getLogger(__name__)

from labpilot.data_management.type_extension_support import serialize, deserialize
from labpilot.data_management.database_manager import DB
from labpilot.data_management.datamodel import Recording

from labpilot.GUI.binding import BindingSupport


class ForbidenKeyError(Exception):
    pass


class JSONImportError(Exception):
    pass


class Infos:
    __authorized_keys__: List[str] | None = None

    def __init__(self) -> None:
        self._values = {}

    def load(self, path: str):
        # try:
        with open(os.path.join(path, "info.json"), "r") as f:
            values = json.load(f, object_hook=deserialize)

            if values["__type__"] != self.__class__.__name__:
                raise JSONImportError(
                    f"The file you tried to load does not contain data of the expected type. Obtained type: {values['__type__']}. Expected type: {self.__class__.__name__}"
                )
            self._values = values["values"]
        # except Exception as e:
        # logger.error(f"Error when opening file {path}")
        # logger.exception(e)

    def to_dict(self) -> dict:
        return {
            "__type__": self.__class__.__name__,
            "version": "1.0.0",
            "values": self._values,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=serialize)

    def save(self, path_folder: str):
        """Saves all the informations in the given directory"""
        path = os.path.join(path_folder, "info.json")

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, default=serialize)

    def __getitem__(self, index: str) -> Any:
        return self._values[index]

    def __setitem__(self, index: str, value: Any):
        if self.__authorized_keys__ and index not in self.__authorized_keys__:
            raise ForbidenKeyError(
                f"You are not authorized to set the key `{index}` in object of class `{self.__class__.__name__}`. Authorized keys are: {self.__authorized_keys__}"
            )
        self._values[index] = value

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, self.__class__):
            return False

        return self._values == value._values


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


class RecordingInfos(ParametrizedInfos):
    """This class is a data, session-independant representation of Recording

    You can use this object outside of the database, with the only downside that the measurement won't be accessible directly...
    """

    __authorized_keys__ = [
        "id",
        "description",
        "readers",
        "start",
        "end",
        "measurement_id",
        "parameters",
    ]

    def as_recording(self, session) -> Recording | None:
        """Convert the current object into a `Recording`. If an instance alread exists in the database, this instance will be queried and updated. The mapping is performed if the 'id' property is set"""
        assert self.__authorized_keys__ is not None

        if "id" in self._values:
            recording = session.query(Recording, self["id"])
        else:
            recording = Recording()

        # Set the keys accordingly
        for key in self.__authorized_keys__:
            if key in self._values:
                setattr(recording, key, self[key])

        return recording
