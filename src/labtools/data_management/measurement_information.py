from typing import Any, Dict, List, Type
import json
import os
from labtools import logger
from labtools.GUI.binding import BindingSupport


class Infos_:
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


class ParametrizedInfos_(Infos_):
    parameters: Dict[str, Any]

    def __init__(self) -> None:
        super().__init__()
        # self._values["parameters"] = {}

    def _build_key(self, owner: object | Type, key: str) -> str:
        if isinstance(owner, Type):
            return f"{owner.__name__}.{key}"
        else:
            return f"{owner.__class__.__name__}.{key}"

    def set_parameter(self, owner: object | Type, key: str, value: Any):
        full_key = self._build_key(owner, key)
        # self._values["parameters"][full_key] = value
        self.parameters[full_key] = value

    def get_parameter(self, owner: object | Type, key: str) -> object:
        full_key = self._build_key(owner, key)
        # return self._values["parameters"][full_key]
        return self.parameters[full_key]

    def has_param(self, owner: object | Type, key: str) -> bool:
        full_key = self._build_key(owner, key)
        # return full_key in self._values["parameters"]
        return full_key in self.parameters

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
