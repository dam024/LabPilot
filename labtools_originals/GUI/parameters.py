from __future__ import annotations

from abc import abstractmethod
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Dict,
    Generic,
    List,
    Type,
    TypeVar,
    override,
)

from PySide6.QtWidgets import QWidget, QGroupBox, QVBoxLayout


from labtools.GUI.binding import BindingSupport
import labtools.GUI.objects as objects

if TYPE_CHECKING:
    from labtools.analysis import View
from labtools.utils import AbstractProperties

T = TypeVar("T")

# ============================================================================
# GUI Param wrappers
# ============================================================================


class GUIParameter:
    def __init__(self, widget: objects.Widget) -> None:
        self.widget = widget


# ============================================================================
# Parametrable base class
# ============================================================================


class GUIParametrable(AbstractProperties, BindingSupport):
    title: str

    def __init__(self) -> None:
        super().__init__()
        self.__param: List[GUIParameter] = []

        self._check_for_property("title", str)

    @override
    def _set_if_not_defined(self, name: str, value):
        # Add support for properties defined as `Binding`.
        if name not in self._bindings:
            return super()._set_if_not_defined(name, value)

    @abstractmethod
    def get_parameters(self, frame: QWidget, view: View | None) -> List[GUIParameter]:
        pass

    def create_group(
        self,
        frame: QWidget,
    ) -> QVBoxLayout:
        self.group_main = QGroupBox(self.title, frame)

        layout = QVBoxLayout()
        self.group_main.setLayout(layout)

        return layout

    def create_widget(self, frame: QWidget, view: View | None) -> QWidget:
        # Build the main group and its layout
        self.group_layout = self.create_group(frame)

        # To avoid garbage collection, the parameters are all saved into a private variable.
        param = self.get_parameters(self.group_main, view)
        self.__param.extend(param)

        # Add all widgets to the current layout
        for p in param:
            self.group_layout.addWidget(p.widget.get_widget())

        if len(param) == 0:
            self.group_main.deleteLater()

        return self.group_main

    def destroy(self) -> None:
        self.group_main.deleteLater()
