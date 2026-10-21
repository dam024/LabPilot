"""
This module contains a few graphical objects useful to build parameters
for the different components of the software.
"""

from __future__ import annotations

from enum import Enum
import logging
import os
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeGuard,
    TypeVar,
)
import math

# import matplotlib as mpl
# from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollBar,
    QFileDialog,
    QMessageBox,
    QMenu,
    QComboBox,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
)

from labpilot.GUI.binding import CBinding
import labpilot.plots.plots as plots
from labpilot.utils import threadSafe
from labpilot import config


class Widget:
    def __init__(self, widget: QWidget) -> None:
        self._widget = widget

    def get_widget(self) -> QWidget:
        return self._widget

    def show_context_menu(self, context_menu: QMenu):
        def _wrapper(position):
            context_menu.exec_(position)

        return _wrapper


# --------------------------------------------------
# Graph Canvas Wrapper
# --------------------------------------------------
class GraphCanvas(Widget):
    def __init__(self, parent: QWidget, graph: plots.GraphSet):
        self.graph = graph

        self.graph.init_plots()
        self.frame = 0

        self.canvas = self.graph.figure.get_app_canvas()

        self.add_context_menu()

        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(
            lambda pos: self.context_menu.exec_(self.canvas.mapToGlobal(pos))
        )

        super().__init__(self.canvas)

    def add_context_menu(self):
        self.context_menu = QMenu()

        save_action = self.context_menu.addAction("Save Plot")
        save_action.triggered.connect(self.save_plot)

    def update_plot(self):
        # self.canvas.draw_idle()
        self.graph.figure.update_canvas(self.canvas)
        self.frame += 1

    def destroy(self):
        self.canvas.deleteLater()

    def save_plot(self):
        initial_path = os.path.join(
            os.getcwd(),
            config.output_dir_plots,
        )

        path, _ = QFileDialog.getSaveFileName(
            self.get_widget(),
            "Save As",
            initial_path,
            self.graph.figure.prefered_export_format,
        )

        if path:
            self.graph.figure.save(path)


T = TypeVar("T", bound=QWidget)


class LabelledWidget[T: QWidget](Widget):
    def __init__(
        self,
        parent: QWidget,
        widget: T,
        label: str,
    ):
        self.container = QFrame(parent)

        layout = QGridLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        self.container.setLayout(layout)

        self.label = QLabel(label)
        self.widget = widget

        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.widget, 0, 1)

        layout.setColumnStretch(1, 1)

        super().__init__(self.container)


class Label(LabelledWidget):
    def __init__(
        self, parent: QWidget, label: str, text: str | CBinding[str | None]
    ) -> None:
        """Creates a new Label to show a given text

        Args:
            label (str): To place before the widget and indicate what is shown
            text (str | CBinding[str]): Value of the Label
        """
        if isinstance(text, CBinding):
            self.label_wg = QLabel(parent=parent, text=text.get())

            # Add change observation
            text.qt_variable().valueChanged.connect(self.setText)
        else:
            self.label_wg = QLabel(parent=parent, text=text)

        super().__init__(parent, self.label_wg, label)

    def setText(self, text: str | None):
        self.label_wg.setText("" if text is None else text)


class Entry(LabelledWidget):
    def __init__(self, parent: QWidget, label: str, text: str | CBinding[str]) -> None:
        """Creates a new Label to show a given text

        Args:
            label (str): To place before the widget and indicate what is shown
            text (str | CBinding[str]): Value of the Label
        """

        self.label_wg = QLineEdit(parent=parent)

        if isinstance(text, CBinding):
            self.label_wg.setText(text.get())

            # Add change observation
            text.qt_variable().valueChanged.connect(self.setText)
            self.label_wg.editingFinished.connect(
                lambda: text.set_signals(self.label_wg.text())
            )
        else:
            self.label_wg.setText(text)

        super().__init__(parent, self.label_wg, label)

    def setText(self, text: str | None):
        self.label_wg.setText("" if text is None else text)


def is_list[T](x: List[T] | List[Tuple[T, str]]) -> TypeGuard[List[T]]:
    return isinstance(x, list) and all(isinstance(item, str) for item in x)


def is_tuple_list[
    T
](x: List[T] | List[Tuple[T, str]]) -> TypeGuard[List[Tuple[T, str]]]:
    return isinstance(x, list) and all(
        isinstance(item, tuple) and len(item) == 2
        # and isinstance(item[0], T)
        and isinstance(item[1], str)
        for item in x
    )


class Combobox[T: str | Enum](LabelledWidget):
    def __init__(
        self,
        parent: QWidget,
        label: str,
        values: List[T] | Type[T] | List[Tuple[T, str]],
        current_value: Optional[T] | CBinding[T],
    ):
        # Compute a list with pair of (value, text). This is much more convenient to have a uniformized data structure...
        self._uniformize_values(values)

        self.combobox = QComboBox()
        self.combobox.addItems([v[1] for v in self.values])
        self.current_value = current_value

        if current_value is not None:
            if isinstance(current_value, CBinding):
                # Sets the current value
                v = current_value.get()
                # Sets the current value to the combobox (BEFORE THE SIGNAL IS SENT)
                self.setCurrentValue(v, default=0)

                # Add change observation
                current_value.qt_variable().valueChanged.connect(self.setCurrentValue)

                # Bind the change of the combobox to the value
                self.combobox.currentIndexChanged.connect(
                    lambda i: current_value.set_signals(self.values[i][0])
                )
            else:
                # Sets the current value
                v = current_value
                # Sets the current value to the combobox
                self.setCurrentValue(v, default=0)

        super().__init__(parent, self.combobox, label)

    def get_index_from_value(self, value: T) -> int:
        """Return the index of a value in the combobox

        If the value is not found, `-1` is returned
        """
        for i in range(len(self.values)):
            if self.values[i][0] == value:
                return i

        return -1

    def setCurrentValue(self, value: T, default: int = -1):
        """Sets the current value of the combobox

        Args:
            value (T): Value to set to the combobox
            default (int, optional): Index of the default value if the value is not found
        """
        i = self.get_index_from_value(value)
        if i >= 0 or default >= len(self.values):
            self.combobox.setCurrentIndex(i)  # Can have value -1, this means 'unset'
        else:
            self.combobox.setCurrentIndex(default)

    def getCurrentValue(self) -> T:
        """Gets the current value of the combobox"""
        i = self.combobox.currentIndex()
        return self.values[i][0]

    def _uniformize_values(self, values: List[T] | Type[T] | List[Tuple[T, str]]):
        """Makes the values in a list that is of a uniform type List[Tuple[T, str]] to have it convenient to work with.

        This function will set `self.values`. Please, work with this attribute!!!
        """
        self.values: List[Tuple[T, str]] = []
        if isinstance(values, type(Enum)):
            self.values = [(m, m.name) for m in values]
        elif isinstance(values, list):
            if len(values) > 0:
                if is_tuple_list(values):
                    self.values = values
                elif is_list(values):
                    self.values = [(v, str(v)) for v in values]

    def update_values(self, values: List[T] | Type[T] | List[Tuple[T, str]]):
        """Update the values of the combobox"""
        current = self.getCurrentValue()
        # Get the curre
        self._uniformize_values(values)

        self.combobox.clear()
        self.combobox.addItems([v[1] for v in self.values])

        self.setCurrentValue(current, default=0)


class Switch(LabelledWidget):
    def __init__(
        self,
        parent: QWidget,
        label: str,
        current_value: bool | CBinding[bool],
    ):
        self.switch = QCheckBox()
        self.current_value = current_value

        if isinstance(current_value, CBinding):
            self.switch.setChecked(current_value.get())

            # Update switch when the binding changes
            current_value.qt_variable().valueChanged.connect(self.switch.setChecked)

            # Update binding when the switch changes
            self.switch.toggled.connect(current_value.set_signals)
        else:
            self.switch.setChecked(current_value)

        super().__init__(parent, self.switch, label)

    def set_value(self, value: bool):
        self.switch.setChecked(value)

    def value(self) -> bool:
        return self.switch.isChecked()


class NumericalValueInput[T: int | float](LabelledWidget):
    """
    Widget to ask the user for a numerical value.

    It combines a slider and a spinbox.
    """

    value_changed = Signal(object)

    def __init__(
        self,
        parent: QWidget,
        from_: int | float,
        to: int | float,
        value: T | CBinding[T],
        text: str,
        # onchange: Optional[Callable[[], bool]] = None,
        increment: int | float = 1.0,
    ):
        # self.onchange = onchange

        frame = QFrame()
        layout = QHBoxLayout(frame)
        super().__init__(parent=parent, widget=frame, label=text)

        initial_value: T = value.get() if isinstance(value, CBinding) else value

        is_float = isinstance(initial_value, float)

        self.slider = QSlider(Qt.Orientation.Horizontal)

        self.nb_values: int = round((to - from_) / increment)

        self.slider.setMinimum(0)
        self.slider.setMaximum(int(self.nb_values))

        self.min_value = from_
        self.max_value = to
        self.increment = increment

        if is_float:
            self.spinbox = QDoubleSpinBox()
            self.spinbox.setDecimals(max(0, -math.floor(math.log10(increment))))
            self.spinbox.setSingleStep(float(increment))
            self.spinbox.setRange(from_, to)
            self.spinbox.setValue(initial_value)
        else:
            self.spinbox = QSpinBox()
            self.spinbox.setSingleStep(int(increment))
            self.spinbox.setRange(int(from_), int(to))
            self.spinbox.setValue(initial_value)

        layout.addWidget(self.spinbox)
        layout.addWidget(self.slider)

        layout.setStretch(1, 1)

        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self._set_slider_from_value(initial_value)

        # if onchange:
        #    self.spinbox.editingFinished.connect(onchange)
        if isinstance(value, CBinding):
            value.qt_variable().valueChanged.connect(self._set_value)

            self.spinbox.editingFinished.connect(
                lambda: value.set_signals(self.spinbox.value())
            )
            self.slider.sliderReleased.connect(
                lambda: value.set_signals(self._value_from_slider(self.slider.value()))
            )

    def _value_from_slider(self, slider_value: int) -> T:
        ratio = slider_value / self.nb_values
        return (
            self.min_value + slider_value * self.increment
        )  # self.min_value + ratio * (self.max_value - self.min_value)

    def _slider_from_value(self, value: T) -> int:
        v = value.get() if isinstance(value, CBinding) else value
        return int(round((v - self.min_value) / self.increment))

    def _set_slider_from_value(self, value: T):
        ratio = self._slider_from_value(value)

        self.slider.blockSignals(True)
        self.slider.setValue(int(ratio))
        self.slider.blockSignals(False)

    def _on_slider_changed(self, slider_value: int):
        value = self._value_from_slider(slider_value)

        self.spinbox.blockSignals(True)

        if isinstance(self.spinbox, QSpinBox):
            self.spinbox.setValue(int(round(value)))
        else:
            self.spinbox.setValue(float(value))

        self.spinbox.blockSignals(False)

        # self.value_changed.emit(self.spinbox.value())

    def _on_spinbox_changed(self, value: T):
        self._set_slider_from_value(value)
        # self.value_changed.emit(value)

    def _set_value(self, value: T):
        self.spinbox.blockSignals(True)
        self.slider.blockSignals(True)

        self.spinbox.setValue(value)
        self.slider.setValue(self._slider_from_value(value))

        self.slider.blockSignals(False)
        self.spinbox.blockSignals(False)

    def value(self):
        return self.spinbox.value()


class ButtonWidget(Widget):
    def __init__(
        self, parent: QWidget, text: str | CBinding[str], action: Callable[[], Any]
    ):
        if isinstance(text, CBinding):
            btn = QPushButton(text.get(), parent)

            text.qt_variable().valueChanged.connect(btn.setText)
        else:
            btn = QPushButton(text, parent)

        btn.clicked.connect(action)

        super().__init__(btn)


class GUILogArea(Widget):
    COLORS = {
        "DEBUG": "dodgerblue",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "orangered",
        "CRITICAL": "magenta",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.text = QTextEdit(parent)
        self.text.setReadOnly(True)

        self.text.setStyleSheet("background-color: black;")

    @threadSafe
    def add_log(
        self,
        level: int,
        message: str,
        end: str = "\n",
        color: str = "black",
    ):
        if self.text is None:
            return

        color_html = color if color in self.COLORS.values() else "white"

        html = f'<span style="color:{color_html};">' f"{message}{end}" f"</span><br/>"

        # self.text.moveCursor(self.text.textCursor().)
        self.text.insertHtml(html)
        self.text.ensureCursorVisible()

        if config.show_errors and level >= logging.ERROR:
            error_message = (": ".join(message.split(": ")[1:])).capitalize()

            QMessageBox.critical(
                None,  # self._widget,
                "Error",
                error_message,
            )
