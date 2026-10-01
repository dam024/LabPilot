import abc
import enum
from typing_extensions import disjoint_base
import labtools.GUI.parameters as params
import numpy as np
import threading
from PySide6.QtWidgets import QWidget
from _typeshed import Incomplete
from abc import abstractmethod
from dataclasses import dataclass
from labtools import config as config, globalState as globalState, logger as logger
from labtools.GUI.binding import (
    Binding as Binding,
    CBinding as CBinding,
    Status as Status,
)
from labtools.analysis import View as View
from typing import Generic, TypeVar, List


class ReaderStatus(enum.StrEnum):
    RUNNING = "green"
    NOT_RUNNING = "orange"
    TRANSITION = "yellow"
    ERROR = "red"


class NoDataError(Exception):
    ...


class ReaderImplementationError(Exception):
    ...


@dataclass(init=False)
class ProcessedData:
    def __init_subclass__(cls) -> None:
        ...

    def to_numpy(self) -> np.ndarray:
        ...


T = TypeVar("T", bound=ProcessedData)


@disjoint_base
class Reader(params.GUIParametrable, Generic[T]):
    # name: str
    # dirname: str
    # refresh_delay: Binding[float]
    # can_stream_data: bool
    # title: Incomplete
    # queue: Incomplete
    # save_queue: Incomplete
    # latest_data: T | None
    # recording_save_index: int

    def __cinit__(self):
        ...

    def __init__(self) -> None:
        ...

    @classmethod
    def __class_getitem__(cls, item):
        ...

    @property
    def dev_name(self) -> str:
        ...

    @property
    def has_data(self) -> bool:
        ...

    def start_reader(self) -> bool:
        ...

    def stop_reader(self) -> None:
        ...

    def read_loop(self, stop_event: threading.Event):
        ...

    def get_data(self) -> T | None:
        ...

    def aggregate_data(
        self, raw_data: np.ndarray, ignore_max_length: bool = False
    ) -> np.ndarray:
        ...

    def clear(self) -> None:
        ...

    @abstractmethod
    def process_data(self, raw_data: np.ndarray) -> T:
        ...

    @property
    def is_running(self) -> bool:
        ...

    @Status
    def status(cls) -> ReaderStatus:
        ...

    radius: int
    status_circle: Incomplete

    def get_status_interface(self, parent: QWidget) -> QWidget:
        ...

    def start(self):
        ...

    def pause(self) -> None:
        ...

    stop_event: Incomplete
    collector: Incomplete

    def resume(self) -> None:
        ...

    @abstractmethod
    def pull_data(self) -> np.ndarray | None:
        ...

    def on_start(self) -> bool:
        ...

    @abstractmethod
    def on_stop(self):
        ...

    def save_data(
        self,
        data: np.ndarray,
        subfolder: str | None = None,
        filename: str | None = None,
        force_save: bool = False,
    ):
        ...

    def load_data(self, path: str | None = None) -> T | None:
        ...


class LiveDataReader(Reader, metaclass=abc.ABCMeta):
    @property
    def name(self) -> str:
        ...

    @name.setter
    def name(self, value: str):
        ...

    @property
    def dirname(self) -> str:
        ...

    @dirname.setter
    def dirname(self, value: str):
        ...

    @Binding
    def refresh_delay(self) -> float:
        ...

    @refresh_delay.onchange
    def __refresh_delay(self, value: float):
        ...

    @property
    def can_stream_data(self) -> bool:
        ...

    @can_stream_data.setter
    def can_stream_data(self, value: bool):
        ...

    def __init__(self, refresh_delay: float = 0.0):
        ...

    def get_parameters(
        self, frame: QWidget, view: View | None
    ) -> List[params.GUIParameter]:
        ...


class StreamDataReader(LiveDataReader, metaclass=abc.ABCMeta):
    max_rows: int

    class DataAggregationMethod(enum.IntEnum):
        LeaveNaN = 1
        ReplaceNaN = 2

    stream_save_i: int
    data: np.ndarray

    def __init__(self, *args, max_rows: int = 1000, **kwargs) -> None:
        ...

    def clear(self) -> None:
        ...

    def on_start(self) -> bool:
        ...

    def nan_aggregation_policy(self, axis: int) -> DataAggregationMethod:
        ...

    def aggregate_data(
        self, raw_data: np.ndarray, ignore_max_length: bool = False
    ) -> np.ndarray:
        ...

    @classmethod
    def nan_aggregation(
        cls, data: np.ndarray, raw_data: np.ndarray, max_row: int
    ) -> np.ndarray:
        ...

    def time_step(self, nb_elements: int) -> np.ndarray:
        ...

    def regularize(self, array: np.ndarray, length: int) -> np.ndarray:
        ...

    def load_data(self, path: str | None = None) -> T | None:
        ...
