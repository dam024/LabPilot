from abc import abstractmethod, ABC, abstractproperty
import os
import re
from typing import List, Literal, TypeVar, Generic
from PySide6.QtWidgets import QWidget
import numpy as np
import numpy.typing as npt


class PlotContent:
    def __init__(self, backend: "PlotBackend", index: int) -> None:
        self.index = index
        self.backend = backend
        backend._lines.append(self)


class Line(PlotContent):
    def set_data(self, x: npt.NDArray, y: npt.NDArray):
        self.backend.set_data(self, x, y)

    def set_ydata(self, y: npt.NDArray | List[float]):
        self.backend.set_ydata(self, y)


class Text(PlotContent):
    def set_text(self, text: str):
        self.backend.set_text(self, text)


class MissingAxeError(Exception):
    pass


Figure = TypeVar("Figure")
Axes = TypeVar("Axes")


class PlotBackend(ABC, Generic[Figure, Axes]):
    _lines: List[PlotContent] = []

    @property
    def prefered_export_format(self) -> str:
        """Returns the list of file types that can be used for saving the plot"""
        return "PDF (*.pdf);;PNG (*.png)"

    @property
    def prefered_extensions(self) -> List[str]:
        """List all valid extensions that can be used for the plots"""
        return re.findall(r"\*\.(\w+)", self.prefered_export_format)

    @property
    def default_extension(self) -> str:
        """Return the extension that will be used by default when saving a plot"""
        return self.prefered_extensions[0]

    @abstractmethod
    def get_figure(self) -> Figure:
        pass

    @abstractmethod
    def make_right_axes(self):
        pass

    #### Data management
    @abstractmethod
    def plot(
        self,
        x: npt.NDArray | List[float],
        y: npt.NDArray | List[float],
        label: str | None = None,
        color: str | None = None,
        marker: str | None = None,
        linestyle: str | None = None,
        lw: int | None = None,
        right_axis: bool = False,
    ) -> Line:
        pass

    @abstractmethod
    def axhline(
        self,
        y: float,
        label: str | None = None,
        color: str | None = None,
        linestyle: str | None = None,
        lw: int | None = None,
        right_axis: bool = False,
    ) -> Line:
        """Creates a horizontal line"""

    @abstractmethod
    def set_data(self, line: Line, x: npt.NDArray, y: npt.NDArray):
        """Sets the data of the given line"""

    @abstractmethod
    def set_ydata(self, line: Line, y: npt.NDArray | List[float]):
        """Sets the y data of the given line"""

    @abstractmethod
    def text(
        self,
        x: float,
        y: float,
        text: str,
        horizontalalignment: Literal["left", "center", "right"] = "left",
    ) -> Text:
        """Creates a text to place on the plot.

        Note:
            The coordinates are given as a purcentage from the left/bottom!!!
        """

    @abstractmethod
    def set_text(self, obj: Text, text: str):
        """Sets the text of a ```Text``` object"""

    ### Styling
    @abstractmethod
    def set_title(self, title: str):
        """Sets the title of the plot"""

    @abstractmethod
    def set_xlabel(self, label: str):
        """Sets the x label of the plot"""

    @abstractmethod
    def set_ylabel(self, label: str, color: str | None = None):
        """Sets the left y label of the plot"""

    @abstractmethod
    def set_ylabel_right(self, label: str, color: str | None = None):
        """Sets the right y label of the plot"""

    @abstractmethod
    def set_xscale(self, scale: Literal["log", "linear"]):
        """Sets the scale of the plot"""

    @abstractmethod
    def set_yscale(self, scale: Literal["log", "linear"]):
        """Sets the scale of the plot"""

    @abstractmethod
    def tick_params(
        self,
        axis: Literal["x", "y", "both"],
        right_axis: bool = False,
        labelcolor: str | None = None,
    ):
        pass

    @abstractmethod
    def grid(
        self,
        right_axis: bool = False,
        visible: bool | None = None,
        which: Literal["major", "minor", "both"] = "major",
        axis: Literal["x", "y", "both"] = "both",
    ):
        pass

    @abstractmethod
    def legend(self):
        pass

    ### Plots properties
    @abstractmethod
    def set_xlim(self, x: float, y: float):
        """Set the limits on the x axis"""
        pass

    @abstractmethod
    def set_ylim(self, x: float, y: float):
        """Set the limits on the left y axis"""
        pass

    @abstractmethod
    def set_ylim_right(self, x: float, y: float):
        """Set the limits on the right y axis"""
        pass

    @abstractmethod
    def set_auto_axis(self):
        """Automatically set the limits of the axis"""

    @abstractmethod
    def close(self):
        """Close a plot"""
        pass

    @abstractmethod
    def save(self, path: str):
        """Save the plot at the given path

        Note:
            The path must be valid!
        """
        pass

    @abstractmethod
    def get_app_canvas(self) -> QWidget:
        """Returns the Application Canvas that will be used in the PySide6 Application"""

    @abstractmethod
    def update_canvas(self, canvas):
        """Executes code to update the canvas"""
