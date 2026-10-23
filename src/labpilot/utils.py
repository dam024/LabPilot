import copy
import abc
import os
import traceback
from typing import Any, Callable, Dict, Tuple, Type, List
import queue
from PySide6.QtWidgets import QMainWindow
import numpy as np
from PySide6.QtCore import QTimer
import inspect

import functools
import threading
from concurrent.futures import ThreadPoolExecutor

import logging

logger = logging.getLogger(__name__)

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


class ThreadExecutor(abc.ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abc.abstractmethod
    def call(self, func, *args, **kwargs):
        """Add the given function to the queue to be executed on the main thread.

        Note:
            Safe to call from ANY thread

        Args:
            func (TYPE): Function to call
            *args: Positional arguments of the function
            **kwargs: Named arguments of the function
        """


class TestThreadExecutor(ThreadExecutor):
    """Test thread executor designed to run for tests. Do not use in production code!!!"""

    def __init__(self, *args, **kwargs) -> None:
        self.queue: queue.Queue[
            Tuple[Callable, Tuple[Any, ...], Dict[str, Tuple[Any, ...]]]
        ] = queue.Queue()
        super().__init__(*args, **kwargs)

    def call(self, func, *args, **kwargs):
        self.queue.put_nowait((func, args, kwargs))

    def main_thread_execute(self):
        """Executes all the methods that are in the queue and must be executed from the  main thread.

        Note:
            You must execute this method from a main thread!
        """
        assert (
            threading.current_thread().name == threading.main_thread().name
        ), f"You must call this method from the main thread only!"

        while not self.queue.empty():
            func, args, kwargs = self.queue.get_nowait()

            func(*args, **kwargs)

    def has_main_thread_func(self) -> bool:
        """Returns a boolean indicating if some functions needs to be executed from the main thread"""
        return not self.queue.empty()


class MainThreadExecutor(ThreadExecutor):
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
        super().__init__()

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


def concurrently(func: Callable):
    """Apply this method decorator to execute the current method concurrently

    Note:
        The method will be executed on a background thread!
        If you call this method from a background thread, it will be executed on a new thread

    Args:
        func (Callable): Function/method to execute concurrently

    Returns:
        ThreadPoolExecutor: The thread pool executor that will run the given method

    Example:
    ```python

    @concurrently
    def background_function(any_parameter):
        ...

    from concurrent.futures import ThreadPoolExecutor

    @concurrently
    def background_function2(any_parameter, threadPool: ThreadPoolExecutor):
        # You can set the special `threadPool` parameter to access the current thread executor!
        ...

    # You can access the threadPool to get the return value of the function if necessary. See https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
    thread_ppol = background_function(any_parameter = 'Hello World!')



    ```
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        def execute(*args, **kwargs):
            func(*args, **kwargs)

        pool = ThreadPoolExecutor(max_workers=1)

        kwargs["threadPool"] = pool

        # Check the signature
        sig = inspect.signature(func)
        try:
            sig.bind(*args, **kwargs)
        except TypeError:
            # If we get a type error, it means that the functionn does not take `threadPool` argument
            del kwargs["threadPool"]
        future = pool.submit(execute, *args, **kwargs)

        return pool

    return wrapper
