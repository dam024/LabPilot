from typing import List

from PySide6.QtWidgets import QWidget
import numpy as np

import labpilot

logger = labpilot.getLogger(__name__)
from labpilot.analysis import View
from labpilot.DataReceiver import StreamDataReader, ProcessedData
from labpilot.GUI.binding import Binding
import labpilot.GUI.parameters as params
import labpilot.GUI.objects as gui_obj


class ExampleData(ProcessedData):
    t: np.ndarray
    raw: np.ndarray
    processed: np.ndarray


class ExampleStreamer(StreamDataReader[ExampleData]):
    ### TODO: Define the name of the reader
    name: str = "Example Streamer"
    ### TODO: Define the directory where the data of the reader will be stored
    dirname: str = "example_streamer"

    # You can set a delay between each sample. This delay can be controlled at the level of the Reader or at the level of the View! If you control it at the level of the View, this one will be ignored
    refresh_delay = 1.0

    @Binding
    # Important: You must define the return type of the Binding for optimal integration!
    def value(cls) -> float:
        """
        Bindings are a core part of LabPilot. Their goal is to control a parameter of your experiments. Anytime you need to control a parameter, define a method with the `@Binding´ decorator. They have the following properties:

            - Persistance: The value of the Binding is saved in the local storage and restituted if the application is restarted
            - Logged during recordings: When you record a measurement, a file `info.json` is created in the recording folder. This file will contain the value of this parameter and it will be restituted if you load the data from this recording.
                Remark: only the last value will be saved. It is not expected that you change it during a recording...

        Value management:
        ```python
        # Set the value of the Binding:
        self.value = ...

        # Get the value of the Binding:
        _ = self.value.get()
        ```
        """
        # The value that you return is the default value. It is used ONLY the first time you start the application or if you delete the local storage.
        return 0.0

    @value.onchange
    def __value(self, value: float):
        """You can change also observe a change of value of the Binding using the decorator `@<binding_name>.onchange`.

        Note:
            The `onchange` mechanism has some limitations. It is strongly advised that you DON'T change some instance attributes. Bindings are stored as a class variable, not an instance. If you absolutely need this, it is recommended to use the `@State` decorator. It works the same way as ´@Binding´, except that it is not persistent. The reason for this is that the `onchange` function is called for only ONE single instance of the class hosting the Binding.
        """
        logger.info(f"Binding has changed value: {value:.1f}")

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
        raw_data[1, :] = self.value.get()

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

    def get_parameters(
        self, frame: QWidget, view: View | None
    ) -> List[params.GUIParameter]:
        """Override this method to define some controls in the application parameters."""
        parameters: List[params.GUIParameter] = []

        # Example: Add a parameter for the `self.value` Binding. Use NumericalValueInput for float and int values
        parameters.append(
            params.GUIParameter(
                widget=gui_obj.NumericalValueInput(
                    frame,
                    from_=0.0,  # Lowest value allowed in the interface
                    to=5.0,  # Highest value allowed in the interface
                    value=self.value,  # Binding linked to the Widget
                    text="Value: ",  # Label placed before the widget
                    increment=0.1,  # Allowed values will increment by 0.1. This is mostly to make the interface nicer to use
                )
            )
        )

        # Don't forget to append the parameters defined by LabPilot!
        parameters += super().get_parameters(frame, view)

        return parameters

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
