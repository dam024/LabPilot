from __future__ import annotations
from abc import ABC, abstractmethod
import copy
import os
import numpy as np
from typing import Iterable, Tuple, List
import enum


import labtools.plots.plot_backend as pb

from labtools import logger, config

if config.use_gui:
    from labtools.plots.pyqt_backend import PyQtBackend as UsePlotBackend

    # from labtools.plots.matplotlib_backend import (
    #    MatplotlibBackend as UsePlotBackend,
    # )
else:
    from labtools.plots.matplotlib_backend import (
        MatplotlibBackend as UsePlotBackend,
    )


class GraphSetData:
    pass


class GraphSet[Data: GraphSetData](ABC):
    class AxisUpdatePolicy(enum.Enum):

        """This enumeration defines which method should be used while auto scaling. This can be used for all axes.

        Attributes:
            CENTERED_AROUND_ZERO (TYPE): The axis limits are centered around 0, while displaying all values. For the set `A`, it means the axis extends from -max(|A|) to max(|A|), with a padding
            FROM_ZERO (TYPE): The axis always shows the 0 value. This is useful if we display values that are only positive or only negative. Otherwise, it behaves like `STRICT_BOUNDS`
            STRICT_BOUNDS (TYPE): Displays only the axis from the minimum to the maximum value, including a padding.
        """

        CENTERED_AROUND_ZERO = enum.auto()
        STRICT_BOUNDS = enum.auto()
        FROM_ZERO = enum.auto()

    show: bool = False

    def __init__(
        self,
        name: str,
        x_limits_update_policy: AxisUpdatePolicy = AxisUpdatePolicy.STRICT_BOUNDS,
        y_limits_update_policy: AxisUpdatePolicy = AxisUpdatePolicy.STRICT_BOUNDS,
    ) -> None:
        """This class represents a single Figure as defined by matplotlib.

        The figure can contain multiple Axes, but it can ONLY contain a single figure...
        """
        self.name = name
        self.x_limits_update_policy = x_limits_update_policy
        self.y_limits_update_policy = y_limits_update_policy

    # @property
    # def figure_canvas(self):
    #    return self.figure.get_figure()

    @property
    def filename(self) -> str:
        """Returns the filename for a given file"""
        return self.name + "." + self.figure.default_extension

    def update_data(self, data: np.ndarray):
        """Receive the new data and handle them to update the plots"""
        if self.show:
            processed = self.pre_process_data(raw_data=data)
            self.graph_update(processed)

    def init_plots(self):
        """Initialize the plots"""
        self.figure: pb.PlotBackend = UsePlotBackend()
        self.prepare_plot(self.figure)

    def init_animation(self):
        """Start the animation of the GraphSet"""
        raise NotImplementedError(
            "Animation is deprecated. Reimplement the reature if necessary"
        )
        self.ani = animation.FuncAnimation(
            self.figure,
            self.graph_update,
            interval=1000,
            cache_frame_data=False,
        )

    def copy(self, name: str):
        new_version = copy.copy(self)
        new_version.name = name
        new_version.init_plots()
        return new_version

    def graph_update(self, data: Data) -> Iterable[pb.Line | pb.Text]:
        """Perform update pipeline for the graph"""

        # def wrapper(frame):
        updated = False

        # Update the data
        itr = self.update_plot_data(processed_data=data)

        return itr

    def update_axis_limits(
        self, ax: pb.PlotBackend, x_data: np.ndarray, y_data: np.ndarray
    ):
        """Update the axis limits of a plot"""
        match self.x_limits_update_policy:
            case self.AxisUpdatePolicy.STRICT_BOUNDS:
                ax.set_xlim(x_data[0], x_data[-1])
            case self.AxisUpdatePolicy.CENTERED_AROUND_ZERO:
                b = np.nan_to_num(np.nanmax(abs(x_data)) or 1.0, nan=1.0)
                ax.set_xlim(-b, b)
            case self.AxisUpdatePolicy.FROM_ZERO:
                m = min(np.nanmin(x_data), 0)
                M = max(np.nanmax(x_data), 0)
                ax.set_ylim(m, M)
            case _:
                raise NotImplementedError(
                    f"Unimplemented AxisUpdatePolicy `{self.AxisUpdatePolicy.__class__.__name__}.{self.x_limits_update_policy.name}`"
                )
        factor = 0.1
        match self.y_limits_update_policy:
            case self.AxisUpdatePolicy.STRICT_BOUNDS:
                ax.set_ylim(np.nanmin(y_data) or -1, np.nanmax(y_data) or 1)
            case self.AxisUpdatePolicy.CENTERED_AROUND_ZERO:
                b = np.nan_to_num(np.nanmax(abs(y_data)) or 1.0, nan=1.0)
                b += 2 * b * factor  # Add some margin to see the signal anyway...
                ax.set_ylim(-b, b)
            case self.AxisUpdatePolicy.FROM_ZERO:
                m = min(np.nanmin(y_data), 0)
                M = max(np.nanmax(y_data), 0)
                ax.set_ylim(m, M)
            case _:
                raise NotImplementedError(
                    f"Unimplemented AxisUpdatePolicy `{self.AxisUpdatePolicy.__class__.__name__}.{self.x_limits_update_policy.name}`"
                )

    @abstractmethod
    def pre_process_data(self, raw_data: np.ndarray) -> Data:
        """This method receives raw data and preprocess them to obtain the data to display



        Important:
            THIS METHOD IS INTENDED TO BE RUN ON A BACKGROUND THREAD
            Therefore, this method must be thread-safe, i.e. it must NOT call anything from matplotlib or any graphical element!

        Args:
            raw_data (np.ndarray): Raw data obtained from the measurement device

        Returns(ProcessedData):
                Processed data ready to be plotted. This must be in a subclass of a `ProcessedData` object

        """
        pass

    @abstractmethod
    def prepare_plot(self, figure: pb.PlotBackend):
        """Creates the plot and set its initial data"""
        pass

    @abstractmethod
    def update_plot_data(self, processed_data: Data) -> Iterable[pb.Line | pb.Text]:
        """Update the data from the plot

         Args:
             processed_data (ProcessedData): Data ready to be plotted

        Return:
             The list of plots that were modified
        """
        pass

    # @abstractmethod
    # def save(self, path: str):
    #
    # @abstractmethod
    # def close(self):

    def save(self, path: str):
        """Saves the plot at the given path

        Args:
            path (str): Path to the _directory_ that will contain the file. The filename is generated automatically!
        """
        filepath = os.path.join(path, self.filename)
        self.figure.save(filepath)

    def close(self):
        """Close all figures to save space"""
        self.figure.close()
