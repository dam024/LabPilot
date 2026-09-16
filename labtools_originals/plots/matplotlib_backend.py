from typing import List, Literal


from PySide6.QtWidgets import QWidget
import matplotlib as mpl

from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.lines import Line2D
from matplotlib.text import Text
import numpy.typing as npt
import numpy as np
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import labtools.plots.plot_backend as pb

### Probably not required anymore:
# mpl.rcParams["path.simplify"] = True
# mpl.rcParams["path.simplify_threshold"] = 1.0
# mpl.rcParams["agg.path.chunksize"] = 10000


class MatplotlibBackend(pb.PlotBackend[Figure, Axes]):
    def __init__(self) -> None:
        self.fig = Figure()
        self.ax = self.fig.subplots()
        self.ax_right: Axes | None = None
        self.lines: List[Line2D] = []
        self.texts: List[Text] = []
        super().__init__()

    def get_figure(self) -> Figure:
        return self.fig

    def make_right_axes(self):
        self.ax_right = self.ax.twinx()

    def _get_axis(self, right_axis: bool) -> Axes:
        if right_axis:
            if self.ax_right is None:
                raise pb.MissingAxeError("You haven't created any right axis yet!")
            ax = self.ax_right
        else:
            ax = self.ax

        return ax

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
    ) -> pb.Line:
        idx = len(self.lines)

        ax = self._get_axis(right_axis=right_axis)

        l = ax.plot(
            x, y, label=label, marker=marker, color=color, linestyle=linestyle, lw=lw
        )[0]
        self.lines.append(l)

        return pb.Line(self, index=idx)

    def axhline(
        self,
        y: float,
        label: str | None = None,
        color: str | None = None,
        linestyle: str | None = None,
        lw: int | None = None,
        right_axis: bool = False,
    ) -> pb.Line:
        ax = self._get_axis(right_axis=right_axis)

        l = ax.axhline(y, label=label, color=color, linestyle=linestyle, lw=lw)
        idx = len(self.lines)
        self.lines.append(l)
        return pb.Line(self, idx)

    def set_data(self, line: pb.Line, x: npt.NDArray, y: npt.NDArray):
        self.lines[line.index].set_data(x, y)

    def set_ydata(self, line: pb.Line, y: npt.NDArray | List[float]):
        self.lines[line.index].set_ydata(y)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        horizontalalignment: Literal["left", "center", "right"] = "left",
    ) -> pb.Text:
        txt = self.ax.text(
            x,
            y,
            text,
            transform=self.ax.transAxes,
            horizontalalignment=horizontalalignment,
        )
        idx = len(self.texts)
        self.texts.append(txt)

        return pb.Text(self, index=idx)

    def set_text(self, obj: pb.Text, text: str):
        self.texts[obj.index].set_text(text)

    #### Styling
    def set_title(self, title: str):
        self.ax.set_title(title)

    def set_xlabel(self, label: str):
        self.ax.set_xlabel(label)

    def set_ylabel(self, label: str, color: str | None = None):
        if color is None:
            color = mpl.rcParams["axes.labelcolor"]
        self.ax.set_ylabel(label, color=color)

    def set_ylabel_right(self, label: str, color: str | None = None):
        if color is None:
            color = mpl.rcParams["axes.labelcolor"]

        if self.ax_right is not None:
            self.ax_right.set_ylabel(label, color=color)
        else:
            raise pb.MissingAxeError("Missing axes on the right")

    def set_xscale(self, scale: Literal["log", "linear"]):
        self.ax.set_xscale(scale)

    def set_yscale(self, scale: Literal["log", "linear"]):
        self.ax.set_yscale(scale)

    def set_xlim(self, x: float, y: float):
        self.ax.set_xlim(x, y)

    def set_ylim(self, x: float, y: float):
        self.ax.set_ylim(x, y)

    def set_ylim_right(self, x: float, y: float):
        if self.ax_right is not None:
            self.ax_right.set_ylim(x, y)
        else:
            raise pb.MissingAxeError("Missing axes on the right")

    def tick_params(
        self,
        axis: Literal["x", "y", "both"],
        right_axis: bool = False,
        labelcolor: str | None = None,
    ):
        ax = self._get_axis(right_axis=right_axis)
        ax.tick_params(axis=axis, labelcolor=labelcolor)

    def grid(
        self,
        right_axis: bool = False,
        visible: bool | None = None,
        which: Literal["major", "minor", "both"] = "major",
        axis: Literal["x", "y", "both"] = "both",
    ):
        ax = self._get_axis(right_axis)

        ax.grid(visible=visible, axis=axis, which=which)

    def legend(self):
        self.ax.legend()

    ###### Plots properties
    def set_auto_axis(self):
        self.ax.relim()
        self.ax.autoscale_view()

        if self.ax_right is not None:
            self.ax_right.relim()
            self.ax_right.autoscale_view()

    def close(self):
        """Close a plot"""
        self.fig.clear()
        self.fig.clf()
        plt.close(self.fig)

    def save(self, path: str):
        self.fig.savefig(fname=path)

    def get_app_canvas(self) -> QWidget:
        return FigureCanvasQTAgg(self.get_figure())

    def update_canvas(self, canvas):
        """Executes code to update the canvas"""
        canvas.draw_idle()
