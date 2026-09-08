from typing import List, Tuple

import numpy as np

path = r"C:\Users\dja\OneDrive - CSEM S.A\Python\snapshot\saved_outputs\data\beam_splitter_characterization_with_fibers\measurements.npy"

data = np.load(path)

print(data[:, 60])


exit()

### This code is to read the different files that import a given module
from pathlib import Path
import ast

root = Path("snapshot")

for py_file in root.rglob("*.py"):
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except Exception:
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "matplotlib" or alias.name.startswith("matplotlib."):
                    print(py_file)
                    break

        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "matplotlib" or node.module.startswith("matplotlib.")
            ):
                print(py_file)
                break

exit()


import numpy as np
import matplotlib.pyplot as plt
import os
import re

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import matplotlib as mpl

from snapshot.utils import resample


class MyProperty:
    def __init__(self, fget=None, fset=None):
        self.fget = fget
        self.fset = fset
        self.__name__ = fget.__name__ if fget else None

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.fget is None:
            raise AttributeError("Unreadable attribute")
        return self.fget(instance)

    def __set__(self, instance, value):
        if self.fset is None:
            raise AttributeError("Can't set attribute")
        self.fset(instance, value)

    def getter(self, fget):
        return type(self)(fget, self.fset)

    def setter(self, fset):
        prop = type(self)(self.fget, fset)
        prop.__name__ = self.__name__
        return prop


class Test:
    @MyProperty
    def test(self) -> str:
        return self._value

    @test.setter
    def test(self, value: str):
        print("Setter!!")
        self._value = value


t = Test()
t.test = "Hello"
print(t.test)  # Hello

exit()


d = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 4.0, 4.0])

print(d)
r = d.reshape((4, 3))
print(r)
print(np.mean(r, axis=1))
print("TEst")


print(resample(d, 3), np.array([1.0, 2.0, 3.0, 4.0]))
print(resample(d, 4), np.array([1.25, 2.5, 3.75]))
print(
    resample(d, 5),
    np.array([1.4, 23 / 7]),
)
# exit()


folder = "C:\\Users\\dja\\OneDrive - CSEM S.A\\Python\\snapshot\\saved_outputs\\temperature_resistance\\2025_05_12_FIRST_GLUING_TEST\\blowing_1"
transmission_folder = "transmission_measurement"

transmission_path = os.path.join(folder, transmission_folder)

DATA_AVERAGED = False


def read(path: str):
    aggregated_path = os.path.join(path, "aggregated.npy")
    if os.path.exists(aggregated_path):
        return np.load(aggregated_path)

    l = os.listdir(path)

    def compare(x):
        match = re.search("output_(.*).npy", x)
        if match:
            return int(match.group(1))
        else:
            return 0

    l.sort(key=compare)

    data = np.array([])
    print("Start reading...")
    for f in l:
        d = np.load(os.path.join(path, f))
        if DATA_AVERAGED:
            m = np.mean(d, axis=1).reshape((d.shape[0], 1))
        else:
            m = d
        if data.shape[0] == 0:
            data = m
        else:
            # data = np.append(data, d, axis=1)
            data = np.append(data, m, axis=1)

    print("End reading!")

    np.save(aggregated_path, data)
    return data


def optical_power(voltage, gain):
    responsivity = 1.05  # A/W -> for 1550nm wavelength

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

    if gain not in gain_to_tg_scale:
        raise ValueError(
            f"Gain {gain} not supported. Choose from {list(gain_to_tg_scale.keys())}"
        )

    tg_scale = gain_to_tg_scale[gain]

    p_opt = voltage / (responsivity * tg_scale)

    return p_opt * 1000


data = read(transmission_path)
data = resample(data, 50000)
print(data.shape)

# Data analysis
t = data[0, :]
ch1 = data[1, :]
ch2 = data[2, :]

ch1_power = 10 * optical_power(ch1, "20")
ch2_power = optical_power(ch2, "40") * 10.0 / 9.0

transmission = 10 * np.log10(ch2_power / ch1_power)

mplstyle.use("fast")

mpl.rcParams["path.simplify"] = True
mpl.rcParams["path.simplify_threshold"] = 0.5

fig, ax = plt.subplots()
# ax_right = ax.twinx()

# ax_right.plot(t, ch2_power, label="ch2")
# ax_right.plot(t, ch1_power, label="ch1")
ax.plot(
    t, transmission, label="transmission", color="red", rasterized=True, marker=None
)
ax.axvline(137, linestyle="--", color="black")
ax.axvline(21, linestyle="--", color="black")

ax.set_xlabel("Time [s]")
ax.set_ylabel("Transmission [dB]")
# ax_right.set_ylabel("Voltage [V]")

ax.legend(loc="upper right")
# ax_right.legend()

plt.show()
