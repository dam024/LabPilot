from __future__ import annotations
from typing import List, Tuple
import numpy as np
from PySide6.QtWidgets import QWidget

from scipy.ndimage import gaussian_filter
#import scipy.signal as sp
from scipy.signal import butter, filtfilt, hilbert, welch
from scipy.interpolate import interp1d
from scipy.fft import rfft
import zmq
import struct

import snapshot.DataReceiver as dr
import snapshot.analysis as ana
import snapshot.GUI.parameters as parameters
from snapshot.GUI.binding import Binding
import snapshot.GUI.objects as objects
from snapshot.data_management.measurement_information import MeasurementInfos
from snapshot.plots.plots import GraphSet
import snapshot.plots.plots_implementation as plots
from config import generalConfig as config
from snapshot import logger, utils


class OFDRData(dr.ProcessedData):
    t: np.ndarray
    ch1: np.ndarray
    ch2: np.ndarray
    z: np.ndarray
    spectrum: np.ndarray


class OFDRReader(dr.LiveDataReader[OFDRData]):
    name: str = "OFDR"
    dirname: str = "OFDR_data"

    nb_chan: int = 2
    devide_sampling: int = 1
    # Size of the data sent
    data_size: int = 2**14
    # Frequency of the clock
    clock: float = 125e6 / 2**4

    # Declaration of a few constants
    FSR = 1.916465 * 1e9  # [Hz]
    c = 3e8  # [m/s]
    n = 1.458  # refractive index of the fiber
    FACTOR = 2000 / 2**14

    TSTART = 0.71861
    TENDS = [3.84652, 8.10161, 12.35707, 16.61255]
    MIN_Z = 0.0
    MAX_Z = 15.0

    FORMAT = "262144h"

    def __init__(self, refresh_delay: float = 0):
        super().__init__(refresh_delay)

    @Binding
    def IP(self) -> str:
        return config.get("OFDR", "IP")

    @Binding
    def PORT(self) -> str:
        return config.get("OFDR", "PORT")

    @Binding
    def center_z(self) -> float:
        return (self.MIN_Z + self.MAX_Z) / 2

    @Binding
    def length_z(self) -> float:
        return self.MAX_Z - self.MIN_Z

    def get_parameters(self, frame: QWidget) -> List[parameters.GUIParameter]:
        l: List[parameters.GUIParameter] = []

        # IP address
        ip_widget = objects.Entry(
            frame, label="IP Address:", text=self.IP
        )
        # ip_widget.widget.insert(-1, self.IP.get())
        ip_address = parameters.GUIParameter(widget=ip_widget)
        l.append(ip_address)

        # Add parameter for min_z
        min_z_parameter = parameters.GUIParameter(
            widget=objects.NumericalValueInput(
                frame,
                from_=self.MIN_Z,
                to=self.MAX_Z,
                value=self.center_z,
                text="Center z [m]:",
                increment=0.01,
            )
        )
        l.append(min_z_parameter)
        # Add parameter for max_z
        max_z_parameter = parameters.GUIParameter(
            widget=objects.NumericalValueInput(
                frame,
                from_=self.MIN_Z,
                to=self.MAX_Z,
                value=self.length_z,
                text="Length z [m]:",
                increment=0.01,
            )
        )
        l.append(max_z_parameter)
        l += super().get_parameters(frame)
        return l

    def pull_data(self) -> np.ndarray | None:
        if self.socket is None:
            return None
        try:
            recv = self.socket.recv()
            if recv is None:
                return np.array([])
            data = struct.unpack(self.FORMAT.encode("utf-8"), recv)
            return np.array(list(data)) * self.FACTOR
        except Exception as e:
            logger.warning(f"No data received from OFDR: {e}")
            return None

    def init_communication_zmq(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, "".encode("utf-8"))
        self.socket.setsockopt(zmq.CONFLATE, 1)
        self.socket.RCVTIMEO = 5000
        self.socket.connect("tcp://" + self.IP.get() + ":" + str(self.PORT.get()))

    def on_start(self):
        if not super().on_start():
            return False

        try:
            logger.debug("Attempting OFDR connection...")
            self.init_communication_zmq()
            # self.socket = socket.socket(
            #    socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP
            # )
            # self.socket.settimeout(10.0)
            # self.socket.connect((self.IP.get(), self.PORT))
            logger.info("OFDR connection successful!")
        except:
            self.socket = None
            logger.error(f"OFDR connection faild ({self.IP.get()}:{self.PORT})")
            return False
        return True

    def on_stop(self):
        if self.socket is not None:
            # self.socket.send(b"sock_closed\n")
            self.socket.close()
            logger.info("OFDR Disconnected")
        return super().on_stop()

    def send(self, command: str):
        if self.socket is not None:
            logger.debug(f"Socket command: {command}")
            command = command + "\n"
            self.socket.send(command.encode())

    def process_data(self, raw_data: np.ndarray) -> OFDRData:
        ch1 = raw_data[0 :: self.nb_chan * int(self.devide_sampling)]
        ch2 = raw_data[1 :: self.nb_chan * int(self.devide_sampling)]
        t00 = np.linspace(
            0, len(ch1) / (self.clock * 10**-3) * int(self.devide_sampling), len(ch1)
        )

        nbrep = len(self.TENDS)  # Number of periods in the file
        ts1 = self.TSTART
        te1 = self.TENDS[0]
        idx1 = np.where((t00 >= ts1) & (t00 <= te1))[0]
        nt = len(idx1)

        # Sampling time
        dt = np.median(np.diff(t00)) * 1e-3  # unit conversion

        # To save the spectrums at the end
        spectrum_save: np.ndarray = np.array([])
        z: np.ndarray = np.array([])

        for j in range(nbrep):
            te2 = self.TENDS[j]
            idx2e = np.argmin(abs(t00 - te2))
            idx2 = np.arange(idx2e - nt, idx2e)

            if j == 0:
                idxcut = idx1
            else:
                idxcut = idx2

            # Get the reduced data
            # t = ch1[i_min:i_max, 0]
            # ref = ch1[i_min:i_max, 1]
            # signal = ch2[i_min:i_max, 1]
            t = t00[idxcut] * 1e-3  # [s] # * 1e3
            ref = ch1[idxcut]  # [V] * factor
            signal = ch2[idxcut]  # [V] * factor
            n_time_steps = len(t)  # Number of time steps in our signal

            # Remove DC part of the signal
            ref -= np.mean(ref)
            signal -= np.mean(signal)

            ############  SIGNAL FILTERING  ##############
            # Apply a filter to the data to smooth the curves
            sigma = 1
            ref = gaussian_filter(ref, sigma=sigma)
            signal = gaussian_filter(signal, sigma=sigma)

            # Apply a low pass filter for the k-space interferogram
            # Our goal is to remove high frequencies that are 50kHz under the Nyquist frequency.
            fc = (
                1 / dt * 1 / 2
            )  # Nyquist frequency of the signal (= half the sampling frequency)
            fl = 50e3  # [kHz], since fc is in [kHz], as dt is in [ms]. This is the
            # Apply a Butterworth filter. This filer has the property of being very flat at the pass band. It will drop the frequencies higher than the specified frequency. https://en.wikipedia.org/wiki/Butterworth_filter#:~:text=to%20be%20rejected.-,Transfer%20function,-%5Bedit%5D
            # Here, we take a filter of order 4, with a cut-off frequency of 50 in the units of the Nyquist frequency (According to the doc., this is what we need to apply it correctly)
            b, a = butter(4, fl / fc, btype="lowpass")
            ref = filtfilt(b, a, ref)

            ##############  Analysis of the k-space interferogram  ###############
            # Compute the Hilbert transform of the signal and then the instantaneous_frequency according to the documentation of sp.hilbert()
            h: np.ndarray = hilbert(ref)
            instantaneous_phase = np.unwrap(np.angle(h))
            instantaneous_frequency = 1 / (2 * np.pi) * self.FSR * instantaneous_phase
            # plot_signal(t, instantaneous_frequency, "test")

            ############## Adapting the range  ################
            # The goal of this section is to reduce the range of detection to get rid of the border effect and avoid going too far away, since this doesn't make sense.

            off = 100
            # t = t[off:-off]
            # t   -= t[0]
            # vref = ref[off:-off]
            vsig = signal[off:-off]
            vt = instantaneous_frequency[off:-off]
            vt -= vt[0]

            # match the data points, vt cut
            dvrangeT = 77 + 0 * 68  # [GHz]
            vt_cut = dvrangeT * 1e9  # [Hz]
            idxpts = np.where(vt <= vt_cut)[0]
            t = t[idxpts]
            vt = vt[idxpts]
            # vref = vref[idxpts]
            vsig = vsig[idxpts]
            # dvrange = vt[-1] * 1e-9  # GHz
            # res = c / (2 * n * dvrange * 1e9) * 1e3  # mm

            ######## Properties and signal interpolation
            v_cut = vt_cut
            # v_interpolation = np.linspace(0, v_cut, n_time_steps)
            # Computes the frequency interval in the linear frequency
            dv = (vt[-1] - vt[0]) / (
                n_time_steps - 1
            )  # np.median(np.diff(v_interpolation))
            # From the frequency interval, one can compute the size of a time interval in the reciprocal space.
            # The delay time is twice the travel time to a given distance z, giving one 1/2 factor
            # The Fourier transform is taken from -v_cut/2 to v_cut/2, giving the other 1/2 factor
            tc = 1 / dv / 2 * 0.5
            # tk = np.linspace(-tc, tc, n_time_steps)
            max_z = tc * self.c / self.n
            tuning_rate = (vt[-1] - vt[0]) / (t[-1] - t[0])
            # print(f"tuning_rate: {tuning_rate*1e-9}GHz/s")

            #####################  Signal interpolation  #####################
            # Interpolate the signal to correct the non linearity of the frequency sweep.
            # In a few words, the way it works is that we define the signal U(vt), where vt is the instantaneous frequency.
            # Then, we define a linear frequency sweep vt_linear and evaluate U(vt_linear) and take it as our signal to fourier transform.
            vt_linear = np.linspace(vt[0], vt[-1], n_time_steps)
            intpl = interp1d(vt, vsig, "linear")
            interpolated_signal = intpl(vt_linear)

            # Apply FFT to obtain the final spectrum
            spectrum = rfft(interpolated_signal)
            # FFT using Welch method. Welch method computes the power spectral density and gives a smuther curve as a FFT.
            power2 = int(np.log2(n_time_steps)) + 5
            Nzp = 2**power2
            vintplzp = np.zeros(Nzp)
            vintplzp[:n_time_steps] = interpolated_signal
            # fwelch, spectrum = sp.welch(
            #    vintplzp, 1/dv, nperseg=Nzp, average="mean", scaling="density"
            # )
            fwelch, spectrum = welch(
                vintplzp, dv, nperseg=Nzp, average="mean", scaling="density"
            )

            z = np.linspace(0, max_z, len(spectrum))  # Sanghoon method
            # print(fwelch / tuning_rate * c / n, z)
            z = (
                fwelch / tuning_rate * self.c / self.n
            )  # My method... Seems more logical to do it that way...
            # exit()

            # print(f"Sampling time: {tc}s, {fwelch[-1]/tuning_rate}s")
            # exit()

            # Save the spectrum for later analysis
            if "spectrum_save" not in vars() or j == 0:
                spectrum_save = np.zeros((nbrep, len(spectrum)), dtype=complex)

            spectrum_save[j, :] = spectrum

        # Compute the avarage of the signals measured
        spectrum_avg = np.average(spectrum_save, axis=0)

        # Make data
        data = OFDRData()

        data.t = t00
        data.ch1 = ch1
        data.ch2 = ch2
        data.z = z
        data.spectrum = spectrum_avg

        return data


class OFDRAnalysis(ana.DataAnalysis):
    title: str = "OFDR"

    def __init__(self) -> None:
        self.plot_ch1 = plots.SimplePlot(
            "OFDR_channel_1",
            title="Channel 1 (raw)",
            xlabel="time [s]",
            ylabel="Voltage [mV]",
            update_axis=True,
        )
        self.plot_ch2 = plots.SimplePlot(
            "OFDR_channel_2",
            title="Channel 2 (raw)",
            xlabel="time [s]",
            ylabel="Voltage [mV]",
            update_axis=True,
        )
        self.graphs = [self.plot_ch1, self.plot_ch2]
        self.plot_spectrum = plots.SimplePlot(
            "Reflection_spectrum",
            title="Reflection Spectrum",
            xlabel="z [m]",
            ylabel="Reflection spectrum [$V^2/s$]",
            yscale="log",
            update_axis=True,
        )
        self.graphs.append(self.plot_spectrum)
        super().__init__()

    @ana.reader
    def ofdr_reader(self) -> OFDRReader:
        ...

    def zoom_spectrum(
        self, z: np.ndarray, spectrum: np.ndarray, center_z: float, length_z: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        diss = center_z - length_z / 2
        dise = center_z + length_z / 2
        cut = np.where((z >= diss) & (z <= dise))[0]
        z_ret = z[cut]
        spectrum_avg_ret = abs(spectrum[cut])
        return z_ret, spectrum_avg_ret

    def refresh_plots(self):
        ofdr_data = self.ofdr_reader().get_data()
        if ofdr_data is not None:
            self.plot_ch1.set_data(ofdr_data.t, ofdr_data.ch1)
            self.plot_ch2.set_data(ofdr_data.t, ofdr_data.ch2)

            # Cut the data to only show a reduced element of the spectrum
            z = ofdr_data.z
            spectrum_avg = ofdr_data.spectrum
            center_z = self.ofdr_reader().center_z.get()
            length_z = max(
                self.ofdr_reader().length_z.get(), z[5]
            )  # Take at least 5 values
            z, spectrum_avg = self.zoom_spectrum(z, spectrum_avg, center_z, length_z)

            self.plot_spectrum.set_data(z, spectrum_avg)
        return super().refresh_plots()

    def plot_generation(self, infos: MeasurementInfos) -> List[GraphSet]:
        """Allows for the generation of extra plots during the post processing"""
        new_plots: List[GraphSet] = super().plot_generation(infos)
        ofdr_data = self.ofdr_reader().get_data()

        if ofdr_data is not None:
            z = ofdr_data.z
            spectrum = ofdr_data.spectrum

            # Generate all the plots with different center and z lengths
            spectrum_zoom_1 = self.plot_spectrum.copy("Reflection_spectrum_zoom_1")
            z, spectrum = self.zoom_spectrum(z, spectrum, 1.58, 1.5)
            spectrum_zoom_1.set_data(z, spectrum)
            spectrum_zoom_1.ax.set_title(f"Reflection spectrum: {infos["title"]}")
            new_plots.append(spectrum_zoom_1)

            spectrum_zoom_2 = self.plot_spectrum.copy("Reflection_spectrum_zoom_2")
            z, spectrum = self.zoom_spectrum(z, spectrum, 1.58, 0.5)
            spectrum_zoom_2.set_data(z, spectrum)
            spectrum_zoom_2.ax.set_title(f"Reflection spectrum: {infos["title"]}")
            new_plots.append(spectrum_zoom_2)

            spectrum_zoom_3 = self.plot_spectrum.copy("Reflection_spectrum_zoom_3")
            z, spectrum = self.zoom_spectrum(z, spectrum, 1.58, 0.12)
            spectrum_zoom_3.set_data(z, spectrum)
            spectrum_zoom_3.ax.set_title(f"Reflection spectrum: {infos["title"]}")
            new_plots.append(spectrum_zoom_3)

        return new_plots
