from __future__ import annotations
from abc import abstractmethod
from typing import TYPE_CHECKING, List, Tuple, Generic, TypeVar, Union
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget
import numpy as np
from labtools import config, globalState, logger
import os
import time
import threading
from pathlib import Path
import queue
import enum
import shutil
import traceback
from dataclasses import dataclass, fields
import cython

import cython.cimports.labtools.GUI.parameters as params
import labtools.GUI.parameters as params
from labtools.GUI.binding import Binding, CBinding, Status
import labtools.GUI.objects as gui_obj

if TYPE_CHECKING:
    from labtools.analysis import View


class ReaderStatus(enum.StrEnum):
    RUNNING = "green"
    NOT_RUNNING = "orange"
    TRANSITION = "yellow"
    ERROR = "red"


class NoDataError(Exception):
    """Exception raised when no data is available for a reader."""

    pass


class ReaderImplementationError(Exception):
    """Exception raised when a reader implementation is incorrect."""

    pass


@dataclass(init=False)
class ProcessedData:
    """Base class for processed data objects. Subclasses should implement this for their specific data types."""

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        dataclass(cls, init=False)

    def to_numpy(self) -> np.ndarray:
        """Converts the current object to a numpy array where each user-defined property becomes a column.

        Returns:
            np.ndarray: 2D array with shape (n_rows, n_fields) where each column corresponds to a field.
                      Returns empty array if no fields are defined.
        """
        # Get field names and values from dataclass
        field_values = [getattr(self, f.name) for f in fields(self)]

        # Convert each field to numpy array
        arrays = [np.array(v) for v in field_values]

        # Stack arrays as columns
        if len(arrays) == 0:
            return np.array([])

        return np.vstack(arrays)


T = TypeVar("T", bound=ProcessedData)


@cython.cclass
class Reader(params.GUIParametrable):
    # class LiveDataReader(params.GUIParametrable):

    _name = cython.declare(cython.unicode, visibility="public")
    _dirname = cython.declare(
        cython.unicode, visibility="public"
    )  #: str  # cython.unicode
    _refresh_delay = cython.declare(
        cython.double, visibility="public"
    )  #: float | Binding[float]
    # ignore: bool = False
    # This property indicates if all arrays that are encountered must be saved. If False, only the latest one will be saved (this is information for the global_background_thread)
    # save_all_arrays: bool = False

    # Indicates if the reader can stream data during replay
    _can_stream_data = cython.declare(cython.bint, visibility="public")

    def __cinit__(self):
        self._can_stream_data = True

    def __init__(self):
        """Initialize the LiveDataReader.

        Args:
            refresh_delay (float, optional): Time to wait at the end of the refresh loop before rerunning it.
                Units: seconds. Default: 0.0
        """
        # self._check_for_property("name", str)

        # self.title = self._name

        # self._check_for_property("dirname", str)

        self._stopped = False  # Indicates if the read loop must be stopped
        # self._set_if_not_defined("refresh_delay", refresh_delay)
        self.queue = queue.Queue[T]()
        self.save_queue = queue.Queue[
            Tuple[np.ndarray, str, bool]
        ]()  # This is the queue that will remember all the data that must be saved for the current reader
        self.latest_data: T | None = None
        self.recording_save_index = 0
        super().__init__()

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    @property
    def dev_name(self) -> str:
        """Developer name of the reader. This property returns the dirname attribute."""
        return self._dirname

    @property
    def has_data(self) -> bool:
        """
        Check if the current reader has already some data loaded.

        Returns:
            bool: True if the reader has data (either in latest_data or in the queue), False otherwise.
        """
        return self.latest_data is not None or not self.queue.empty()

    def start_reader(self) -> bool:
        """
        Execute the on_start procedure and handle different cases.

        In simulation mode, always returns True. In real mode, checks on_start() and handles errors.

        Returns:
            bool: True if initialization succeeded, False if it failed.
        """
        if not config.simulation:
            self.status = ReaderStatus.TRANSITION
            if not self.on_start():
                logger.warning(
                    f"Initialization of data collection for `{self.__class__.__name__}` failed. Data collection loop did not start"
                )
                self.on_stop()
                self.status = ReaderStatus.ERROR
                return False
            else:
                self.status = ReaderStatus.RUNNING
                return True

        return True

    def stop_reader(self):
        """
        Execute the on_stop procedure and handle different cases.

        Always stops the reader regardless of simulation mode.

        In real mode, also updates status to NOT_RUNNING.
        """
        if not config.simulation:
            self.status = ReaderStatus.TRANSITION
            logger.debug(f"Calling `on_stop` for {self.__class__.__name__}")
            self.on_stop()
            self.status = ReaderStatus.NOT_RUNNING

    def read_loop(self, stop_event: threading.Event):
        """
        Reading loop that continuously reads data. Must be executed in a background thread!

        The loop continues until the stop_event is set. It handles both simulation
        and real data acquisition modes.

        Args:
            stop_event: Threading.Event used to signal the loop to stop.
        """

        if not self.start_reader():
            return

        try:
            while not stop_event.is_set():
                self._data_collection_step()

                # Wait before the next loop
                if config.simulation:
                    stop_event.wait(0.3)
                else:
                    delay = self._refresh_delay

                    # Check if I need to use the refresh_delay of the view (if defined, overcome the one of the reader)
                    if (
                        self.window is not None
                        and self.window.active_view.refresh_delay is not None
                    ):
                        delay = self.window.active_view.refresh_delay

                    # Wait for the appropriate amount of time
                    if isinstance(delay, CBinding):
                        stop_event.wait(delay.get())
                    else:
                        stop_event.wait(delay)
        except Exception as e:
            self.status = ReaderStatus.ERROR
            # print(e)
            logger.error(e)
            traceback.print_exception(e)
        finally:
            self.stop_reader()

    def _data_collection_step(self):
        """
        Execute a step of data collection.

        A step is composed of the following substeps:
            1. Data pulling: Call `pull_data` to take a measurement
            2. Data saving: Save the data if we are recording
            3. Data aggregation: Integrate the newly collected data into the previous ones
            4. Data processing: Process the raw data to compute the desired quantities
            5. Queue appending: Append the current data to the queue of data
            6. Optional wait: Optionally wait for some time before taking a new measurement
        """
        # t0 = time.perf_counter()
        if config.simulation:
            # Load data from saved files
            data = self._load_file()

            if data is None:
                raise FileNotFoundError(f"Couldn't open file...")

            data_aggregated = self.aggregate_data(data)

        else:
            # Pull the data
            data = self.pull_data()

            if data is None or data.shape[-1] == 0:
                return

            # Save all data
            if globalState.recording:
                # self.save_all_arrays = True
                self.save_data(
                    data,
                    os.path.join(globalState.recording_subfolder, self._dirname),
                    f"output_{self.recording_save_index}.npy",
                    force_save=True,
                )
                self.recording_save_index += 1
            else:
                # self.save_all_arrays = False
                self.recording_save_index = 0  # Reset the recording count...

            # Internal pre-processing
            data_aggregated = self.aggregate_data(data)

            # Save the new raw data
            # ts0 = time.perf_counter()
            if not globalState.recording:
                self.save_data(data_aggregated)
            # ts1 = time.perf_counter()
            # logger.debug(f"Elapsed time for saving: {ts1-ts0}")

        # Process the data
        processed_data = self.process_data(data_aggregated)

        # Add data to the Queue
        self.queue.put(item=processed_data)

        # t1 = time.perf_counter()
        # logger.debug(f"Total elapsed time for loop: {t1-t0}")

    def get_data(self) -> T | None:
        """
        Get the latest collected data.

        This method is supposed to be called from the main thread! It retrieves
        the latest data from the queue and stores it in latest_data.

        Returns:
            T | None: The latest collected data, or None if no data was collected since the previous call.
        """
        data: T | None = self.latest_data
        while not self.queue.empty():
            data = self.queue.get_nowait()

        self.latest_data = data
        return data

    def aggregate_data(
        self, raw_data: np.ndarray, ignore_max_length: bool = False
    ) -> np.ndarray:
        """
        Assemble all the data if needed.

        Subclasses can override this method to implement custom aggregation logic.

        Args:
            raw_data: The raw data to aggregate.
            ignore_max_length: If True, ignore the max length constraint.

        Returns:
            np.ndarray: The aggregated data.
        """
        return raw_data

    def clear(self):
        """
        Clear all the data saved for the current data reader.

        Empties the queue and sets latest_data to None.
        """
        while not self.queue.empty():
            data = self.queue.get_nowait()

        self.latest_data = None

    @abstractmethod
    def process_data(self, raw_data: np.ndarray) -> T:
        """
        Process the raw data into the desired format.

        This abstract method must be implemented by subclasses. It is responsible
        for generating a ProcessedData object from the raw data.

        Note:
            The raw_data has the same structure as the one returned by the `pull_data()` method.

        Important:
            This method will be executed on a background thread.

        Args:
            raw_data: The raw data to process.

        Returns:
            T: The processed data object.
        """

    @property
    def is_running(self) -> bool:
        """
        Check if the thread of the current `LiveDataReader` is running.

        Returns:
            bool: True if the collector thread is alive, False otherwise.
        """
        return hasattr(self, "collector") and self.collector.is_alive()

    @Status
    def status(cls) -> ReaderStatus:
        """
        Get the status of the current reader.

        Returns:
            ReaderStatus: The current status (NOT_RUNNING by default).
        """
        return ReaderStatus.NOT_RUNNING

    @status.onchange
    def __status(self, value: ReaderStatus):
        """
        Handle status changes.

        If a status circle has been defined, update its state

        Args:
            value: The new status value.
        """
        if hasattr(self, "status_circle"):
            self._set_status_color(value)

    def get_status_interface(self, parent: QWidget) -> QWidget:
        """
        Create a generic status interface that presents the user the state of a reader.

        Everything is handled automatically! The interface includes a status
        circle and a label with the reader name.

        Args:
            parent: The parent widget.

        Returns:
            QWidget: The status interface widget.
        """

        frame = QFrame(parent)

        layout = QHBoxLayout(frame)
        frame.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

        self.radius = 5

        self.status_circle = QLabel()
        self.status_circle.setFixedSize(
            2 * self.radius + 1,
            2 * self.radius + 1,
        )

        self._set_status_color(ReaderStatus.NOT_RUNNING)

        layout.addWidget(self.status_circle)

        label = QLabel(self._name)
        layout.addWidget(label, 1)  # Takes remaining horizontal space

        return frame

    def _set_status_color(self, color: ReaderStatus):
        """
        Set the status circle color based on the reader status.

        Args:
            color: The ReaderStatus enum value to use for the color.
        """
        self.status_circle.setStyleSheet(
            f"""
            background-color: {color.value};
            border-radius: {self.radius}px;
        """
        )

    def start(self):
        """
        Start collecting and processing data.

        Starts the collection thread. If you have used `self.pause()`, you must use
        `self.resume()` to restart the thread!

        Returns:
            Tuple: (collector, stop_event) tuple for external control.
        """
        # Start the threads
        self.resume()

        return (self.collector, self.stop_event)

    def pause(self):
        """
        Pause the current data collection thread.

        Sets the stop_event to signal the thread to pause.
        """
        # logger.debug(f"Pausing `{self.__class__.__name__}`...")
        if hasattr(self, "stop_event"):
            self.stop_event.set()

        # logger.debug(f"Paused `{self.__class__.__name__}`!")

    def resume(self):
        """
        Resume the collection of data from the threads.

        Creates and starts a new collector thread if not already running.
        Raises RuntimeError if called while the thread is already running.
        """
        # logger.debug(f"Resume `{self.__class__.__name__}`")
        # Create the
        if self.is_running:
            raise RuntimeError(
                f"You tried to resume a thread that was already running in {self.__class__.__name__}"
            )
        self.stop_event = threading.Event()

        self.collector = threading.Thread(
            target=self.read_loop, args=(self.stop_event,)
        )

        self.collector.start()

    @abstractmethod
    def pull_data(self) -> np.ndarray | None:
        """
        Pull the data from the acquisition source.

        This abstract method must be implemented by subclasses. It pulls
        the new raw data and returns them as a well-structured numpy array.

        Note:
            This method assumes by default the array to be 2-D. An error will be
            thrown if this is not the case! If you need to work with arrays having
            different dimensions, please subclass the `aggregate_data` and implement
            your own data aggregation. If your class is NOT a subclass of `StreamDataReader`,
            you can ignore this note.

        Returns:
            np.ndarray | None: The raw data as a 2D numpy array, or None if no data was pulled.
        """
        pass

    def on_start(self) -> bool:
        """
        Execute initialization when the thread is started.

        This is when the instrument must be started. Override this method in
        subclasses for custom initialization logic.

        Note:
            This code is executed in a background thread.

        Returns:
            bool: True if initialization succeeded, False if it failed.
        """
        logger.debug(f"Starting thread `{self.__class__.__name__}`")
        return True

    @abstractmethod
    def on_stop(self):
        """
        Execute cleanup when the thread is stopped.

        This is important to undergo any cleaning and shut down all instruments
        managed by this thread. Override this method in subclasses for custom
        cleanup logic.

        Note:
            This code is executed in a background thread.
        """
        logger.debug(f"Stopping thread `{self.__class__.__name__}`")

    def save_data(
        self,
        data: np.ndarray,
        subfolder: str | None = None,
        filename: str | None = None,
        force_save: bool = False,
    ):
        """
        Save the data to a file.

        Since saving takes a long time, this task is delegated to the global queue.

        Args:
            data: The data array to save.
            subfolder: Optional subfolder where to save the data.
            filename: Optional name of the file to save the data in.
                If None, uses dirname + ".npy" as the filename.
            force_save: If True, forces the data to be saved. If False, the file
                will be saved only if it is last in the queue.

        Note:
            If the `force_save` parameter is causing issue, I can probably go
            back to a sort of 'save_all_arrays' (CMD+F) solution. But as for now
            (05.08.2026), the data are saved only during recording (force_save=True)
            or the latest aggregated data when no recording (force_save=False), so
            it doesn't cause any issue.
        """
        output_dir = (
            config.output_dir_data
            if subfolder is None
            else os.path.join(config.output_dir_data, subfolder)
        )
        if filename is None:
            path = os.path.join(output_dir, self._dirname + ".npy")
        else:
            path = os.path.join(output_dir, filename)

        # Since saving takes a long time, this task is delegate to the global queue
        self.save_queue.put(item=(data, path, force_save))

    def _load_file(self, path: str | None = None) -> np.ndarray | None:
        """
        Load data from a file.

        Args:
            path: Optional path to load data from. If None, loads from the
                configured output directory.

        Returns:
            np.ndarray | None: The loaded data, or None if the file doesn't exist.
        """
        if path is not None:
            if not os.path.isfile(path):
                filename = os.path.join(path, self._dirname + ".npy")
            else:
                filename = path
        else:
            filename = os.path.join(
                config.output_dir_data,
                globalState.reading_recording_subfolder or "",
                self._dirname + ".npy",
            )
            # print(filename)

        if not os.path.exists(filename):
            logger.warning(
                f"No data found for `{self.__class__.__name__}` at path {filename}"
            )
            return None
        # Load the data
        path_var = Path(filename)
        data = np.load(path_var)

        return data

    def load_data(self, path: str | None = None) -> T | None:
        """
        Load all the data for a recording.

        Loads the saved data, processes it, and adds it to the queue for
        smooth integration.

        Args:
            path: Optional path to load data from. If None, uses the default path.

        Returns:
            T | None: The processed data, or None if no data was loaded.
        """
        data = self._load_file(path)
        if data is None:
            return None
        logger.debug(f"Data size [{self.__class__.__name__}]: {data.shape}")

        # Process the data
        processed_data = self.process_data(data)

        # Add the data to the queue for smooth integration
        self.queue.put(item=processed_data)

        return processed_data


class LiveDataReader(Reader):
    """
    Abstract base class for live data readers.

    This class manages the lifecycle of data acquisition, including:
    - Starting and stopping data collection threads
    - Pulling raw data from sources
    - Aggregating and processing data
    - Saving data to files
    - Managing data queues for smooth integration

    Subclasses must implement the abstract methods:
        - `pull_data()`: Pulls raw data from the acquisition source
        - `process_data()`: Processes raw data into the desired format
        - `on_stop()`: Cleans up resources when stopping

    Attributes:
        name (str): Identifier for the data reader
        dirname (str): Directory name where data is saved
        refresh_delay (float | Binding[float]): Time to wait at the end of the refresh loop
    """

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def dirname(self) -> str:
        return self._dirname

    @dirname.setter
    def dirname(self, value: str):
        self._dirname = value

    @Binding
    def refresh_delay(self) -> float:
        return 0.0

    @refresh_delay.onchange
    def __refresh_delay(self, value: float):
        self._refresh_delay = value

    # ignore: bool = False
    # This property indicates if all arrays that are encountered must be saved. If False, only the latest one will be saved (this is information for the global_background_thread)
    # save_all_arrays: bool = False

    # Indicates if the reader can stream data during replay
    @property
    def can_stream_data(self) -> bool:
        return self._can_stream_data

    @can_stream_data.setter
    def can_stream_data(self, value: bool):
        self._can_stream_data = value

    def __init__(self, refresh_delay: float = 0.0):
        self._check_for_property("name", str)

        self.title = self.name

        self._check_for_property("dirname", str)

        self._stopped = False  # Indicates if the read loop must be stopped
        # self._set_if_not_defined("refresh_delay", refresh_delay)
        super().__init__()
        self.refresh_delay = refresh_delay

    def get_parameters(
        self, frame: QWidget, view: View | None
    ) -> List[params.GUIParameter]:
        """
        Get GUI parameters for the data reader.

        Creates a slider for refresh_delay if it's not bound in the view.

        Args:
            frame: The parent frame widget.
            view: The active view, if available.

        Returns:
            List[params.GUIParameter]: List of GUI parameters to display.
        """
        l: List[params.GUIParameter] = []
        # print(f"{view.__class__.__name__}, {self.__class__.__name__}: {"refresh_delay" in view._bindings}, {"refresh_delay" in self._bindings}", self.refresh_delay.get())
        if (
            view is not None
            and "refresh_delay" not in view._bindings
            and "refresh_delay" in self._bindings
        ):
            slider_delay = gui_obj.NumericalValueInput(
                frame,
                from_=0.0,
                to=100.0,
                value=self.refresh_delay,
                text="Delay between samples [s]:",
                increment=0.1,
            )

            l.append(params.GUIParameter(slider_delay))

        return l


class StreamDataReader(LiveDataReader):
    """
    Subclass of LiveDataReader for streaming data acquisition.

    This class adds support for:
    - Maximum number of rows to store
    - Stream data aggregation with NaN handling
    - Time step computation for streaming data
    - Data regularization for multi-channel streams
    """

    max_rows: int

    class DataAggregationMethod(enum.IntEnum):
        """
        Describes how NaN should be treated when data arrive with an irregular shape.

        Attributes:
            LeaveNaN (int): Indicates that NaN values must be treated as any legitimate value.
                Therefore, no specific treatment is performed on the data.
            ReplaceNaN (int): Indicates that NaN values must be overridden with actual values.
        """

        LeaveNaN = 1
        ReplaceNaN = 2

    def __init__(self, *args, max_rows: int = 1000, **kwargs):
        """
        Initialize the StreamDataReader.

        Args:
            *args: Additional positional arguments passed to LiveDataReader.__init__.
            max_rows: Maximum number of rows to store in the stream. Default: 1000.
            **kwargs: Additional keyword arguments passed to LiveDataReader.__init__.
        """
        self._set_if_not_defined("max_rows", max_rows)
        self.stream_save_i = 0
        self.data: np.ndarray = np.array([])
        super().__init__(*args, **kwargs)

    def clear(self):
        """
        Clear all the data saved for the current data reader.

        Calls the parent clear() method and resets stream-specific counters and data.
        """
        super().clear()
        self.stream_save_i = 0
        self.data = np.array([])

    def on_start(self) -> bool:
        """
        Initialize stream data structures when starting.

        Calls the parent on_start() and resets stream-specific state.

        Returns:
            bool: True if initialization succeeded.
        """
        self._last_stopped_time = 0
        self.data: np.ndarray = np.array([])
        self._time = time.perf_counter()
        return super().on_start()

    def nan_aggregation_policy(self, axis: int) -> DataAggregationMethod:
        """
        Get the NaN aggregation policy for the given axis.

        This is a placeholder that raises NotImplementedError. Subclasses should
        override this method for custom NaN handling policies.

        Args:
            axis: The axis along which to apply the aggregation policy.

        Returns:
            DataAggregationMethod: The policy to use for NaN handling.

        Note:
            This feature is not available in the base implementation.
        """
        raise NotImplementedError("This feature is not available")
        return StreamDataReader.DataAggregationMethod.LeaveNaN

    def aggregate_data(
        self, raw_data: np.ndarray, ignore_max_length: bool = False
    ) -> np.ndarray:
        """
        Aggregate the data together, handling stream data with NaN values.

        Note:
            It is assumed that the first dimension represents the different values
            and the 2nd the time evolution of each value. Therefore, the first
            dimension must always be the same size during aggregation!

        Args:
            raw_data: The raw data to aggregate.
            ignore_max_length: If True, ignore the max_length constraint.

        Returns:
            np.ndarray: The aggregated data.

        Raises:
            ReaderImplementationError: If raw_data is not 2-dimensional.
        """
        if len(raw_data.shape) != 2:
            raise ReaderImplementationError(
                f"Your implementation of `{self.__class__.__name__}.pull_data()` return an array with {len(raw_data.shape)} dimensions. Only 2 dimensions are allowed. If you need other number of dimensions, please implement your own {self.__class__.__name__}.aggregate_data`"
            )
        if self.data.shape == () or self.data.shape[0] == 0:
            d = raw_data
        else:
            d = np.append(self.data, raw_data, axis=1)

        length = d.shape[-1]

        # Reduce the lengths of the stream to avoid having too many data accumulating
        if ignore_max_length:
            self.data = d
        else:
            self.data = d[:, max(0, length - self.max_rows) :]
        return self.data

    @classmethod
    def nan_aggregation(
        cls, data: np.ndarray, raw_data: np.ndarray, max_row: int
    ) -> np.ndarray:
        """
        Aggregate data with NaN handling.

        This class method aggregates existing data with new data, filling gaps
        with NaN values where necessary.

        Args:
            data: The existing data array.
            raw_data: The new raw data to aggregate.
            max_row: The maximum number of rows.

        Returns:
            np.ndarray: The aggregated data with NaN handling applied.
        """
        d = np.full(max_row, np.nan)

        # Number of NaN values
        nb_nan = np.sum(np.isnan(data))

        # From where we keep the data
        data_from = data.shape[-1] + raw_data.shape[-1] - nb_nan - max_row

        # Until where we fill the existing data in the new array
        d_to_data = data.shape[0] - max(data_from, 0)

        # From where we add the new data
        d_from_raw = max(max_row - raw_data.shape[0] + min(0, data_from), 0)

        # Truncation of the new data, if necessary
        from_raw = max(0, raw_data.shape[0] - max_row)

        # Make the shift
        if d_to_data > 0:
            d[:d_to_data] = data[max(data_from, 0) :]
        d[d_from_raw : None if data_from > 0 else data_from] = raw_data[from_raw:]
        return d

    def _get_stream_path(self, i: int) -> str:
        """
        Get the file path for a specific stream file.

        Args:
            i: The stream index.

        Returns:
            str: The path to the stream file.
        """
        path = os.path.join(
            self.dirname,
            f"output_{i}.npy",
        )
        return path

    def _load_file(self, path: str | None = None) -> np.ndarray | None:
        """
        Load data from a file, handling stream data in simulation mode.

        If no file is provided and we are in simulation mode, loads from the
        logged stream files.

        Args:
            path: Optional path to load data from. If None, uses the default path.

        Returns:
            np.ndarray | None: The loaded data, or None if the file doesn't exist.
        """
        # If no file is provided, load the logged by stream
        if path is None and config.simulation:
            # logger.debug(f"Loading: {self.stream_save_i}")
            path = self._get_stream_path(self.stream_save_i)

            if not os.path.exists(
                os.path.join(
                    config.output_dir_data,
                    globalState.reading_recording_subfolder or "",
                    path,
                )
            ):
                if self.stream_save_i > 0:
                    self.stream_save_i = 0
                    path = self._get_stream_path(self.stream_save_i)
                    self.clear()
                else:
                    path = None
            else:
                self.stream_save_i += 1

            # Correct path...
            if path is not None:
                path = os.path.join(
                    config.output_dir_data,
                    globalState.reading_recording_subfolder or "",
                    path,
                )

        data = super()._load_file(path)

        # if config.simulation and data is not None:
        # logger.debug(
        #    f"Data info: {data.shape}, {np.nanmax(data[1:, :])}, {np.nanargmax(data[1:,:])}"
        # )
        return data

    def time_step(self, nb_elements: int) -> np.ndarray:
        """
        Compute the time axis since last data collection.

        Args:
            nb_elements: Number of elements to generate in the time array.

        Returns:
            np.ndarray: Time array from last stopped time to current time.
        """
        current_t = time.perf_counter()
        # print(current_t)
        dt = current_t - self._time
        self._time = current_t
        t = self._last_stopped_time
        self._last_stopped_time = self._last_stopped_time + dt
        return np.linspace(t, self._last_stopped_time, nb_elements)

    def regularize(self, array: np.ndarray, length: int) -> np.ndarray:
        """
        Complete the given array with NaN values until it has the correct length.

        The goal of this method is to take support data streams having multiple
        channels where data do not have the same size. In this case, NaN values
        will complete the missing values. Then, during data aggregation, the NaN
        values will be replaced by the actual values.

        Args:
            array: The array to regularize.
            length: The desired length of the output array.

        Returns:
            np.ndarray: The regularized array with NaN padding.

        Raises:
            RuntimeError: If the array is larger than the desired length or if the array doesn't have 1 dimensions.
        """
        if len(array.shape) != 1:
            raise RuntimeError(
                f"Regularization is only possible for 1-D array. Obtained array with shape {array.shape}"
            )
        if array.shape[0] > length:
            raise RuntimeError(
                f"Regularization is impossible for an array of size {array.shape} and length {length}. Make sure the desired length is >= array.shape[0]"
            )

        out = np.full((length), np.nan)
        out[: array.shape[0]] = array

        return out

    def load_data(self, path: str | None = None) -> T | None:
        """
        Load all the data for a recording (stream reader specific).

        Loads stream data files and aggregates them. Saves the aggregated data
        if streaming is not enabled.

        Args:
            path: Path to the recording folder if different from the one in the configuration. If None, uses the default path.

        Returns:
            T | None: The processed data, or None if no data was loaded.

        Raises:
            NoDataError: If no data is available for the reader.
        """
        logger.info(f"Start loading data for `{self.__class__.__name__}`")

        # Load the files
        if path is None:
            base_path = os.path.join(
                config.output_dir_data, globalState.reading_recording_subfolder or ""
            )
        else:
            base_path = path

        all_data_path = os.path.join(base_path, self.dirname, "data.npy")

        if os.path.exists(all_data_path):
            data_aggregated = np.load(all_data_path)
        else:
            previous_stream_i = self.stream_save_i
            data_aggregated = np.array([])
            while previous_stream_i <= self.stream_save_i:
                previous_stream_i = self.stream_save_i
                # print(f"stream: {previous_stream_i}")

                data = self._load_file()
                if previous_stream_i >= self.stream_save_i:
                    # Avoids taking twice the first batch...
                    break
                if data is None:
                    return None
                logger.debug(f"Data size [{self.__class__.__name__}]: {data.shape}")

                data_aggregated = self.aggregate_data(data, True)

            if "data_aggregated" not in vars() or data_aggregated.shape == (0,):
                raise NoDataError(
                    f"No data is available in for the `DataReader`: `{self.__class__.__name__}` (path: {os.path.dirname(all_data_path)})"
                )

            # Save the aggregated data if necessary
            if not self.can_stream_data:
                dir_path = os.path.join(
                    base_path,
                    self.dirname,
                )
                try:
                    # os.removedirs(dir_path)
                    shutil.rmtree(dir_path, ignore_errors=False)
                except Exception as e:
                    # print(e)
                    logger.error(e)
                    traceback.print_exception(e)
                finally:
                    os.makedirs(dir_path, exist_ok=True)
                    np.save(all_data_path, data_aggregated)

        # Process the data
        processed_data = self.process_data(data_aggregated)

        # Add the data to the queue for smooth integration
        self.queue.put(item=processed_data)

        return processed_data
