from __future__ import annotations
from typing import Callable, Iterable, List, Literal, Tuple

from PySide6.QtWidgets import QWidget
import numpy as np

from labpilot.analysis import View
import labpilot.plots.plot_backend as pb
from labpilot.plots.plots import GraphSet, GraphSetData, UsePlotBackend
import labpilot.GUI.parameters as params
import labpilot.GUI.objects as gui_obj


class SimpleData(GraphSetData):
    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = x
        self.y = y


class SimplePlot(GraphSet):
    def __init__(
        self,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        xlim: Tuple[float, float] | None = None,
        ylim: Tuple[float, float] | None = None,
        xscale: Literal["log", "linear"] = "linear",
        yscale: Literal["log", "linear"] = "linear",
        update_axis: bool = False,
        **kwags,
    ) -> None:
        """This class represents the base plot that can be done. It will just plot a single curve on a plot

        Args:
            update_axis (bool, optional): Indicates if the axis must be adapted automatically
        """
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.xlim = xlim
        self.ylim = ylim
        self.xscale = xscale
        self.yscale = yscale
        self.update_axis = update_axis
        super().__init__(name=name, **kwags)

    def pre_process_data(self, raw_data: np.ndarray) -> SimpleData:
        if len(raw_data.shape) > 1 and raw_data.shape[0] > 1:
            return SimpleData(x=raw_data[0, :], y=raw_data[1, :])
        else:
            return SimpleData(x=np.array([]), y=np.array([]))

    def prepare_plot(self, figure: pb.PlotBackend):
        # Generate fig

        figure.set_title(self.title)
        figure.set_xlabel(self.xlabel)
        figure.set_ylabel(self.ylabel)
        figure.set_xscale(self.xscale)
        figure.set_yscale(self.yscale)

        self.line = figure.plot([], [])

        if self.xlim is not None:
            figure.set_xlim(*self.xlim)
        if self.ylim is not None:
            figure.set_ylim(*self.ylim)

        self.text_box = figure.text(
            0.98, 0.5, f"avg: \ncur: ", horizontalalignment="left"
        )

    def set_data(self, x: np.ndarray, y: np.ndarray):
        z = np.vstack((x, y))

        self.update_data(z)

    def update_plot_data(
        self, processed_data: SimpleData
    ) -> Iterable[pb.Line | pb.Text]:
        self.line.set_data(processed_data.x, processed_data.y)
        self.text_box.set_text(
            f"avg: {np.nanmean(processed_data.y):.2f}\ncur: {processed_data.y[-1] or np.nan:.2f}"
        )

        if self.update_axis:
            self.update_axis_limits(self.figure, processed_data.x, processed_data.y)

        return (self.line, self.text_box)


class GeneralData:
    def __init__(self, data: np.ndarray) -> None:
        self.data = data


class GeneralPlot(GraphSet):
    def __init__(
        self,
        name: str,
        # ax: List[Axes],
        prepare_plot: Callable[[pb.PlotBackend], None],
        udpate_data: Callable[[GeneralData], Iterable[pb.Line | pb.Text]],
        **kwags,
    ) -> None:
        """This class represents the base plot that can be done. It will just plot a single curve on a plot

        Args:
            update_axis (bool, optional): Indicates if the axis must be adapted automatically
        """
        self._prepare_plot = prepare_plot
        self._update_data = udpate_data
        super().__init__(name=name, **kwags)

    @classmethod
    def create_figure(cls) -> pb.PlotBackend:
        return UsePlotBackend()

    def pre_process_data(self, raw_data: np.ndarray) -> GeneralData:
        return GeneralData(raw_data)

    def prepare_plot(self, figure: pb.PlotBackend):
        self._prepare_plot(figure)

    def update_plot_data(
        self, processed_data: GeneralData
    ) -> Iterable[pb.Line | pb.Text]:
        it = self._update_data(processed_data)

        self.figure.set_auto_axis()

        return it

    def set_data(self, data: np.ndarray):
        d = GeneralData(data)
        self.update_plot_data(d)


class MaximizationPlot(SimplePlot, params.GUIParametrable):
    def __init__(
        self,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        xlim: Tuple[float, float] | None = None,
        ylim: Tuple[float, float] | None = None,
        xscale: Literal["log", "linear"] = "linear",
        yscale: Literal["log", "linear"] = "linear",
        update_axis: bool = False,
        **kwargs,
    ) -> None:
        self.reset_max_value()
        super().__init__(
            name,
            title,
            xlabel,
            ylabel,
            xlim,
            ylim,
            xscale,
            yscale,
            update_axis,
            **kwargs,
        )
        params.GUIParametrable.__init__(self)

    def prepare_plot(self, figure: pb.PlotBackend):
        out = super().prepare_plot(figure)

        # Creates a horizontal line to show the maximum value
        self.h_line = figure.axhline(y=self.max_value, color="r", linestyle="--", lw=1)

        return out

    def update_plot_data(
        self, processed_data: SimpleData
    ) -> Iterable[pb.Line | pb.Text]:
        # Update the data from the horizontal line
        self.h_line.set_ydata([self.max_value, self.max_value])
        return super().update_plot_data(processed_data)

    def update_axis_limits(
        self, ax: pb.PlotBackend, x_data: np.ndarray, y_data: np.ndarray
    ):
        # Includes horizontal line into the y data, to update axis accordingly
        min_value = min(np.nanmin(y_data), self.max_value)
        max_value = max(np.nanmax(y_data), self.max_value)
        factor = 0.1
        match self.y_limits_update_policy:
            case self.AxisUpdatePolicy.STRICT_BOUNDS:
                max_bound = self.max_value + (min_value - max_value) * factor
            case self.AxisUpdatePolicy.CENTERED_AROUND_ZERO:
                max_bound = (
                    max(abs(self.max_value), abs(min_value))
                    + 2 * abs(max_value) * factor
                )
            case self.AxisUpdatePolicy.FROM_ZERO:
                max_bound = (
                    max(abs(self.max_value), abs(min_value))
                    + 2 * abs(max_value) * factor
                )
            case _:
                raise NotImplementedError(
                    f"Unimplemented AxisUpdatePolicy `{self.AxisUpdatePolicy.__class__.__name__}.{self.x_limits_update_policy.name}`"
                )

        return super().update_axis_limits(
            ax,
            x_data,
            np.append(y_data, [max_bound]),
        )

    def set_data(self, x: np.ndarray, y: np.ndarray):
        # Update maximum value when new data come
        self.max_value = max(np.nanmax(y), self.max_value)
        return super().set_data(x, y)

    ## Parameters
    def get_parameters(
        self, frame: QWidget, view: View | None
    ) -> List[params.GUIParameter]:
        l: List[params.GUIParameter] = []

        l.append(
            params.GUIParameter(
                widget=gui_obj.ButtonWidget(
                    frame, text="Reset maximum value", action=self.reset_max_value
                )
            )
        )

        return l

    def reset_max_value(self):
        self.max_value = -np.inf
