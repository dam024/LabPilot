from __future__ import annotations
from typing import Iterable, List
import time
import numpy as np

# Add this code in your file if you want the logs to appear in the log area in the window
import labpilot

logger = labpilot.getLogger(__name__)

import labpilot.plots.plot_backend as pb
import labpilot.plots.plots_implementation as plots
import labpilot.GUI.objects as gui_obj
from labpilot.GUI.binding import Binding
import labpilot.analysis as ana
import labpilot.measurement_procedure as mp

from src.analysis import ExampleAnalysis
from src.readers import ExampleStreamer


### TODO: Declare your views. Note: with the given configuration, all views must be declared in this file.
class TestView(ana.View):
    ### TODO: Give a name to the view. It will be displayed on the interface
    name: str = "Example View"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        """This method defines which `DataAnalysis` are shown and which plots are shown"""
        analysis = ExampleAnalysis()

        ### TODO: Indicate which plots are visible
        analysis.plot_raw.show = True
        analysis.plot_processed.show = True

        return [analysis]


class ExampleProcedure(mp.MeasurementProcedure):
    name: str = "Example Procedure"
    dirname: str = "example_procedure"

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
    def test_streamer(self) -> ExampleStreamer:
        ...

    def make_plot(self, figure: pb.PlotBackend):
        figure.make_right_axes()
        figure.legend()

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
