from dataclasses import dataclass
from typing import List, Literal

from PySide6.QtWidgets import QWidget
import numpy as np
import numpy.typing as npt
import pyqtgraph as pg
from PySide6.QtCore import Qt
from pyqtgraph.exporters import ImageExporter
from pyqtgraph.graphicsItems.ViewBox import ViewBox
from pyqtgraph.widgets.PlotWidget import PlotItem

import logging

logger = logging.getLogger(__name__)

import labpilot.plots.plot_backend as pb
from labpilot import config


_LINESTYLES = {
    None: Qt.PenStyle.SolidLine,
    "-": Qt.PenStyle.SolidLine,
    "--": Qt.PenStyle.DashLine,
    ":": Qt.PenStyle.DotLine,
    "-.": Qt.PenStyle.DashDotLine,
    "-:": Qt.PenStyle.DashDotDotLine,
}


@dataclass(slots=True)
class _LineEntry:
    item: object
    right_axis: bool
    is_horizontal: bool


class _AxesText:
    __slots__ = ("x_norm", "y_norm", "item")

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        horizontalalignment: Literal["left", "center", "right"],
    ) -> None:
        self.x_norm = x
        self.y_norm = y

        anchor = {
            "left": (0.0, 0.5),
            "center": (0.5, 0.5),
            "right": (1.0, 0.5),
        }[horizontalalignment]

        self.item = pg.TextItem(text=text, anchor=anchor, ensureInBounds=True)

    def set_text(self, text: str):
        self.item.setText(text)


class AxisItemCustom(pg.AxisItem):
    """This subclass handles better tick naming and scaling. It also improves the auto SI scaling of pyqtgraph."""

    def __init__(
        self,
        orientation: str,
        pen=None,
        textPen=None,
        tickPen=None,
        linkView=None,
        parent=None,
        maxTickLength=-5,
        showValues=True,
        **args,
    ):
        super().__init__(
            orientation,
            pen,
            textPen,
            tickPen,
            linkView,
            parent,
            maxTickLength,
            showValues,
            **args,
        )
        self.enableAutoSIPrefix(False)

    # def tickStrings(self, values: list[float], scale: float, spacing: float):
    def tickStrings(
        self, values: list[float], scale: float, spacing: float | None
    ):  # Spacing is sometimes `None`, creating segemtation faults!!!
        # This method is responsible for converting the values in tick strings.
        return super().tickStrings(values, scale, spacing)

    def linkedViewChanged(self, view, newRange=None):
        ## This method is responsible for:
        # - Computing the new scaling
        # - Updating the label of the axis (to reflect the correct range)
        # - Updating the global scaling
        # Changes must take effect only if they have changed and if newRange is not None
        return super().linkedViewChanged(view, newRange)


class PyQtBackend(pb.PlotBackend[pg.PlotWidget, PlotItem]):
    def __init__(self) -> None:
        self.fig = pg.PlotWidget(
            axisItems={
                "left": AxisItemCustom(orientation="left"),
                "bottom": AxisItemCustom(orientation="bottom"),
            }
        )
        self.ax: PlotItem = self.fig.getPlotItem()
        self.ax.hideButtons()  # Hide the buttons that allow the user to reset the plot scale
        self.ax.getViewBox().disableAutoRange()
        self.ax.layout.setContentsMargins(5, 5, 50, 5)

        self.ax_right: ViewBox | None = None

        self.lines: List[_LineEntry] = []
        self.texts: List[_AxesText] = []

        self._left_axis = self.ax.getAxis("left")
        self._right_axis_item = self.ax.getAxis("right")
        self._bottom_axis = self.ax.getAxis("bottom")

        self._x_log = False
        self._y_log = False

        self._grid_x = False
        self._grid_y = False

        self._right_axis_update_connected = False
        self._text_update_connected = False

        self._right_axis_item.setStyle(showValues=False)

        if config.simulation and False:
            # This feature is not ready, so it has been deactivated...
            # Add the mouse coordinate
            self.coord_label = self.text(0.01, -0.05, "mouse")

            self.proxy = pg.SignalProxy(
                self.fig.scene().sigMouseMoved,
                rateLimit=60,
                slot=self.mouse_moved,
            )

        super().__init__()

    @property
    def prefered_export_format(self) -> str:
        return "PNG (*.png)"

    def mouse_moved(self, evt):
        logger.dev_warning(
            "Improve the coordinate solution. I need to be able to see the location of the cursor, which is not the case right now..."
        )
        pos = evt[0]  # SignalProxy passes arguments as a tuple

        if self.fig.sceneBoundingRect().contains(pos):
            mouse_point = self.fig.getViewBox().mapSceneToView(pos)

            self.coord_label.set_text(
                f"X = {mouse_point.x():.6f}    " f"Y = {mouse_point.y():.6f}"
            )

    def get_figure(self) -> pg.PlotWidget:
        return self.fig

    def make_right_axes(self):
        if self.ax_right is not None:
            return

        self.ax_right = ViewBox()
        self.ax.scene().addItem(self.ax_right)

        self.ax.showAxis("right")
        self._right_axis_item.setStyle(showValues=True)
        self._right_axis_item.linkToView(self.ax_right)

        self.ax_right.setXLink(self.ax)

        def update_views(*args):
            if self.ax_right is None:
                return

            self.ax_right.setGeometry(self.ax.vb.sceneBoundingRect())
            self.ax_right.linkedViewChanged(
                self.ax.vb,
                self.ax_right.XAxis,
            )

        self.ax.vb.sigResized.connect(update_views)
        self.ax.vb.sigRangeChanged.connect(update_views)
        self._right_axis_update_connected = True

        update_views()

    def _get_axis(self, right_axis: bool):
        """Get the `PlotItem` corresponding to the desired axis"""
        if right_axis:
            if self.ax_right is None:
                raise pb.MissingAxeError("You haven't created any right axis yet!")
            return self.ax_right

        return self.ax

    def _make_pen(
        self,
        color: str | None,
        linestyle: str | None,
        lw: int | None,
    ):
        pen = pg.mkPen(
            color=color if color is not None else pg.getConfigOption("foreground"),
            width=lw if lw is not None else 1,
        )

        pen.setStyle(
            _LINESTYLES.get(
                linestyle,
                Qt.PenStyle.SolidLine,
            )
        )

        return pen

    def _connect_text_updates_if_needed(self):
        if self._text_update_connected:
            return

        self.ax.vb.sigRangeChanged.connect(self._update_axes_text_positions)
        self.ax.vb.sigResized.connect(self._update_axes_text_positions)

        self._text_update_connected = True

    def _update_axes_text_positions(self, *args):
        if not self.texts:
            return

        rect = self.ax.vb.sceneBoundingRect()

        xmin = rect.left()
        ymin = rect.bottom()

        dx = rect.right() - rect.left()
        dy = rect.top() - rect.bottom()

        for text in self.texts:
            x = xmin + text.x_norm * dx
            y = ymin + text.y_norm * dy

            text.item.setPos(x, y)

        # (xmin, xmax), (ymin, ymax) = self.ax.vb.viewRange()

        # dx = xmax - xmin
        # dy = ymax - ymin

        # for text in self.texts:
        #    x = xmin + text.x_norm * dx
        #    y = ymin + text.y_norm * dy
        #    # x = 0.98
        #    # y = 0.5
        #    print("Position: ", x, y)
        #    text.item.setPos(x, y)

    def _finite_min_max(self, values):
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]

        if arr.size == 0:
            return None

        if arr.size == 1:
            value = float(arr[0])
            return value, value

        return float(np.min(arr)), float(np.max(arr))

    def _transform_range_for_log(self, low: float, high: float, is_log: bool):
        if not is_log:
            return low, high

        if low <= 0 or high <= 0:
            return None

        return float(np.log10(low)), float(np.log10(high))

    def _expand_degenerate_range(self, low: float, high: float):
        if low != high:
            return low, high

        if low == 0:
            return -0.5, 0.5

        delta = abs(low) * 0.05
        return low - delta, high + delta

    def _autoscale_axis(self, right_axis: bool):
        x_values = []
        y_values = []

        for entry in self.lines:
            if entry.right_axis != right_axis:
                continue

            item = entry.item

            if isinstance(item, pg.PlotDataItem):
                x = item.xData
                y = item.yData

                if x is not None:
                    x_values.append(x)

                if y is not None:
                    y_values.append(y)

            elif isinstance(item, pg.InfiniteLine):
                if entry.is_horizontal:
                    y_values.append([item.value()])

        if not x_values and not y_values:
            return None, None

        x_range = None
        y_range = None

        if x_values:
            x_all = np.concatenate(
                [np.asarray(v, dtype=float).ravel() for v in x_values]
            )
            x_range = self._finite_min_max(x_all)

        if y_values:
            y_all = np.concatenate(
                [np.asarray(v, dtype=float).ravel() for v in y_values]
            )
            y_range = self._finite_min_max(y_all)

        return x_range, y_range

    def _set_view_range(
        self,
        vb: ViewBox,
        x_range,
        y_range,
        set_x: bool,
        set_y: bool,
    ):
        kwargs = {}

        if set_x and x_range is not None:
            xmin, xmax = self._expand_degenerate_range(*x_range)
            transformed = self._transform_range_for_log(
                xmin,
                xmax,
                self._x_log,
            )

            if transformed is not None:
                kwargs["xRange"] = transformed

        if set_y and y_range is not None:
            ymin, ymax = self._expand_degenerate_range(*y_range)
            transformed = self._transform_range_for_log(
                ymin,
                ymax,
                self._y_log,
            )

            if transformed is not None:
                kwargs["yRange"] = transformed

        if kwargs:
            vb.setRange(
                padding=0.05,
                **kwargs,
            )

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

        if len(x) * len(y) == 0:
            x = [0.0]
            y = [0.0]

        symbol = None
        if marker is not None:
            conversion_marker = {"*": "star"}
            symbol = conversion_marker[marker] or symbol

        curve = pg.PlotDataItem(
            np.asarray(x),
            np.asarray(y),
            pen=self._make_pen(
                color=color,
                linestyle=linestyle,
                lw=lw,
            ),
            name=label,
            symbol=symbol,
            symbolBrush=color,
            symbolPen=color,
            hoverable=config.simulation,
            tip=lambda x, y, data: f"x={x:.2f}\ny={y:.2f}",
        )

        if right_axis:
            axis = self._get_axis(right_axis=True)
            axis.addItem(curve)
        else:
            self.ax.addItem(curve)

        self.lines.append(
            _LineEntry(
                item=curve,
                right_axis=right_axis,
                is_horizontal=False,
            )
        )

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
        line = pg.InfiniteLine(
            pos=y,
            angle=0,
            pen=self._make_pen(
                color=color,
                linestyle=linestyle,
                lw=lw,
            ),
            label=label,
        )

        if right_axis:
            axis = self._get_axis(right_axis=True)
            axis.addItem(line)
        else:
            self.ax.addItem(line)

        idx = len(self.lines)

        self.lines.append(
            _LineEntry(
                item=line,
                right_axis=right_axis,
                is_horizontal=True,
            )
        )

        return pb.Line(self, idx)

    def set_data(self, line: pb.Line, x: npt.NDArray, y: npt.NDArray):
        entry = self.lines[line.index]
        item = entry.item

        if isinstance(item, pg.PlotDataItem):
            item.setData(
                x=np.asarray(x),
                y=np.asarray(y),
            )

        elif isinstance(item, pg.InfiniteLine):
            y_arr = np.asarray(y)

            if y_arr.size > 0:
                item.setValue(float(y_arr.ravel()[0]))

    def set_ydata(self, line: pb.Line, y: npt.NDArray | List[float]):
        entry = self.lines[line.index]
        item = entry.item

        if isinstance(item, pg.PlotDataItem):
            y_arr = np.asarray(y)

            x = item.xData

            if x is None:
                x = np.arange(y_arr.size)

            item.setData(
                x=x,
                y=y_arr,
            )

        elif isinstance(item, pg.InfiniteLine):
            y_arr = np.asarray(y)

            if y_arr.size > 0:
                item.setValue(float(y_arr.ravel()[0]))

    def text(
        self,
        x: float,
        y: float,
        text: str,
        horizontalalignment: Literal["left", "center", "right"] = "left",
    ) -> pb.Text:
        txt = _AxesText(
            x=x,
            y=y,
            text=text,
            horizontalalignment=horizontalalignment,
        )

        # self.ax.vb.addItem(txt.item)
        self.fig.scene().addItem(txt.item)
        self.texts.append(txt)

        self._connect_text_updates_if_needed()
        self._update_axes_text_positions()

        idx = len(self.texts) - 1

        return pb.Text(self, index=idx)

    def set_text(self, obj: pb.Text, text: str):
        self.texts[obj.index].set_text(text)

    #### Styling

    def set_title(self, title: str):
        self.ax.setTitle(title)

    def set_xlabel(self, label: str):
        self.ax.setLabel("bottom", label)

    def set_ylabel(self, label: str, color: str | None = None):
        if color is None:
            self.ax.setLabel("left", label)
        else:
            self.ax.setLabel("left", label, color=color)

    def set_ylabel_right(self, label: str, color: str | None = None):
        if self.ax_right is None:
            raise pb.MissingAxeError("Missing axes on the right")

        if color is None:
            self.ax.setLabel("right", label)
        else:
            self.ax.setLabel("right", label, color=color)

    def set_xscale(self, scale: Literal["log", "linear"]):
        self._x_log = scale == "log"
        # self._apply_log_mode()
        self.ax.setLogMode(x=scale == "log")

    def set_yscale(self, scale: Literal["log", "linear"]):
        self._y_log = scale == "log"
        # self._apply_log_mode()
        self.ax.setLogMode(y=scale == "log")

    def set_xlim(self, x: float, y: float):
        transformed = self._transform_range_for_log(
            x,
            y,
            self._x_log,
        )

        if transformed is None:
            return

        self.ax.setXRange(
            transformed[0],
            transformed[1],
            padding=0,
        )

    def set_ylim(self, x: float, y: float):
        transformed = self._transform_range_for_log(
            x,
            y,
            self._y_log,
        )

        if transformed is None:
            return

        self.ax.setYRange(
            transformed[0],
            transformed[1],
            padding=0,
        )

    def set_ylim_right(self, x: float, y: float):
        if self.ax_right is None:
            raise pb.MissingAxeError("Missing axes on the right")

        transformed = self._transform_range_for_log(
            x,
            y,
            self._y_log,
        )

        if transformed is None:
            return

        self.ax_right.setYRange(
            transformed[0],
            transformed[1],
            padding=0,
        )

    def tick_params(
        self,
        axis: Literal["x", "y", "both"],
        right_axis: bool = False,
        labelcolor: str | None = None,
    ):
        self._get_axis(right_axis=right_axis)

        if labelcolor is None:
            return

        if axis in ("x", "both"):
            self._bottom_axis.setTextPen(labelcolor)

        if axis in ("y", "both"):
            if right_axis:
                self._right_axis_item.setTextPen(labelcolor)
            else:
                self._left_axis.setTextPen(labelcolor)

    def grid(
        self,
        right_axis: bool = False,
        visible: bool | None = None,
        which: Literal["major", "minor", "both"] = "major",
        axis: Literal["x", "y", "both"] = "both",
    ):
        self._get_axis(right_axis=right_axis)

        if axis in ("x", "both"):
            if visible is None:
                self._grid_x = not self._grid_x
            else:
                self._grid_x = visible

        if axis in ("y", "both"):
            if visible is None:
                self._grid_y = not self._grid_y
            else:
                self._grid_y = visible

        self.ax.showGrid(
            x=self._grid_x,
            y=self._grid_y,
        )

    def legend(self):
        self.ax.addLegend()

    ###### Plots properties

    def set_auto_axis(self):
        left_x_range, left_y_range = self._autoscale_axis(right_axis=False)
        right_x_range, right_y_range = self._autoscale_axis(right_axis=True)

        x_ranges = [r for r in (left_x_range, right_x_range) if r is not None]

        if x_ranges:
            global_x_range = (
                min(r[0] for r in x_ranges),
                max(r[1] for r in x_ranges),
            )
        else:
            global_x_range = None

        self._set_view_range(
            vb=self.ax.vb,
            x_range=global_x_range,
            y_range=left_y_range,
            set_x=True,
            set_y=True,
        )

        if self.ax_right is not None:
            self._set_view_range(
                vb=self.ax_right,
                x_range=None,
                y_range=right_y_range,
                set_x=False,
                set_y=True,
            )

        self._update_axes_text_positions()

    def close(self):
        """Close a plot"""
        self.fig.close()

        self.lines.clear()
        self.texts.clear()

        self.ax_right = None

    def save(self, path: str):
        exporter = ImageExporter(self.fig.scene())
        exporter.export(path)

    def get_app_canvas(self) -> QWidget:
        return self.fig

    def update_canvas(self, canvas):
        return super().update_canvas(canvas)
