from __future__ import annotations
from typing import Any, Callable, Iterable, List
import random
import PySide6.QtWidgets as qt

from labtools.DataReceiver import (
    LiveDataReader,
    ProcessedData,
    StreamDataReader,
)
import labtools.plots.plot_backend as pb
import labtools.plots.plots_implementation as plots
import labtools.GUI.objects as gui_obj
from labtools.GUI.binding import Binding, CBinding
from labtools import logger
import labtools.analysis as ana
import labtools.measurement_procedure as mp

import numpy as np

# DIRTY

import time


class TestData(ProcessedData):
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray


class TestReader(LiveDataReader[TestData]):
    name: str = "Test Reader"
    dirname: str = "test_reader"

    def pull_data(self) -> np.ndarray:
        time.sleep(0.5)
        mean = 0.1
        std = 0.05
        n_samples = 1000
        errors = np.random.normal(loc=mean, scale=std, size=n_samples)

        x = np.linspace(-5, 5, n_samples)

        y = np.sin(np.pi * x) / (np.pi * x) + errors

        z = np.zeros((2, n_samples))

        z[0, :] = x
        z[1, :] = y

        return z

    def process_data(self, raw_data: np.ndarray) -> TestData:
        data = TestData()

        data.x = raw_data[0, :]
        data.y = raw_data[1, :]

        return data

    def on_stop(self):
        super().on_stop()
        logger.info("Stop test reader...")


class TestStreamer(StreamDataReader):
    name: str = "Test Streamer"
    dirname: str = "stream_reader"

    can_stream_data = False

    @Binding
    def refresh_delay(self) -> float:
        return 0.5

    def __init__(self, *args, **kwargs):
        self.t = 0
        self.n_nan_f1 = 0
        self.n_nan_f2 = 0
        super().__init__(*args, **kwargs)

    def pull_data(self) -> np.ndarray:
        # time.sleep(0.5)
        mean = 0
        std = 0.05

        # Take a different shape for f1 and f2. This is to simulate delay in the data collection
        n_samples_f1 = random.randint(80, 120)
        n_samples_f2 = random.randint(80, 120)
        n_samples = max(n_samples_f1, n_samples_f2)
        errors = np.random.normal(loc=mean, scale=std, size=n_samples)

        dt = 0.5 / 100

        # This is the legit method...
        t = self.time_step(n_samples)
        # Here, we just simulate the fact we don't receive data at the same rate
        # t = np.linspace(self.t, self.t + n_samples * dt, n_samples)

        dt = t[1] - t[0]

        # Remove according time from each generated data to simulate delay
        t_f1 = t[:n_samples_f1]  # - self.n_nan_f1 * dt
        t_f2 = t[:n_samples_f2]  # - self.n_nan_f2 * dt

        f = np.sin(2 * np.pi / 20 * t_f1) + errors[:n_samples_f1]
        f2 = np.cos(2 * np.pi / 20 * t_f2) + errors[:n_samples_f2]

        z = np.zeros((3, n_samples))

        z[0, :] = self.regularize(t, n_samples)
        z[1, :] = self.regularize(f, n_samples)
        z[2, :] = self.regularize(f2, n_samples)

        # Compute number of NaN for delay shift (this is to make the example simulate the real world)
        self.n_nan_f1 += np.sum(np.isnan(z[1, :]))
        self.n_nan_f2 = np.sum(np.isnan(z[2, :]))

        self.t = t[-1]

        return z

    def process_data(self, raw_data: np.ndarray) -> TestData:
        data = TestData()

        data.x = raw_data[0, :]
        data.y = raw_data[1, :]
        data.z = raw_data[2, :]

        return data

    def on_stop(self):
        super().on_stop()
        logger.info("Stop streaming thread...")


class TestAnalysis(ana.DataAnalysis):
    title: str = "Test analysis"

    def __init__(self) -> None:
        # Setup graphs
        self.plot_reader = plots.SimplePlot(
            "test_plot_reader",
            title="Test of plot reader",
            xlabel="time [s]",
            ylabel="Spectrum [$V^2/s$]",
            xlim=(-5.1, 5.1),
            ylim=(-0.5, 1.5),
        )
        self.plot_streamer_ch1 = plots.MaximizationPlot(
            "input_channel_1",
            title="Channel 1",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.CENTERED_AROUND_ZERO,
        )
        self.plot_streamer_ch2 = plots.SimplePlot(
            "input_channel_2",
            title="Channel 2",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
        )
        self.graphs = [self.plot_reader, self.plot_streamer_ch1, self.plot_streamer_ch2]
        super().__init__()

    @ana.reader
    def test_reader(self) -> TestReader:
        ...

    @ana.reader
    def test_streamer(self) -> TestStreamer:
        ...

    @classmethod
    def test_var(cls):
        pass

    @Binding
    def test_binding(cls):
        return "Initial Value"

    def refresh_plots(self):
        # Test data
        test_reader: TestReader = self.test_reader()
        data_reader = test_reader.get_data()
        if data_reader is not None:
            self.plot_reader.set_data(data_reader.x, data_reader.y)

        # stream data
        stream_data = self.test_streamer().get_data()
        if stream_data is not None:
            self.plot_streamer_ch1.set_data(stream_data.x, stream_data.y)
            self.plot_streamer_ch2.set_data(stream_data.x, stream_data.z)


# ana1 = TestAnalysis()
# ana2 = TestAnalysis()
#
## ana1.test_binding  # (TestAnalysis, None)
# TestAnalysis.test_binding(TestAnalysis, None)
#
# print(ana1 is ana2)
# print(ana1.test_binding)
# print(ana2.test_binding)
# print(ana1.test_binding is ana2.test_binding)
# exit()


class Test2ndAnalysis(ana.DataAnalysis):
    title: str = "Test analysis"

    def __init__(self) -> None:
        # Setup graphs
        self.plot_reader = plots.SimplePlot(
            "test_plot_reader_2",
            title="Test of plot reader",
            xlabel="time [s]",
            ylabel="Spectrum [$V^2/s$]",
            xlim=(-5.1, 5.1),
            ylim=(-0.5, 1.5),
        )
        self.plot_streamer_ch2 = plots.SimplePlot(
            "test_ch_2",
            title="Channel 2",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.FROM_ZERO,
        )
        self.graphs = [self.plot_reader, self.plot_streamer_ch2]
        super().__init__()

    @ana.reader
    def test_reader(self) -> TestReader:
        ...

    @ana.reader
    def test_streamer(self) -> TestStreamer:
        ...

    @Binding
    def I(self) -> float:
        return 100.0

    @I.onchange
    def __I(self, value: float):
        """Test"""
        self.set_current(value)

    def get_parameters(
        self, frame: qt.QWidget, view: ana.View | None
    ) -> List[ana.GUIParameter]:
        l: List[ana.GUIParameter] = []

        def make_action(
            method: Callable[[Any], None], variable: CBinding
        ) -> Callable[[], bool]:
            def wrapper():
                method(variable.get())
                return True

            return wrapper

        self.I_parameter = ana.GUIParameter(
            widget=gui_obj.NumericalValueInput(
                frame,
                from_=0,
                to=100,
                value=self.I,
                text="Laser current [mA]:",
                # onchange=make_action(self.set_current, self.I),
            )
        )
        l.append(self.I_parameter)
        l += super().get_parameters(frame, view)
        return l

    def set_current(self, I: float):
        logger.info(f"Got current: {I}")

    def refresh_plots(self):
        # Test data
        data_reader = self.test_reader().get_data()
        if data_reader is not None:
            self.plot_reader.set_data(data_reader.x, data_reader.y)

        # stream data
        stream_data = self.test_streamer().get_data()
        if stream_data is not None:
            self.plot_streamer_ch2.set_data(stream_data.x, stream_data.z)


class TestStreamAnalysis(ana.DataAnalysis):
    title: str = "Test Streamer analysis"

    def __init__(self) -> None:
        # Setup graphs
        self.plot_streamer_ch1 = plots.MaximizationPlot(
            "test_ch_1",
            title="Channel 1",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.CENTERED_AROUND_ZERO,
        )
        self.plot_streamer_ch2 = plots.SimplePlot(
            "test_ch_2",
            title="Channel 2",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
        )
        self.graphs = [self.plot_streamer_ch1, self.plot_streamer_ch2]
        super().__init__()

    @ana.reader
    def test_streamer(self) -> TestStreamer:
        ...

    @Binding
    def I(self) -> float:
        return 100.0

    @I.onchange
    def __I(self, value: float):
        """Test"""
        self.set_current(value)

    def get_parameters(
        self, frame: qt.QWidget, view: ana.View | None
    ) -> List[ana.GUIParameter]:
        l: List[ana.GUIParameter] = []

        def make_action(
            method: Callable[[Any], None], variable: CBinding
        ) -> Callable[[], bool]:
            def wrapper():
                method(variable.get())
                return True

            return wrapper

        self.I_parameter = ana.GUIParameter(
            widget=gui_obj.NumericalValueInput(
                frame,
                from_=0,
                to=100,
                value=self.I,
                text="Laser current [mA]:",
                # onchange=make_action(self.set_current, self.I),
            )
        )
        l.append(self.I_parameter)
        l += super().get_parameters(frame, view)
        return l

    def set_current(self, I: float):
        logger.info(f"Got current: {I}")

    def refresh_plots(self):
        # stream data
        stream_data = self.test_streamer().get_data()
        if stream_data is not None:
            self.plot_streamer_ch1.set_data(stream_data.x, stream_data.y)
            self.plot_streamer_ch2.set_data(stream_data.x, stream_data.z)


class TestView(ana.View):
    name: str = "Reader + ch1"

    @Binding
    def refresh_delay(self) -> float:
        return 1.0

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = TestAnalysis()

        # Controls which graphs are visible
        analysis.plot_reader.show = True
        analysis.plot_streamer_ch1.show = True

        return [analysis]


class Test2View(ana.View):
    name: str = "ch1 + ch2"

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = TestStreamAnalysis()

        # Controls which graphs are visible
        analysis.plot_streamer_ch2.show = True
        analysis.plot_streamer_ch1.show = True

        return [analysis]


class Test3View(ana.View):
    name: str = "with_param"

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = Test2ndAnalysis()

        # Controls which graphs are visible
        analysis.plot_streamer_ch2.show = True
        analysis.plot_reader.show = True

        return [analysis]


class InsertionLoss(mp.MeasurementProcedure):
    name: str = "Insertion Loss"
    title: str = "Measurement of Insertion Loss"
    dirname: str = "insertion_loss"

    def __init__(self) -> None:
        # Creates the plot

        self.plot_ratio = plots.GeneralPlot(
            name="plot_ratio",
            prepare_plot=self.make_plot,
            udpate_data=self.update_plot_data,
        )
        self.plot_ratio.show = True
        self.graphs = [self.plot_ratio]
        super().__init__()

    @ana.reader
    def test_streamer(self) -> TestStreamer:
        ...

    def make_plot(self, figure: pb.PlotBackend):
        figure.make_right_axes()

        self.line_power_D1 = figure.plot([], [], color="cyan", label="Power in D1")
        self.line_power_D2 = figure.plot([], [], color="b", label="Power in D2")
        self.line_ratio = figure.plot([], [], color="r", label="r", right_axis=True)

        figure.set_title("Insertion Loss")
        figure.set_xlabel("I [mA]")
        figure.set_ylabel("P [mW]", color="b")
        figure.set_yscale("log")
        figure.tick_params(axis="y", labelcolor="b")
        figure.set_ylabel_right("ratio", color="r")
        figure.tick_params(axis="y", labelcolor="r", right_axis=True)

        figure.grid(right_axis=True)
        figure.grid(axis="x")

    def get_analysis(self) -> List[ana.DataAnalysis]:
        self.plot_ratio.show = True
        return [self]

    def refresh_plots(self):
        data = self.get_procedure_data()
        if data is not None:
            self.plot_ratio.set_data(data)

    def execute(self):
        """Procedure to characterize the beam splitter"""
        currents = np.arange(99) + 1
        data = np.zeros((5, len(currents)))

        for i in range(len(currents)):
            I = currents[i]
            logger.info(f"Current: {I}mA")

            # Wait until actualization
            time.sleep(0.5)

            # Measure data
            T = 25
            D1_raw = I
            D2_raw = 9 * I

            data[0, i] = I
            data[1, i] = D1_raw
            data[2, i] = D2_raw
            data[3, i] = T
            data[4, i] = self.ratio(D1_raw, D2_raw)

            # Update data for live plotting
            self.log_data(data, i)

        return data

    def ratio(
        self, P1: float | np.ndarray, P2: float | np.ndarray
    ) -> float | np.ndarray:
        return P1 / (P1 + P2)

    def update_plot_data(self, data: plots.GeneralData) -> Iterable[pb.Line | pb.Text]:
        # Generates the plots
        I = data.data[0, :]
        D1_raw = data.data[1, :]
        D2_raw = data.data[2, :]
        T = data.data[3, :]
        ratio = data.data[4, :]

        self.line_power_D1.set_data(I, D1_raw)
        self.line_power_D2.set_data(I, D2_raw)
        self.line_ratio.set_data(I, ratio)

        return [self.line_power_D1, self.line_power_D2, self.line_ratio]
