from sys import prefix
from typing import Iterable, List

# from matplotlib.artist import Artist
# from matplotlib.figure import Figure
import numpy as np

# import matplotlib.pyplot as plt
import time


from labtools.GUI.binding import Binding
import labtools.plots.plot_backend as pb
import labtools.analysis as ana
import labtools.measurement_procedure as mp
from labtools import logger
from config import generalConfig as config
import labtools.plots.plots_implementation as plots

# import src.readers as r
from src.readers import (
    LSRTransmissionAnalysis,
    LaserController,
    OscilloscopeReader,
    LaserTransmissionAnalysis,
    LaserOnlyAnalysis,
    PowerMeterAnalysis,
)
import src.ofdr_reader as ofdr
import src.temperature_readers as temp_ana


class LaserView(ana.View):
    name: str = "Laser Infos"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        transmission = LaserOnlyAnalysis()

        transmission.plot_current.show = True
        transmission.plot_temperature.show = True
        transmission.plot_voltage.show = True

        return [transmission]


class OscilloscopeView(ana.View):
    name: str = "Oscilloscope Raw"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = LaserTransmissionAnalysis()

        # Choose which graphs to take
        analysis.plot_ch1.show = True
        analysis.plot_ch2.show = True

        return [analysis]


class OscilloscopePowerView(ana.View):
    name: str = "Oscilloscope - Power"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = LaserTransmissionAnalysis()

        # Choose which graphs to take
        analysis.plot_ch1_power.show = True
        analysis.plot_ch2_power.show = True

        return [analysis]


class TransmissionView(ana.View):
    name: str = "Transmission"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        transmission = LaserTransmissionAnalysis()

        transmission.plot_transmission.show = True
        transmission.plot_ch2.show = True

        return [transmission]


class TransmissionLSRView(ana.View):
    name: str = "Transmission - LSR"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        transmission = LSRTransmissionAnalysis()

        transmission.plot_transmission.show = True
        transmission.plot_ch2.show = True

        return [transmission]


class PowerMeterView(ana.View):
    name: str = "Power Meter"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        power_meter = PowerMeterAnalysis()

        power_meter.plot_power.show = True

        return [power_meter]


class TransmissionReflectionView(ana.View):
    name: str = "Transmission - Reflection"
    ignore = True

    def get_analysis(self) -> List[ana.DataAnalysis]:
        transmission = LaserTransmissionAnalysis()

        transmission.plot_transmission.show = True
        # transmission.plot_ch2.show = True

        reflection = ofdr.OFDRAnalysis()
        reflection.plot_spectrum.show = True

        return [transmission, reflection]


class OFDRRawView(ana.View):
    name: str = "OFDR Raw Data"
    ignore = True

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = ofdr.OFDRAnalysis()

        analysis.plot_ch1.show = True
        analysis.plot_ch2.show = True

        return [analysis]


class OFDRSpectrumView(ana.View):
    name: str = "OFDR Spectrum"
    ignore = True

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = ofdr.OFDRAnalysis()

        analysis.plot_spectrum.show = True

        return [analysis]


class TemperatureView(ana.View):
    name: str = "Temperature"
    ignore = False

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = temp_ana.TemperatureAnalysis()

        analysis.plot_T.show = True

        return [analysis]


class ClimateChamberView(ana.View):
    name: str = "Climate Chamber"
    ignore = False

    @Binding
    def refresh_delay(self) -> float:
        return 5.0

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = temp_ana.TemperatureAnalysis()

        analysis.plot_T.show = True

        analysis2 = LSRTransmissionAnalysis()

        analysis2.plot_transmission.show = True

        return [analysis, analysis2]


class ClimateChamber2View(ana.View):
    name: str = "Climate Chamber - power"
    ignore = False

    @Binding
    def refresh_delay(self) -> float:
        return 5.0

    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = temp_ana.TemperatureAnalysis()

        analysis.plot_T.show = True

        analysis2 = LSRTransmissionAnalysis()

        analysis2.plot_ch2_power.show = True

        return [analysis, analysis2]


class LaserCharacterization(mp.MeasurementProcedure):
    name: str = "Laser Characterization"
    title: str = "Laser Characterization"
    dirname: str = "laser_characterization"

    def __init__(self) -> None:
        # Creates the plot

        self.plot_LIV = plots.GeneralPlot(
            name="LIV_plot",
            prepare_plot=self.make_plot,
            udpate_data=self.update_plot_data,
        )
        self.graphs = [self.plot_LIV]
        super().__init__()

    def make_plot(self, figure: pb.PlotBackend):
        # ax_right = ax.twinx()
        figure.make_right_axes()

        self.line_power = figure.plot(
            [], [], marker="*", color="b", label="Optical Power"
        )
        self.line_voltage = figure.plot(
            [], [], marker="*", color="r", label="Forward Voltage", right_axis=True
        )

        figure.set_xlabel("I [mA]")
        figure.set_ylabel("P [mW]", color="b")
        figure.tick_params(axis="y", labelcolor="b")
        figure.set_ylabel_right("V [V]", color="r")
        figure.tick_params(axis="y", labelcolor="r", right_axis=True)
        figure.grid()

        # fig, ax = plt.subplots()
        #
        # ax.plot(I, T, label="Temperature")
        #
        # ax.set_xlabel("I [mA]")
        # ax.set_ylabel("T [°C]")
        # ax.grid()

    @ana.reader
    def laser_reader(self) -> LaserController:
        ...

    @ana.reader
    def oscilloscope_reader(self) -> OscilloscopeReader:
        ...

    def get_analysis(self) -> List[ana.DataAnalysis]:
        self.plot_LIV.show = True
        return [self]

    def refresh_plots(self):
        data = self.get_procedure_data()
        if data is not None:
            self.plot_LIV.set_data(data)

    def execute(self):
        """Procedure to characterize the laser"""
        laser_reader = self.laser_reader()
        oscilloscope_reader = self.oscilloscope_reader()
        currents = np.arange(laser_reader.max_I)
        data = np.zeros((4, len(currents)))
        for i in range(len(currents)):
            I = currents[i]
            logger.info(f"Current: {I}mA")
            # Set the current of the laser
            laser_reader.set_current(I)

            # Wait until actualization
            time.sleep(5.0)

            # Detect saturation
            if oscilloscope_reader.detectors_saturated.get():
                logger.warning(
                    f"Detector saturated at I={I:.2f}mA. The procedure is interrupted to protect the detectors"
                )
                break

            # Measure data
            laser_data = laser_reader.get_data()
            oscilloscope_data = oscilloscope_reader.get_data()
            if laser_data is not None and oscilloscope_data is not None:
                V = laser_data.voltage[-1]
                T = laser_data.temperature[-1]
                P_raw = np.mean(oscilloscope_data.ch1)

                data[0, i] = I
                data[1, i] = V
                data[2, i] = P_raw
                data[3, i] = T

            # Update data for live plotting
            self.log_data(data, i)

        return data

    def update_plot_data(self, data: plots.GeneralData) -> Iterable[pb.Line | pb.Text]:
        # Generates the plots
        I = data.data[0, :]
        V = data.data[1, :]
        P_raw = data.data[2, :]
        T = data.data[3, :]

        V[0] = 0

        gain = self.oscilloscope_reader().detector_gain_1.get()  # dB

        P = self.oscilloscope_reader().optical_power(P_raw, gain)

        self.line_power.set_data(I, P)
        self.line_voltage.set_data(I, V)

        return [self.line_power, self.line_voltage]


class InsertionLoss(mp.MeasurementProcedure):
    name: str = "Insertion Loss"
    title: str = "Insertion Loss"
    dirname: str = "beam_splitter_characterization"

    def __init__(self) -> None:
        # Creates the plot

        self.plot_ratio = plots.GeneralPlot(
            name="plot_ratio",
            prepare_plot=self.make_plot,
            udpate_data=self.update_plot_data,
        )
        self.graphs = [self.plot_ratio]
        super().__init__()

    def make_plot(self, figure: pb.PlotBackend):
        # fig, ax = plt.subplots()
        figure.make_right_axes()

        self.line_power_D1 = figure.plot([], [], color="cyan", label="Power in D1")
        self.line_power_D2 = figure.plot([], [], color="b", label="Power in D2")
        self.line_ratio = figure.plot([], [], color="r", label="r", right_axis=True)

        figure.set_xlabel("I [mA]")
        figure.set_ylabel("P [mW]", color="b")
        figure.set_yscale("log")
        figure.tick_params(axis="y", labelcolor="b")
        figure.set_ylabel_right("ratio", color="r")
        figure.tick_params(axis="y", labelcolor="r", right_axis=True)
        figure.grid(axis="y", right_axis=True)
        figure.grid(axis="x")
        figure.legend()

        # self.ax = ax
        # self.ax_right = ax_right

    @ana.reader
    def laser_reader(self) -> LaserController:
        ...

    @ana.reader
    def oscilloscope_reader(self) -> OscilloscopeReader:
        ...

    def get_analysis(self) -> List[ana.DataAnalysis]:
        self.plot_ratio.show = True
        return [self]

    def refresh_plots(self):
        data = self.get_procedure_data()
        if data is not None:
            self.plot_ratio.set_data(data)

    def execute(self):
        """Procedure to characterize the beam splitter"""
        laser_reader = self.laser_reader()
        oscilloscope_reader = self.oscilloscope_reader()
        currents = np.arange(laser_reader.max_I)
        data = np.zeros((5, len(currents)))

        for i in range(len(currents)):
            I = currents[i]
            logger.info(f"Current: {I}mA")
            # Set the current of the laser
            laser_reader.set_current(I)

            # Wait until actualization
            time.sleep(5.0)

            # Detect saturation
            if oscilloscope_reader.detectors_saturated.get():
                logger.warning(
                    f"Detector saturated at I={I:.2f}mA. The procedure is interrupted to protect the detectors"
                )
                break

            # Measure data
            laser_data = laser_reader.get_data()
            oscilloscope_data = oscilloscope_reader.get_data()
            if laser_data is not None and oscilloscope_data is not None:
                T = laser_data.temperature[-1]
                D1_raw = np.mean(oscilloscope_data.ch1)
                D2_raw = np.mean(oscilloscope_data.ch2)
                gain_1 = oscilloscope_reader.detector_gain_1.get()
                gain_2 = oscilloscope_reader.detector_gain_2.get()

                data[0, i] = I
                data[1, i] = D1_raw
                data[2, i] = D2_raw
                data[3, i] = T
                data[4, i] = self.ratio(
                    oscilloscope_reader.optical_power(D1_raw, gain_1),
                    oscilloscope_reader.optical_power(D2_raw, gain_2),
                )

            # Update data for live plotting
            self.log_data(data, i)

        return data

    def ratio(
        self, P1: float | np.ndarray, P2: float | np.ndarray
    ) -> float | np.ndarray:
        return P1 / (P1 + P2)

    def update_plot_data(self, data: plots.GeneralData) -> Iterable[pb.Line | pb.Text]:
        # Generates the plots
        I = data.data[0, :]
        D1_raw = data.data[1, :]
        D2_raw = data.data[2, :]
        T = data.data[3, :]
        ratio = data.data[4, :]

        gain_1 = self.oscilloscope_reader().detector_gain_1.get()  # dB
        gain_2 = self.oscilloscope_reader().detector_gain_2.get()  # dB

        P1 = self.oscilloscope_reader().optical_power(D1_raw, gain_1)
        P2 = self.oscilloscope_reader().optical_power(D2_raw, gain_2)

        self.line_power_D1.set_data(I, P1)
        self.line_power_D2.set_data(I, P2)
        self.line_ratio.set_data(I, ratio)

        return [self.line_power_D1, self.line_power_D2, self.line_ratio]
