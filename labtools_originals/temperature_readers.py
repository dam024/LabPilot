from __future__ import annotations
import traceback
from typing import List, overload

from PySide6.QtWidgets import QWidget
import numpy as np
import pyvisa

from snapshot.GUI.binding import Binding
from snapshot.GUI.parameters import GUIParameter
import snapshot.analysis as ana
from snapshot.DataReceiver import ProcessedData, StreamDataReader
from snapshot import logger
from config import generalConfig as config
import snapshot.plots.plots_implementation as plots
import snapshot.GUI.objects as gui_obj


class TemperatureData(ProcessedData):
    t: np.ndarray
    # Resistance for the PT100 probe
    resistance_pt100: np.ndarray
    # Temperature from PT100 probe
    T_pt100: np.ndarray
    # Temperature from thorlabs sensor
    T_thorlabs: np.ndarray
    # Humidity from thorlabs sensor
    humidity_thorlabs: np.ndarray


class TemperatureHumidityReader(StreamDataReader[TemperatureData]):
    name: str = "Temperature and Humidity"
    dirname: str = "temperature_humidity"

    # Parameters for the multimeter
    RANGE_V: int = 10
    NPLC: int = 12
    AVG_COUNT: int = 20

    @Binding
    def refresh_delay(self) -> float:
        """Time to wait between every value [s]"""
        return 10.0

    def __init__(self, *args, max_rows: int = 1000, **kwargs):
        self.IP = config.get("DIGITAL_MULTIMETER", "IP")
        self.a = float(config.get("DIGITAL_MULTIMETER", "C-D-A"))
        self.b = float(config.get("DIGITAL_MULTIMETER", "C-D-B"))
        self.c = float(config.get("DIGITAL_MULTIMETER", "C-D-C"))
        self.R_0 = float(config.get("DIGITAL_MULTIMETER", "R_0"))

        super().__init__(*args, max_rows=max_rows, **kwargs)

    def on_start(self) -> bool:
        if not super().on_start():
            return False

        try:
            logger.debug("Attempting connection to oscilloscope...")

            # self.socket.settimeout(5)
            # self.socket.connect((self.IP, self.PORT))

            # Start resource manager
            self.rm = pyvisa.ResourceManager()
            self.sds = self.rm.open_resource(f"TCPIP0::{self.IP}::inst0::INSTR")
            self.sds.timeout = 30000  # 30s
            self.sds.chunk_size = 20 * 1024 * 1024  # 20MB

            rslt = str(self.send_command("*IDN?"))

            self.setup_multimeter()

        except Exception as e:
            logger.error(f"Temperature Multimeter connection failed: {self.IP}: {e}")
            traceback.print_exception(e)
            self.rm = None
            self.sds = None
            return False

        return True

    def on_stop(self):
        super().on_stop()

        if self.sds is not None:
            self.send_command(":TRIG:CONT REST")
            self.sds.close()
            logger.info("Temperature multimeter disconnected!")

    def setup_multimeter(self):
        """Setup the multimeter to have always the same parameters"""
        # Reset
        self.send_command("*RST")
        # Clear status/errors
        self.send_command("*CLS")

        # Set the function to 4-wire measurement
        self.send_command(':SENS:FUNC "FRES"')

        # Enable auto range
        self.send_command(":SENS:FRES:RANG:AUTO ON")

        # Enable offset compensation
        self.send_command(":SENS:FRES:OCOM ON")

        # Enable auto zero
        self.send_command(":SENS:FRES:AZER ON")

        # set NPLC to 1 (Number of Power Line Cycles -> how much we average the measurements)
        self.send_command(":SENS:FRES:NPLC 1")

    def send_command(self, command: str) -> bytes:
        if self.sds is None:
            return b""

        self.sds.write(command)
        # If data out are expected, treat them
        if "?" in command or command.endswith("DATA") or command.endswith("DAT2"):
            value = self.sds.read().strip()
            # raw_bytes = self.sds.recv(recv_size)
            # The value returns contains the command sent with the data separated by a space. Get the value
            # value = raw_bytes  # .split()[1]

            # logger.debug(f"Oscilloscope command: {command}. Output: {value}")

            return value  # .rstrip(b"V")
        # logger.debug(f"Oscilloscope command: {command}. No output")
        return b""

    def pull_data(self) -> np.ndarray | None:
        if self.sds is None:
            return None

        resistance_pt100 = self.send_command(":READ?")
        t = self.time_step(1)

        z = np.zeros((4, 1))

        z[0, :] = t
        z[1, :] = resistance_pt100
        # z[2, :] = ...
        # z[3, :] = ...

        # Restore continuous display/updates after the read [6](https://tamironov.com/keithley-dmm6500/)
        # self.send_command(":TRIG:CONT REST")

        return z

    def process_data(self, raw_data: np.ndarray) -> TemperatureData:
        obj = TemperatureData()

        obj.t = raw_data[0, :]
        obj.resistance_pt100 = raw_data[1, :]
        obj.T_pt100 = self.convert_R_to_T(obj.resistance_pt100)
        obj.T_thorlabs = raw_data[2, :]
        obj.humidity_thorlabs = raw_data[3, :]

        return obj

    @overload
    def convert_R_to_T(self, R: float) -> float:
        ...

    @overload
    def convert_R_to_T(self, R: np.ndarray) -> np.ndarray:
        ...

    def convert_R_to_T(self, R: float | np.ndarray) -> float | np.ndarray:
        # idx = np.asarray(R >= self.R_0, dtype=int)

        T_gt_0 = (-self.a + np.sqrt(self.a**2 - 4 * self.b * (1 - R / self.R_0))) / (
            2 * self.b
        )

        # Since I don't need such a precise measurement on the temperature and that self.c is small, I decided to use the same formula for both positive and negative temperatures. This allows me to save some time...
        # rho = R / self.R_0 * (1 - idx)

        # T_0 = -self.a + np.sqrt(self.a**2 - 4 * self.b * (1 - rho))

        # T_st_0 = T_0 - (self.c * (T_0 - 100) * T_0**3) / (
        #    self.a + 2 * self.b * T_0 + self.c * (4 * T_0**3 - 300 * T_0 * T_0)
        # )

        # T_st_0 = (R - 100) / 0.385

        return T_gt_0  # * idx + T_st_0 * (1 - idx)

        p = self.b / self.c - 3750.0
        q = (self.a + 50 * self.b) / self.c - 125000.0
        s = (1 - rho + 25 * self.a + 625 * self.b) / self.c - 1171875
        P = -p * p / 12 - s
        Q = -(p**3) / 108 + p * s / 3 - q * q / 8
        U = np.cbrt(-Q / 2 + np.sqrt(Q * Q + P**3 / 27))
        Y = -5 * p / 6 - U - P / (3 * U)
        W = np.sqrt(p + 2 * Y)

        T_st_0 = 25 + 1 / 2 * (-W + np.sqrt(-(3 * p + 2 * Y + 2 * q / W)))

        print(rho, p, q, s, P, Q, U, Y, W)

        return T_gt_0 * idx + T_st_0 * (1 - idx)

    @overload
    def convert_T_to_R(self, T: float) -> float:
        ...

    @overload
    def convert_T_to_R(self, T: np.ndarray) -> np.ndarray:
        ...

    def convert_T_to_R(self, T: float | np.ndarray) -> float | np.ndarray:
        idx = np.asarray(T >= 0, dtype=int)

        # print(idx)
        R_gt_0 = self.R_0 * (1 + self.a * T + self.b * T * T)

        R_st_0 = self.R_0 * (
            1 + self.a * T + self.b * T * T + self.c * (T - 100) * T * T * T
        )

        return R_gt_0 * idx + R_st_0 * (1 - idx)


class TemperatureAnalysis(ana.DataAnalysis):
    title: str = "Temperature"

    def __init__(self) -> None:
        self.plot_H = plots.SimplePlot(
            "humidity",
            title="Humidity",
            xlabel="time [s]",
            ylabel="Humidity [%]",
            update_axis=True,
        )
        self.plot_T = plots.SimplePlot(
            "temperature",
            title="Temperature",
            xlabel="time [s]",
            ylabel="Temperature [°C]",
            update_axis=True,
        )
        self.graphs = [self.plot_H, self.plot_T]
        super().__init__()

    @ana.reader
    def temperature_reader(self) -> TemperatureHumidityReader:
        ...

    def refresh_plots(self):
        temperature_data = self.temperature_reader().get_data()

        if temperature_data is not None:
            self.plot_T.set_data(temperature_data.t, temperature_data.T_pt100)
            self.plot_H.set_data(temperature_data.t, temperature_data.humidity_thorlabs)
        return super().refresh_plots()
