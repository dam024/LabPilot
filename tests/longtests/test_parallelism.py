"""This module tests that the threads managed by cython are indeed executed in parallel"""
import threading
import time
from typing import List
from labtools import utils
from labtools.GUI.binding import CBinding
import psutil
import os
import sys
import numpy as np

from tests.utils import UpdatableConfigTest

import labtools.DataReceiver as dr


class TestData(dr.ProcessedData):
    x: np.ndarray
    y: np.ndarray


class TestReadersThreads(UpdatableConfigTest):
    def setUp(self) -> None:
        self.readers: List[dr.LiveDataReader] = []
        return super().setUp()

    def tearDown(self) -> None:
        # Stops the loops
        for reader in self.readers:
            reader.pause()

        # Join the loops
        for reader in self.readers:
            if hasattr(reader, "collector") and reader.collector is not None:
                reader.collector.join()

        return super().tearDown()

    def _test_reader_parallelism(self):
        """With the GIL, we cannot have true parallelism, so this test is meaningless..."""
        status = sys._is_gil_enabled()
        self.assertFalse(status, "GIL enabled...")

        class BaseReader(dr.StreamDataReader):
            def __init__(self, *args, max_rows: int = 1000, **kwargs):
                super().__init__(*args, max_rows=max_rows, **kwargs)
                self.number_loops = 0

            def pull_data(self) -> np.ndarray:
                z = np.zeros((2, 10))
                self.number_loops += 1

                # Stop the loop after 50000 iterations for security reasons
                if self.number_loops > 50000:
                    self.pause()
                    print(f"Loop for {self.__class__.__name__} stopped!")
                return z

            def process_data(self, raw_data: np.ndarray) -> TestData:
                data = TestData()

                data.x = raw_data[0, :]
                data.y = raw_data[1, :]
                return data

            def on_stop(self):
                return super().on_stop()

        class Reader1(BaseReader):
            name = "Reader 1"
            dirname = "reader1"

        class Reader2(BaseReader):
            name = "Reader 2"
            dirname = "reader2"

        class Reader3(BaseReader):
            name = "Reader 3"
            dirname = "reader3"

        class Reader4(BaseReader):
            name = "Reader 4"
            dirname = "reader4"

        # Declare all the readers
        self.readers = [
            Reader1(),
            Reader2(),
            Reader3(),
            Reader4(),
        ]

        # Run all the loops
        for reader in self.readers:
            self.assertTrue(reader.start())

        time.sleep(0.1)

        # Check that the loops are running
        for reader in self.readers:
            self.assertTrue(reader.status.get() is dr.ReaderStatus.RUNNING)

        # Check the CPU load

        process = psutil.Process(os.getpid())
        value = process.cpu_percent(interval=0.5)
        print("CPU usage: ", value)

        # Makes sure they are still running
        for reader in self.readers:
            self.assertTrue(reader.status.get() is dr.ReaderStatus.RUNNING)

        # Check the value
        self.assertGreater(value, 150)

    def test_wait_time(self):
        """Test that the threads have a correct refresh delay"""

        class BaseReader(dr.StreamDataReader):
            name: str = "Test Reader"
            dirname: str = "test_reader"

            def __init__(self, *args, max_rows: int = 1000, **kwargs):
                super().__init__(*args, max_rows=max_rows, **kwargs)
                self.number_loops = 0

            def pull_data(self) -> np.ndarray:
                z = np.zeros((2, 10))
                self.number_loops += 1

                if isinstance(self.refresh_delay, CBinding):
                    time.sleep(self.refresh_delay.get() / 2)
                else:
                    time.sleep(self.refresh_delay / 2)

                # Stop the loop after 50000 iterations for security reasons
                if self.number_loops > 50000:
                    self.pause()
                    print(f"Loop for {self.__class__.__name__} stopped!")
                return z

            def process_data(self, raw_data: np.ndarray) -> TestData:
                data = TestData()

                data.x = raw_data[0, :]
                data.y = raw_data[1, :]
                return data

            def on_stop(self):
                return super().on_stop()

        # TEST START
        stop_event = threading.Event()
        refresh_delay = 1

        reader = BaseReader(refresh_delay=refresh_delay)

        # Measures the time the loop need to execute.
        start_time = time.perf_counter()
        reader._reader_event_loop_step(stop_event)
        stop_time = time.perf_counter()
        execution_time = stop_time - start_time

        self.assertLessEqual(
            execution_time, refresh_delay * 1.01
        )  # Allows the loop to take 1% more time


class TestMethodRethreading(UpdatableConfigTest):
    """Test the @concurrently and @threadSafe"""

    def setUp(self) -> None:
        self.thread_name: str | None = None
        return super().setUp()

    def test_concurrently(self):
        """Test that a @concurrently method executed from the main thread is executed concurrently"""

        @utils.concurrently
        def test_method(self):
            self.thread_name = threading.current_thread().name

        # Execute concurrently
        thread_pool = test_method(self)

        # Wait for the completion
        thread_pool.shutdown(wait=True)

        # Check that it executed
        self.assertIsNotNone(self.thread_name, f"The thread did not execute...")

        # Check that it was in a different thread from the current one
        self.assertNotEqual(
            threading.main_thread().name,
            self.thread_name,
            f"Executed in the main thread while it's supposed to execute in a background thread...",
        )

    def test_concurrently_bg_thread(self):
        """Test that a @concurrently method executed from a background thread is executed concurrently"""

        @utils.concurrently
        def test_method(self):
            self.thread_name = threading.current_thread().name

        def background_thread(self):
            # This method is executed on a background thread
            test_method(self)

        # Execute from a background thread
        thread = threading.Thread(target=background_thread, args=(self,))
        thread.start()

        # Wait for the execution of the thread
        thread.join()

        # Check that it executed
        self.assertIsNotNone(self.thread_name, f"The thread did not execute...")

        # Check that it was executed on the main thread
        self.assertNotEqual(
            threading.main_thread().name,
            self.thread_name,
            f"Executed in the main thread while it's supposed to execute in a background thread...",
        )
        self.assertNotEqual(
            thread.name,
            self.thread_name,
            f"Executed in the main thread while it's supposed to execute in a background thread...",
        )

    def test_threadSafe_main_thread(self):
        """Test that a method executed with @threadSafe from the mainthread is still executed from the main thread"""

        @utils.threadSafe
        def test_method(self):
            self.thread_name = threading.current_thread().name

        # Execute concurrently
        test_method(self)

        # Check that it executed
        self.assertIsNotNone(self.thread_name, f"The thread did not execute...")

        # Check that it was executed on the main thread
        self.assertEqual(
            threading.main_thread().name,
            self.thread_name,
            f"Executed in the main thread while it's supposed to execute in a background thread...",
        )

    def test_main_thread(self):
        """Test that a @threadSafe method executed from a background thread is executed on the main thread"""

        @utils.threadSafe
        def test_method(self):
            self.thread_name = threading.current_thread().name

        def background_thread(self):
            # This method is executed on a background thread
            test_method(self)

        # Execute from a background thread
        thread = threading.Thread(target=background_thread, args=(self,))
        thread.start()

        # Wait for the execution of the thread
        thread.join()

        # Check that the job was scheduled
        self.assertTrue(self.has_thread_jobs())

        # Execute main thread methods
        self.main_thread_execute()

        self.assertIsNotNone(utils._executor)

        # Check that it executed
        self.assertIsNotNone(self.thread_name, f"The thread did not execute...")

        # Check that it was executed on the main thread
        self.assertEqual(
            threading.main_thread().name,
            self.thread_name,
            f"Executed in the main thread while it's supposed to execute in a background thread...",
        )
