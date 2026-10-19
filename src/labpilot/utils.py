import copy
import abc
import os
import traceback
from typing import Any, Callable, Type, List
import queue
from PySide6.QtWidgets import QMainWindow
import numpy as np
from PySide6.QtCore import QTimer
import tqdm
import inspect
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import functools
import threading
from concurrent.futures import ThreadPoolExecutor

import labpilot._logging as log


def resample(arr: np.ndarray, every: int):
    """Given an array, resample the data every `every` data point.

    Data are averaged to create a new datapoint.
    """
    end_nb = arr.shape[-1] // every
    stop = end_nb * every  # % every

    s: List[slice | int] = [slice(None)] * len(arr.shape)
    s[-1] = slice(None, stop)

    new_shape = (*arr.shape[:-1], end_nb, every)

    r = arr[tuple(s)].reshape(new_shape)
    m = np.mean(r, axis=-1)

    if stop < arr.shape[-1]:
        s[-1] = slice(stop, None)
        s_m = s.copy()
        s_m[-1] = -1

        # m[*s_m] = (np.sum(arr[*s], axis=-1) + every * m[*s_m]) / (
        #    arr.shape[-1] - stop + every
        # )
        m[tuple(s_m)] = (np.sum(arr[tuple(s)], axis=-1) + every * m[tuple(s_m)]) / (
            arr.shape[-1] - stop + every
        )

    return m


def read_data(path_template: str, zip_delete: bool = False) -> np.ndarray:
    """From a recording, aggregate all data from all outputs to create a single file with everything

    Args:
        path_template (str): Path to one of the "output_%1.npy" file to aggregate
        zip_delete (bool, optional): If `True`, will ZIP all "output_%1.npy" files into a single ZIP file and delete the original files

    Returns:
        np.ndarray: Description
    """
    direct_file = os.path.join(os.path.dirname(path_template), "data.npy")
    zip_file = os.path.join(os.path.dirname(path_template), "originals.zip")

    data = np.array([])

    # List all files with the format output_%1.py
    all_files = list(Path(os.path.dirname(path_template)).glob("output_*.npy"))

    # Check if it already exists as a single file
    if os.path.exists(direct_file):
        data = np.load(direct_file)
    else:
        for i in tqdm.tqdm(range(len(all_files)), desc="aggregation"):
            # print(f"Importing {i}/{len(all_files)}")
            path = path_template.replace("%1", str(i))
            # data_step = np.mean(np.load(path), axis=-1, keepdims=True)
            data_step = np.load(path)

            if data.shape == (0,):
                data = data_step.copy()
            else:
                data = np.append(data, data_step, axis=1)

            # print(data.shape, data_step.shape)

        np.save(direct_file, data)

    # Find all output_*.npy files

    if zip_delete and not os.path.exists(zip_file):
        # Zip all output_%1.npy files into a single zip file and deletes them

        # Create ZIP archive
        with ZipFile(zip_file, "w", compression=ZIP_DEFLATED) as zipf:
            for file in tqdm.tqdm(all_files, desc="ZIP creation"):
                zipf.write(file, arcname=file.name)

    if len(all_files) > 0 and zip_delete:
        # Delete original files
        for file in tqdm.tqdm(all_files, desc="detail files suppression"):
            file.unlink()

    return data


def list_experiment_folders(base_path: str) -> List[str]:
    experiment_folders: List[str] = []
    rec_folders = [base_path]
    while len(rec_folders) > 0:
        # Pop
        current_folder = rec_folders.pop()

        # Check if it has an info.json
        sub_dirs = os.walk(current_folder).__next__()
        if (
            os.path.exists(os.path.join(current_folder, "info.json"))
            and len(sub_dirs[1]) > 0
        ):
            # This is an experiment folder!
            exp_path = os.path.dirname(current_folder)
            if exp_path not in experiment_folders:
                experiment_folders.append(exp_path)
        else:
            # List sub dirs
            for d in sub_dirs[1]:
                if d == "Simulation_checks":
                    continue
                rec_folders.insert(0, os.path.join(sub_dirs[0], d))

    return experiment_folders


class AbstractProperties(abc.ABC):
    """This class provides a mecanism to ensure that some properties are declared in subclasses.

    Subclasses must call the methods of this class to ensure that the desired properties are defined in subclasses
    """

    __dict__: dict

    def _check_for_property(self, name: str, type: Type | None = None):
        """Check that the current instance possesses a given property

        Args:
            name (str): Name of the property to check
            type (Type): Type of the property
        """
        if not hasattr(self, name):
            raise AttributeError(
                f"You must define the property `{name}` in class {self.__class__.__name__}. If you have defined it in the __init__(), you must do it BEFORE calling super().__init__()"
            )

        if type is not None and not isinstance(getattr(self, name), type):
            raise TypeError(
                f"The type of the property `{name}` must be `{type}` in class {self.__class__.__name__}. Obtained type: {getattr(self, name)}"
            )

    def _set_if_not_defined(self, name: str, value):
        """Set the value for a property if it is not already defined

        Args:
            name (str): Name of the property
            value (Any): Value to assign if the property is not already defined
        """
        if not hasattr(self, name):
            setattr(self, name, value)

    def _make_attribute_instance(self, attr: str, default: Any):
        """Make the given attribute local to the class


        Args:
            attr (str): Name of the attribute
            default (Any): Value to reset the class attribute to


        It is possible to define the class attributes:
            ```python
            class MyClass(AbstractProperties):
                graphs: List[AnObject] = []
            ```

            When we do this, the array `graphs` is shared among all instances of `MyClass`.

        One solution is the following:
            ```python
            class MyClass(AbstractProperties):

                def __init__(self) -> None:
                    self.graphs: List[AnObject] = []
            ```
            However, if subclasses must modify the `graphs` array, this should normally be done BEFORE the `__init__`, so the modifications can could be removed.

            This method provides a way to make the `graphs` array (and any objects saved as reference in memory) being declared as class attribute, while keeping them local to each instance.

        """

        if attr in type(self).__dict__ and attr not in vars(self):
            setattr(self, attr, copy.copy(getattr(type(self), attr)))
            setattr(type(self), attr, default)


# _root: tkinter.Tk


class TestThreadExecutor:
    def __init__(self) -> None:
        pass

    def call(self, func, *args, **kwargs):
        func(*args, **kwargs)


class MainThreadExecutor:
    """Dispatch function calls to the main thread

    This object is responsible to execute a function on the main thread when it is called from a background thread
    """

    def __init__(self, root: QMainWindow, interval=10):
        self.root = root
        self.queue = queue.Queue()
        self.interval = interval
        self.timer = QTimer(root)
        self.timer.timeout.connect(self._poll)
        self.timer.start(self.interval)
        # self._poll()

    def call(self, func, *args, **kwargs):
        """Safe to call from ANY thread"""
        self.queue.put((func, args, kwargs))

    def _poll(self):
        while not self.queue.empty():
            func, args, kwargs = self.queue.get_nowait()
            try:
                func(*args, **kwargs)
            except Exception as e:
                traceback.print_exc()
                print("Error in main-thread task:", e)
        # self.root.after(self.interval, self._poll)


_executor: MainThreadExecutor | None = None


# def application_root() -> tkinter.Tk:
#    return _root


def threadSafe(func: Callable):
    """Creates a function wrapper that automatically executes code in the main thread if necessary. Therefore, all the code called in the function will be thread safe!"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        def execute():
            func(*args, **kwargs)

        if threading.current_thread() is threading.main_thread():
            execute()
        else:
            if _executor is not None:
                _executor.call(execute)
            else:
                print(
                    f"{log.ColoredFormatter.COLORS['WARNING']}Executing {func.__name__} on the current thread, because you did not set a global `MainThreadExecutor`!!{log.ColoredFormatter.RESET}"
                )
                execute()

    return wrapper


def concurrently(func):
    """Apply this method decorator to execute the current method concurrently


    Note:
        The method will be executed on a background thread!
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        def execute(*args, **kwargs):
            func(*args, **kwargs)

        pool = ThreadPoolExecutor(max_workers=1)

        kwargs["threadPool"] = pool

        # Check the signature
        sig = inspect.signature(func)
        if not sig.bind(*args, **kwargs):
            del kwargs["threadPool"]
        future = pool.submit(execute, *args, **kwargs)

        return pool

    return wrapper
