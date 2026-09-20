import numpy as np

from labtools.DataReceiver import StreamDataReader, ProcessedData
from labtools.GUI.binding import Binding


class ExampleData(ProcessedData):
    t: np.ndarray
    raw: np.ndarray
    processed: np.ndarray


class ExampleStreamer(StreamDataReader[ExampleData]):
    ### TODO: Define the name of the reader
    name: str = "Example Streamer"
    ### TODO: Define the directory where the data of the reader will be stored
    dirname: str = "example_streamer"

    def pull_data(self) -> np.ndarray:
        """Implement this data to read values from your instrument.

        Important: The return must be an array with 2 dimensions!
        """
        n_samples = 1  # Adapt if necessary: Number of samples

        # Create a (N, M) array with the raw data you read from your instrument
        raw_data = np.zeros((2, 1))

        # Get the current time steps for the collected samples (if applicable)
        t = self.time_step(n_samples)

        ### TODO: Fill the different columns in your array
        raw_data[0, :] = t
        # raw_data[1, :] = ...

        return raw_data

    def process_data(self, raw_data: np.ndarray) -> ExampleData:
        """Implement this method to process your data and compute the quantities you want

        Note: `raw_data` is an array with 2 dimensions. The first dimension has the same number of elements than the array returned by `pull_data()`, but may have a different number of elements in the second dimension.
        """
        # Declare the object
        data = ExampleData()

        # Remplace each properties with their value
        data.t = raw_data[0, :]
        data.raw = raw_data[1, :]
        data.processed = (
            raw_data[1, :] * 2
        )  ### TODO: Replace with your actual data processing

        return data

    def on_start(self) -> bool:
        """This method is called when the instrument starts being read"""

        # Check the connection: Load informations about the oscilloscope
        if not super().on_start():
            return False

        ### TODO: Configure your instrument before reading its data

        return True

    def on_stop(self):
        """This method is called when the instrument is stopped being read"""
        super().on_stop()

        ### TODO: Configure your instrument when you don't need to read its data anymore
