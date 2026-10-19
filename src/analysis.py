import labpilot.analysis as ana
import labpilot.plots.plots_implementation as plots
from labpilot.GUI.binding import Binding

from src.readers import ExampleStreamer


class ExampleAnalysis(ana.DataAnalysis):
    ### TODO: Set the title of the analysis
    title: str = "Example Analysis"

    def __init__(self) -> None:
        ### TODO: Setup the plots that you need
        self.plot_raw = plots.SimplePlot(
            "example_reader_raw",
            title="Raw data",
            xlabel="time [s]",
            ylabel="Value [...]",
            update_axis=True,
        )
        self.plot_processed = plots.SimplePlot(
            "example_reader_processed",
            title="Processed Data",
            xlabel="time [s]",
            ylabel="Processed Value [...]",
            update_axis=True,
        )

        ### TODO: Register your plots. You must do this before calling `super()__init__()`! If you forget, your plot won't display or you will encounter errors
        self.graphs = [self.plot_raw, self.plot_processed]
        super().__init__()

    ### TODO: Define which readers are used in the analysis. Only define the one you need. It is important that you define it that way!!!
    @ana.reader
    def example_streamer(self) -> ExampleStreamer:
        ...

    def refresh_plots(self):
        ### TODO: Update your plots data with the fresh data from each reader
        data_reader = self.example_streamer().get_data()
        if data_reader is not None:
            self.plot_raw.set_data(data_reader.t, data_reader.raw)
            self.plot_processed.set_data(data_reader.t, data_reader.processed)
