from __future__ import annotations
from ctypes import (
    byref,
    c_bool,
    c_char_p,
    c_double,
    c_int,
    c_int16,
    c_uint32,
    create_string_buffer,
)
import threading
import time
from types import ClassMethodDescriptorType
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    Self,
    Tuple,
    Type,
    overload,
)
import socket
import pyvisa
import os
from PySide6.QtWidgets import QWidget

import serial
from serial import serialutil
from serial.tools.list_ports import comports

# from scpi_control import Oscilloscope

from snapshot.GUI.parameters import GUIParameter
from snapshot.GUI.binding import Binding, Status
import snapshot.GUI.objects as gui_obj

from snapshot.DataReceiver import ProcessedData, StreamDataReader
import snapshot.plots.plots_implementation as plots
from snapshot import logger
from config import generalConfig as config

import numpy as np
import numpy.typing as npt

from src.thorlabs_power_meter import TLPM_DEFAULT_CHANNEL, TLPMX


import threading


class OscilloscopeData(ProcessedData):
    t: np.ndarray
    ch1: np.ndarray
    ch2: np.ndarray
    ch1_power: np.ndarray
    ch2_power: np.ndarray
    transmission: np.ndarray


class OscilloscopeReader(StreamDataReader[OscilloscopeData]):
    name: str = "Oscilloscope"
    dirname: str = "transmission_measurement"
    max_rows = 500000
    # graphs: List[GraphSet] = []
    # ignore = True

    # with 50 Ohm termination,
    gain_to_tg_scale = {
        "0": 0.75e3,
        "10": 2.38e3,
        "20": 7.5e3,
        "30": 23.8e3,
        "40": 75e3,
        "50": 238e3,
        "60": 750e3,
        "70": 2.38e6,
    }
    DETECTOR_SATURATION_THRESHOLD = 5.2
    # gain_1 = "70"
    # gain_2 = "70"

    @Binding
    def detector_gain_1(self) -> str:
        """Gain of the detector in channel 1"""
        return "70"  # self.gain_1

    @Binding
    def detector_gain_2(self) -> str:
        """Gain of the detector in channel 1"""
        return "70"  # self.gain_2

    @Binding
    def fiber_splitter_ratio(self) -> float:
        """Ratio of the beam spliter: coeff_channel_1 / coeff_channel_2"""
        return 0.1

    @Status
    def detectors_saturated(self) -> bool:
        """Indicates if the detector is saturated"""
        return False

    @detectors_saturated.onchange
    def __detectors_saturated(self, value: bool):
        """Executed on change of a the detector being saturated"""
        if value:
            logger.warning("!!!!Detector Saturated!!!!")
        else:
            logger.info("Detector not saturated anymore")

    def __init__(self, *args, **kwargs):
        self.IP = config.get("OSCILLOSCOPE", "IP_ADDRESS")
        self.PORT = int(config.get("OSCILLOSCOPE", "PORT"))
        logger.dev_warning("Handle is_dB")
        self.is_dB = True
        if self.is_dB:
            ylabel = "T [dB]"
        else:
            ylabel = "T [a.u]"

        super().__init__(*args, **kwargs)

    def get_parameters(
        self, frame: QWidget, view: ana.View | None
    ) -> List[GUIParameter]:
        parameters = []

        # def make_gain(
        #    name: str, variable: tkinter.Variable
        # ) -> Callable[[Optional[tkinter.Event]], bool]:
        #    def wrapper(*args):
        #        setattr(self, name, variable.get())
        #        return True
        #
        #    return wrapper

        # self.detector_gain_1.tk_variable().trace_add(
        #    "write", make_gain("gain_1", self.detector_gain_1.tk_variable())
        # )
        # self.detector_gain_2.tk_variable().trace_add(
        #    "write", make_gain("gain_2", self.detector_gain_2.tk_variable())
        # )

        # gain
        gain_1_parameter = GUIParameter(
            widget=gui_obj.Combobox(
                frame,
                label="Gain detector 1 [dB]:",
                current_value=self.detector_gain_1,
                values=list(self.gain_to_tg_scale.keys()),
            )
        )

        parameters.append(gain_1_parameter)

        # gain
        gain_2_parameter = GUIParameter(
            widget=gui_obj.Combobox(
                frame,
                label="Gain detector 2 [dB]:",
                current_value=self.detector_gain_2,
                values=list(self.gain_to_tg_scale.keys()),
            )
        )

        parameters.append(gain_2_parameter)

        # Fiber splitter
        fiber_splitter_parameter = GUIParameter(
            widget=gui_obj.NumericalValueInput(
                frame,
                from_=0.001,
                to=0.999,
                value=self.fiber_splitter_ratio,
                text="Ratio Channel 1",
                increment=0.001,
            )
        )

        parameters.append(fiber_splitter_parameter)

        parameters += super().get_parameters(frame, view)

        return parameters

    def on_start(self) -> bool:
        # Check the connection: Load informations about the oscilloscope
        if not super().on_start():
            return False

        try:
            # Connection to the socket
            # self.dump_threads()
            logger.debug("Attempting connection to oscilloscope...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # self.socket.settimeout(5)
            # self.socket.connect((self.IP, self.PORT))

            # Start resource manager
            self.rm = pyvisa.ResourceManager()
            self.sds = self.rm.open_resource(f"TCPIP::{self.IP}::INSTR")
            self.sds.timeout = 30000  # 30s
            self.sds.chunk_size = 20 * 1024 * 1024  # 20MB

            rslt = str(self.send_command("*IDN?"))

            self.setup_scope()
            self.read_scaling()

            logger.info(f"Oscilloscope connection success: {rslt}")
            return True
        except Exception as e:
            self.socket = None
            self.rm = None
            self.sds = None
            # print("Before error...")
            logger.error(
                f"Oscilloscope connection failed ({self.IP}:{self.PORT}): {str(e)}"
            )
            logger.exception(e)
            # print("After error...")
            # logger.error(repr(e))
            return False

    def setup_scope(self):
        """Execute a few initial configuration to the oscilloscope at the beginning"""
        # Remove headers from commands
        self.send_command("CHDR OFF")

        self.send_command("TDIV 0.01")

        # self.send_command("ACQ:MEMD LONG")
        # self.send_command("ACQW SAMPLING")

        # Enable History / rollback
        # self.send_command("HSMD ON")

        # Leave initialization being done
        # time.sleep(0.1)

        # Waveform transfer optimization
        # self.send_command("WFSU SP,4,NP,10000")  # Indicates we need to send all data points

        # Start aquisition
        # self.send_command("MSIZ 70")
        # self.send_command("TRMD AUTO")
        # self.send_command("TRSE EDGE,SR,C1")

        self.send_command("C1:TRA ON")
        self.send_command("C1:CPL DC")

        self.send_command("C2:TRA ON")
        self.send_command("C2:CPL DC")

        self.send_command("WFSU SP,4,NP,50000")

        # self.send_command("TRMD AUTO")
        self.send_command("TRIG_MODE AUTO")
        # self.send_command("RUN")
        #

    def reset_scope(self):
        """Execute a few commands to configure the oscilloscope in Roll mode"""
        # Set scale for time division
        self.send_command("TDIV 0.2")

        self.send_command("TRMD AUTO")

    def read_scaling(self):
        """Read the scaling parameters for efficient conversion from raw data to actual voltages"""
        # Read the scale of the voltage
        self.vdiv1 = float(self.send_command("C1:VDIV?"))
        self.vdiv2 = float(self.send_command("C2:VDIV?"))

        # Read the offset of the voltage
        self.offset1 = float(self.send_command("C1:OFST?"))
        self.offset2 = float(self.send_command("C2:OFST?"))

        # Read time scaling
        self.sara = float(self.send_command("SARA?"))

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

    def read_channel(self, ch: Literal["C1", "C2"]) -> np.ndarray:
        if self.socket is None or self.sds is None:
            return np.array([])

        if ch == "C1":
            vdiv = self.vdiv1
            offset = self.offset1
        else:
            vdiv = self.vdiv2
            offset = self.offset2

        cmd = f"{ch}:WF? DAT2"
        self.sds.write(cmd)
        # Read and prepare data
        raw_bytes = self.sds.read_raw()
        length_header = len("DAT2") + 3 + 9
        # print(raw_bytes[:40], raw_bytes[length_header:40])
        raw_data = np.array(list(raw_bytes)[length_header:])  # Skip header
        raw_data = list(np.where(raw_data > 127, raw_data - 256, raw_data))
        raw_data.pop()
        raw_data.pop()
        return np.array(raw_data) / 25 * vdiv - offset

    def pull_data(self) -> np.ndarray | None:
        # t0 = time.perf_counter()
        if self.socket is None or self.sds is None:
            return None

        # Need to wait for data acquisition to have time to execute...
        time.sleep(0.2)

        self.read_scaling()

        ch1 = self.read_channel("C1")
        ch2 = self.read_channel("C2")

        if ch1.shape != ch2.shape:
            # self.read_scaling()
            logger.warning(f"Read scalling! {ch1.shape}, {ch2.shape}")
            # return np.array([[],[],[]])
        #    logger.error(
        #        f"Data in channel 1 have a different shape [{ch1.shape}] than in channel 2 [{ch2.shape}]"
        #    )
        # print(ch1[:20], ch1[:-20])
        # n_samples = ch1.shape[0]
        # n_samples = ch2.shape[0]
        n_samples = max(ch1.shape[0], ch2.shape[0])

        z = np.zeros((3, n_samples))

        t = self.time_step(n_samples)  # t0 + np.arange(n_samples) / self.sara
        z[0, :] = t
        z[1, :] = ch1
        z[2, :] = ch2
        # t1 = time.perf_counter()
        # logger.debug(f"Elapsed time for data_collection: {t1-t0}")
        return z

    def process_data(self, raw_data: np.ndarray) -> OscilloscopeData:
        obj = OscilloscopeData()

        # Set the different fields
        obj.t = raw_data[0, :]
        obj.ch1 = raw_data[1, :]
        obj.ch2 = raw_data[2, :]
        obj.ch1_power = (
            1.0
            / self.fiber_splitter_ratio.get()
            * self.optical_power(obj.ch1, self.detector_gain_1.get())
        )
        obj.ch2_power = (
            1.0
            / (1.0 - self.fiber_splitter_ratio.get())
            * self.optical_power(obj.ch2, self.detector_gain_2.get())
        )

        # if np.any(obj.ch1 >= 5.0) or np.any(obj.ch2 >= 5.0):
        # logger.warning("!!!!Detector staturated!!!!")
        # print("Test: ", np.any(obj.ch1 >= 5.0) or np.any(obj.ch2 >= 5.0), bool(np.any(obj.ch1 >= 5.0) or np.any(obj.ch2 >= 5.0)))
        # self.detectors_saturated.set(bool(np.any(obj.ch1 >= 5.0) or np.any(obj.ch2 >= 5.0)))
        self.detectors_saturated = bool(
            np.any(obj.ch1 >= self.DETECTOR_SATURATION_THRESHOLD)
            or np.any(obj.ch2 >= self.DETECTOR_SATURATION_THRESHOLD)
        )

        if self.is_dB:
            obj.transmission = np.nan_to_num(
                10 * np.log10(obj.ch2_power / obj.ch1_power),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

        else:
            obj.transmission = obj.ch1_power - obj.ch2_power

        return obj

    def on_stop(self):
        super().on_stop()
        if self.socket is not None and self.sds is not None:
            # if self.scope is not None and not self.scope.is_connected:
            self.reset_scope()
            # self.socket.close()
            self.sds.close()
            # self.scope.disconnect()
            logger.info("Oscilloscope disconnected")

    @overload
    @classmethod
    def optical_power(cls, voltage: float | np.floating[Any], gain: str) -> float:
        ...

    @overload
    @classmethod
    def optical_power(
        cls, voltage: npt.NDArray[np.float64], gain: str | npt.NDArray[np.str_]
    ) -> np.ndarray:
        ...

    @classmethod
    def optical_power(
        cls,
        voltage: float | np.floating[Any] | npt.NDArray[np.float64],
        gain: str | npt.NDArray[np.str_],
    ):
        """Computes the optical power in mW"""
        responsivity = 1.05  # A/W -> for 1550nm wavelength

        if gain not in cls.gain_to_tg_scale:
            raise ValueError(
                f"Gain {gain} not supported. Choose from {list(cls.gain_to_tg_scale.keys())}"
            )

        if isinstance(gain, np.ndarray):
            tg_scale = np.array([cls.gain_to_tg_scale[g] for g in gain])
        else:
            tg_scale = cls.gain_to_tg_scale[gain]

        p_opt = voltage / (responsivity * tg_scale)

        return p_opt * 1000


class OscilloscopeAveragedMeasurements(OscilloscopeReader):
    name: str = "Oscilloscope (LSR)"
    dirname: str = "lsr_oscilloscope"
    # Since we have lots of data over a long time, don't allow streaming during simulation
    can_stream_data: bool = False

    @Binding
    def refresh_delay(self) -> float:
        """Number of seconds to wait between each measurements"""
        return 0.0

    def pull_data(self) -> np.ndarray | None:
        # Do an average of the pulled data to reduce their number...
        z = super().pull_data()
        if z is not None:
            z = np.mean(z, axis=1, keepdims=True)

        return z


class PowerMeterData(ProcessedData):
    time: np.ndarray
    power: np.ndarray


class PowerMeter(StreamDataReader[PowerMeterData]):
    name: str = "Power Meter"
    dirname: str = "power_meter"
    ignore = False
    # refresh_delay = 0.1

    @Binding
    def refresh_delay(self) -> float:
        return 0.1

    def __init__(self, *args, max_rows: int = 50, **kwargs):
        super().__init__(*args, max_rows=max_rows, **kwargs)

    @Binding
    def wavelength(self) -> float:
        """Returns the wavelengths in nm"""
        return 1550.0

    def on_start(self) -> bool:
        try:
            self.power_meter = TLPMX()

            # Listing all devices
            deviceCount = c_uint32()
            self.power_meter.findRsrc(byref(deviceCount))
            if deviceCount.value == 0:
                logger.exception(
                    "No power meter was found... Please, make sure it is connected!"
                )
                return False
            elif deviceCount.value == 1:
                # Get the name of the power meter
                resourceName = create_string_buffer(1024)

                self.power_meter.getRsrcName(c_int(0), resourceName)

                # Close and reset the object
                self.power_meter.close()
                self.power_meter = TLPMX()

                # Now, we can start...
                self.power_meter.open(resourceName, c_bool(True), c_bool(True))

                self.setup_power_meter()
            else:
                logger.exception(
                    f"{deviceCount.value} power meters were found. Handling of multiple power meters is not yet supported. Please, update the code of this application to support multiple power meters! Code examples can be found here: https://github.com/Thorlabs/Light_Analysis_Examples/tree/main/Python/Thorlabs%20PMxxx%20Power%20Meters/TLPMX_dll (23.07.2026)"
                )

                return False

        except Exception as e:
            logger.error(f"Impossible to read from the power meter... \n{e}")
            print(e)
            return False

        if not super().on_start():
            return False

        return True

    def setup_power_meter(self):
        """This method is responsible to adjust the parameters of the power meter, so that it always behaves the same and is automatically configured"""

        # Set the wavelength
        self.power_meter.setWavelength(
            c_double(self.wavelength.get()), TLPM_DEFAULT_CHANNEL
        )

        # Enable auto-range mode
        self.power_meter.setPowerAutoRange(c_int16(1), TLPM_DEFAULT_CHANNEL)

        # Set power units to Watt
        self.power_meter.setPowerUnit(c_int16(0), TLPM_DEFAULT_CHANNEL)

        # Wait until the power meter gets ready:
        time.sleep(2)

    def on_stop(self):
        self.power_meter.close()
        return super().on_stop()

    def pull_data(self) -> np.ndarray | None:
        # Read power
        power = c_double()
        t = self.time_step(1)
        self.power_meter.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
        # print(power.value)
        # Read unit
        z = np.zeros((2, 1))
        z[0, :] = t
        z[1, :] = power.value * 1000
        return z

    def process_data(self, raw_data: np.ndarray) -> PowerMeterData:
        data = PowerMeterData()

        data.time = raw_data[0, :]
        data.power = raw_data[1, :]

        return data


class LaserData(ProcessedData):
    time: np.ndarray
    temperature: np.ndarray
    current: np.ndarray
    voltage: np.ndarray


class LaserController(StreamDataReader[LaserData]):
    name: str = "Laser"
    dirname: str = "laser"
    graphs: List[plots.GraphSet] = []
    ignore = False

    def __init__(self, *args, **kwargs):
        # self.port = "COM12" # Make a parameter, also with the baudrate
        self.serial = serial.Serial(timeout=2.0, write_timeout=2.0)
        self.serial_lock = threading.Lock()
        self.refresh_delay = float(config.get("LASER", "monitor_rate"))
        # print(comports())
        super().__init__(*args, **kwargs)

    @property
    def min_I(self) -> int:
        """Minimum current for the laser"""
        return 0

    @property
    def max_I(self) -> int:
        """Maximum current for the laser"""
        return 100

    @property
    def min_T(self) -> float:
        """Minimum temperature for the laser"""
        return 15.0

    @property
    def max_T(self) -> float:
        """Maximum temperature for the laser"""
        return 35.0

    @Status
    def port(self) -> str:
        return ""

    @Binding
    def I(self) -> int:
        return 20

    @I.onchange
    def __I(self, value: int):
        if self.is_laser_on():
            self.set_current(value)
        else:
            logger.warning("Couldn't update laser value")

    @Binding
    def T(self) -> float:
        return 25.0

    @T.onchange
    def __T(self, value: float):
        if self.is_laser_on():
            self.set_temperature(value)
        else:
            logger.warning("Couldn't update laser value")

    def send_command(self, command: str) -> bytes:
        with self.serial_lock:
            if self.serial.is_open:
                self.serial.write(command.encode() + b"\r\n")
                line = self.serial.readline()
                line = self.serial.readline().removesuffix(b"\r\n")
                logger.debug(f"Laser command: {command}. Output: {line}")
                return line
            else:
                logger.debug(f"Laser: Serial port unavailable")
                return b"0.0"

    def pull_data(self) -> np.ndarray:
        t = self.time_step(1)

        z = np.zeros((4, 1))
        z[0, :] = t[0]
        z[1, :] = self.get_temperature()
        z[2, :] = self.get_current()
        z[3, :] = self.get_voltage()

        return z

    def process_data(self, raw_data: np.ndarray) -> LaserData:
        data = LaserData()

        data.time = raw_data[0, :]
        data.temperature = raw_data[1, :]
        data.current = raw_data[2, :]
        data.voltage = raw_data[3, :]

        return data

    def update_ports(self):
        logger.debug("Refreshing ports")
        values = [port.name for port in comports()]  # ('COM12', 'COM13')

        if self.port.get() == "" and len(values) > 0:
            self.port = values[0]
        if hasattr(self, "port_combobox"):
            # self.port_combobox['values'] = values
            self.port_combobox.update_values(values)
            if self.port.get() in values:
                i = values.index(self.port.get())
            else:
                i = 0
            # if i < len(values):
            #    self.port_combobox.current(i)

    def get_parameters(
        self, frame: QWidget, view: ana.View | None
    ) -> List[GUIParameter]:
        parameters = []

        # Serial Port
        self.port_combobox = gui_obj.Combobox(
            frame,
            label="Serial Port:",
            current_value=self.port,
            values=[""],
        )
        port_parameter = GUIParameter(widget=self.port_combobox)
        self.update_ports()

        parameters.append(port_parameter)
        parameters.append(
            GUIParameter(
                widget=gui_obj.ButtonWidget(
                    frame, text="Refresh Ports", action=self.update_ports
                )
            )
        )

        # def make_action(
        #    method: Callable[[Any], None], variable: tkinter.Variable
        # ) -> Callable[[Optional[tkinter.Event]], bool]:
        #    def wrapper(event: tkinter.Event | None = None):
        #        if self.is_laser_on():
        #            method(variable.get())
        #        else:
        #            logger.warning("Couldn't update laser value")
        #        return True

        #    return wrapper

        # Laser current
        self.I_parameter = GUIParameter(
            widget=gui_obj.NumericalValueInput(
                frame,
                from_=self.min_I,
                to=self.max_I,
                value=self.I,
                text="Laser current [mA]:",
                # onchange=make_action(self.set_current, self.I.tk_variable()),
            )
        )
        parameters.append(self.I_parameter)

        # Laser temperature
        self.T_parameter = GUIParameter(
            widget=gui_obj.NumericalValueInput(
                frame,
                from_=self.min_T,
                to=self.max_T,
                value=self.T,
                text="Laser temperature [T]:",
                # onchange=make_action(self.set_temperature, self.T.tk_variable()),
            )
        )
        parameters.append(self.T_parameter)

        parameters += super().get_parameters(frame, view)

        return parameters

    def on_start(self) -> bool:
        try:
            self.serial.port = self.port.get()
            self.serial.baudrate = 115200
            self.serial.open()
            self.config_laser()
        except serialutil.SerialException as e:
            logger.error(
                str(e) + "\nTry changing the serial port and restarting the experiments"
            )
            return False
        if not super().on_start():
            return False
        self.start_laser()
        return True

    def on_stop(self):
        self.stop_laser()
        if self.serial.is_open:
            logger.debug("Closing serial connection to laser controller")
            self.serial.close()
        return super().on_stop()

    def start_laser(self):
        logger.warning("Starting laser. Be carful!")
        self.send_command("lason 1")

    def stop_laser(self):
        self.send_command(f"lason 0")
        logger.warning("Laser off")

    def is_laser_on(self):
        rslt = int(float(self.send_command(f"lason")))
        return rslt == 1

    def convert_R_to_T(self, R: float) -> float:
        """Converts the resistance of the thermoresistor contained in the laser into an actual temperature.

        This method is using the _Steinhart–Hart equation_ (https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation), which converts the resistance of the thermoresistor into its actual temperature.
        The coefficients can be found in the datasheet of the DFB laser diaode.

        Args:
            R (float): Resistance in [Ω]

        Returns:
            float: The temperature in °C of the laser
        """
        A = float(config.get("LASER", "S-H-A"))
        B = float(config.get("LASER", "S-H-B"))
        C = float(config.get("LASER", "S-H-C"))

        T_1 = A + B * np.log(R) + C * np.log(R) ** 3
        return 1 / T_1 - 273.15

    def convert_T_to_R(self, T: float) -> float:
        """Converts a desired temperature of the thermoresistor into its actual resistance

        See `self.convert_R_to_T()` for more infos

        Args:
            T (float): Temperature in [°C]

        Returns:
            float: Resistance of the thermoresistor [Ω]
        """
        A = float(config.get("LASER", "S-H-A"))
        B = float(config.get("LASER", "S-H-B"))
        C = float(config.get("LASER", "S-H-C"))

        T_K = T + 273.15  # Temperature in [K]

        x = 1 / C * (A - 1 / T_K)
        y = np.sqrt((B / (3 * C)) ** 3 + x * x / 4)

        R = np.exp(np.cbrt(y - x / 2) - np.cbrt(y + x / 2))
        return R

    def set_temperature(self, temperature: float):
        """Sets the temperature of the laser"""
        R = self.convert_T_to_R(temperature)
        self.send_command(f"tecon {1}")
        self.send_command(f"rtset {R}")

    def get_temperature(self) -> float:
        """Returns the temperature of the laser"""
        R = self.send_command(f"rtact")
        return self.convert_R_to_T(float(R))

    def set_current(self, I: float):
        """Sets the current of the laser

        Args:
            I (float): Current in [mA]
        """
        if I > self.max_I:
            raise RuntimeError(
                f"Tried to set the current of the laser to an invalid value: {I}mA. The current must be bellow 100mA!"
            )
        self.send_command(f"ilaser {I}")

    def get_current(self) -> float:
        """Get laser current"""
        return float(self.send_command("ilaser"))

    def get_voltage(self) -> float:
        """Returns the voltage of the laser"""
        return float(self.send_command("vlaser"))

    def config_laser(self):
        """Sets a bunch of things to protect the laser"""
        # Temperature protection: Set bounds to the thermoresistor to prevent over heating or under heating
        # Alows to control the temperature between 15°C and 35°C
        T_min = int(self.convert_T_to_R(self.max_T))
        T_max = int(self.convert_T_to_R(self.min_T))

        self.send_command(f"rtmin {T_min}")
        self.send_command(f"rtmax {T_max}")
        self.send_command(f"tprot {1}")

        # Set the values
        self.set_current(self.I.get())
        self.set_temperature(self.T.get())


import snapshot.analysis as ana


class LaserTransmissionAnalysis(ana.DataAnalysis):
    title: str = "Laser Transmission analysis"

    def __init__(self) -> None:
        # Oscilloscope related plots
        self.plot_ch1 = plots.SimplePlot(
            "oscilloscope_channel_1",
            title="Channel 1 (input)",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.CENTERED_AROUND_ZERO,
        )
        self.plot_ch2 = plots.MaximizationPlot(
            "oscilloscope_channel_2",
            title="Channel 2 (output)",
            xlabel="time [s]",
            ylabel="Voltage [V]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.CENTERED_AROUND_ZERO,
        )
        self.graphs = [self.plot_ch1, self.plot_ch2]
        self.plot_ch1_power = plots.SimplePlot(
            "oscilloscope_channel_1_power",
            title="Channel 1 (Power)",
            xlabel="time [s]",
            ylabel="P [mW]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.FROM_ZERO,
        )
        self.plot_ch2_power = plots.MaximizationPlot(
            "oscilloscope_channel_2_power",
            title="Channel 2 (Power)",
            xlabel="time [s]",
            ylabel="P [mW]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.FROM_ZERO,
        )
        self.graphs.append(self.plot_ch1_power)
        self.graphs.append(self.plot_ch2_power)
        logger.dev_warning("Handle is_dB")
        self.is_dB = True
        if self.is_dB:
            ylabel = "T [dB]"
        else:
            ylabel = "T [a.u]"
        self.plot_transmission = plots.SimplePlot(
            "transmission",
            title="Transmission",
            xlabel="time [s]",
            ylabel=ylabel,
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.CENTERED_AROUND_ZERO,
        )

        self.graphs.append(self.plot_transmission)

        # Laser related plots
        self.plot_current = plots.SimplePlot(
            "laser_current",
            title="Laser current",
            xlabel="time [s]",
            ylabel="I [mA]",
            update_axis=True,
        )
        self.plot_temperature = plots.SimplePlot(
            "laser_temperature",
            title="Laser Temperature",
            xlabel="time [s]",
            ylabel="T [°C]",
            update_axis=True,
        )
        self.plot_voltage = plots.SimplePlot(
            "laser_voltage",
            title="Laser Voltage",
            xlabel="time [s]",
            ylabel="U [V]",
            update_axis=True,
        )
        self.graphs.append(self.plot_current)
        self.graphs.append(self.plot_temperature)
        self.graphs.append(self.plot_voltage)
        super().__init__()

    @ana.reader
    def laser_reader(self) -> LaserController:
        ...

    @ana.reader
    def oscilloscope_reader(self) -> OscilloscopeReader:
        ...

    def refresh_plots(self):
        # Oscilloscope plots
        oscilloscope_data = self.oscilloscope_reader().get_data()
        if oscilloscope_data is not None:
            # print(oscilloscope_data.ch1.shape)
            self.plot_ch1.set_data(oscilloscope_data.t, oscilloscope_data.ch1)
            self.plot_ch2.set_data(oscilloscope_data.t, oscilloscope_data.ch2)
            self.plot_ch1_power.set_data(
                oscilloscope_data.t, oscilloscope_data.ch1_power
            )
            self.plot_ch2_power.set_data(
                oscilloscope_data.t, oscilloscope_data.ch2_power
            )
            self.plot_transmission.set_data(
                oscilloscope_data.t, oscilloscope_data.transmission
            )
            # print(min(self.plot_transmission.line.get_data()[1]),max(self.plot_transmission.line.get_data()[1]), self.plot_transmission.ax.get_ylim())
            # print(oscilloscope_data.transmission)

        laser_data = self.laser_reader().get_data()
        if laser_data is not None:
            self.plot_current.set_data(laser_data.time, laser_data.current)
            self.plot_temperature.set_data(laser_data.time, laser_data.temperature)
            self.plot_voltage.set_data(laser_data.time, laser_data.voltage)
        return super().refresh_plots()


class LSRTransmissionAnalysis(LaserTransmissionAnalysis):
    @ana.reader
    def oscilloscope_reader(self) -> OscilloscopeAveragedMeasurements:
        ...


class LaserOnlyAnalysis(ana.DataAnalysis):
    title: str = "Laser Only"
    graphs: List[plots.GraphSet] = []

    def __init__(self) -> None:
        # Laser related plots
        self.plot_current = plots.SimplePlot(
            "laser_current",
            title="Laser current",
            xlabel="time [s]",
            ylabel="I [mA]",
            update_axis=True,
        )
        self.plot_temperature = plots.SimplePlot(
            "laser_temperature",
            title="Laser Temperature",
            xlabel="time [s]",
            ylabel="T [°C]",
            update_axis=True,
        )
        self.plot_voltage = plots.SimplePlot(
            "laser_voltage",
            title="Laser Voltage",
            xlabel="time [s]",
            ylabel="U [V]",
            update_axis=True,
        )
        self.graphs.append(self.plot_current)
        self.graphs.append(self.plot_temperature)
        self.graphs.append(self.plot_voltage)
        super().__init__()

    @ana.reader
    def laser_reader(self) -> LaserController:
        ...

    def refresh_plots(self):
        laser_data = self.laser_reader().get_data()
        if laser_data is not None:
            self.plot_current.set_data(laser_data.time, laser_data.current)
            self.plot_temperature.set_data(laser_data.time, laser_data.temperature)
            self.plot_voltage.set_data(laser_data.time, laser_data.voltage)
        return super().refresh_plots()


class PowerMeterAnalysis(LaserOnlyAnalysis):
    title: str = "Laser Power Measurement"
    graphs: List[plots.GraphSet] = []

    def __init__(self) -> None:
        self.plot_power = plots.MaximizationPlot(
            "Power Meter",
            title="Power Meter",
            xlabel="time [s]",
            ylabel="P [mW]",
            update_axis=True,
            y_limits_update_policy=plots.MaximizationPlot.AxisUpdatePolicy.FROM_ZERO,
        )

        self.graphs.append(self.plot_power)
        super().__init__()

    @ana.reader
    def power_meter_reader(self) -> PowerMeter:
        ...

    def refresh_plots(self):
        power_meter_data = self.power_meter_reader().get_data()
        if power_meter_data is not None:
            # print("Data: ", power_meter_data.power)
            self.plot_power.set_data(power_meter_data.time, power_meter_data.power)
        return super().refresh_plots()
