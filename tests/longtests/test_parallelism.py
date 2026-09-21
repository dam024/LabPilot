"""This module tests that the threads managed by cython are indeed executed in parallel"""
import time
from typing import List
import psutil
import os
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

    def test_reader_parallelism(self):
        dr.LiveDataReader

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
            reader._setup(None)
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
