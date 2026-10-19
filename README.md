# LabPilot

Automatic measurement interface for scientific experiments.

LabPilot is a Python-based data acquisition system designed for automated measurements using laboratory instruments. It provides a flexible, modular architecture for connecting to various instruments through a unified API. The system supports both live data acquisition and replay mode for analyzing previously recorded measurements.

## Key Features

- **Multi-Instrument Support**: Implement instrument-specific code and leave the rest to LabPilot
- **Live Data Acquisition**: Continuous data collection with configurable sampling rates and refresh delays
- **Replay Mode**: Load and visualize previously recorded measurements with interactive plots
- **Flexible Architecture**: Plugin-based design with abstract base classes (Reader, View, Analysis) for easy customization
- **Persistent State**: All user settings are saved across application sessions
- **Recording System**: Automatic data recording with structured folder organization
- **GUI Binding System**: Qt-compatible reactive variables for seamless GUI updates

## Installation

> **Note**: These commands are executed using Git Bash on Windows. On macOS/Linux, use standard bash/zsh commands.

```bash
pip install labpilot
```

**Required Packages:**
- `numpy`, `scipy` - Numerical computing
- `matplotlib`, `pyqtgraph` - Data visualization
- `PySide6` - Qt GUI framework
- Other less critical packages

## Project creation

LabPilot provides a set of tools to ease the creation of a project. A few tools are described here. 

### 1. List the available tools

To list all the available tools and access their description, run the following command:

```bash
labpilot -h
```

### 2. Initialization of an example project

LabPilot provides an example, ready-to-go sample project. This example project highlights the main features of LabPilot. In an empty folder, run the following command:

```bash
labpilot init
```

## Configuration

Edit the `config.ini` file to configure your instruments. When you initialize the example project, that file will contain the following code:

```ini
[GENERAL]

# Output directory where to store all the data. The path is relative to the current working directory
output_directory=outputs
# Location where to save the plots
plots_output_dir=plots
# Where data are placed once a measurement is done
data_analysis_folder=saved_outputs

# File containing the extra code definition. This is the entry point of the extension – Make sure you define all your views in this file, or make them available there! Otherwise, they won't be discovered!
extra_code = src/views.py

# Indicates if errors must be shown using an alert
error_alert = true
[QT]
# Indicates the frequency at which the plots are refreshed [ms]
plot_refresh_rate = 500
```

## Running the Application

### Live Data Acquisition Mode

Start the application in live data acquisition mode:

```bash
python main.py start -c config.ini
```

This mode starts the main GUI that allows you to connect to your instruments and begin continuous data acquisition. See bellow for more details

### Replay Mode (Disk Data)

Once data has been recorded, replay it without connecting to instruments:

```bash
python main.py start -d -c config.ini
```

The `-d` flag uses data stored on disk, allowing you to:
- Select recorded data folders
- Replay and visualize measurements interactively
- Zoom and save plot views

### Help

For command-line help:

```bash
python main.py -h
```

## Recording Feature

LabPilot automatically records measurement data during live acquisition. To start a recording, you must first `Start Experiments` and you will be able to use the `Record` button

**Important**: The recording feature records only the raw data of your readers used in the selected view. In case of a problem, you will have access to the raw data and may be able to mitigate it.

### How Recording Works

LabPilot's recording system saves data directly from each instrument into structured folders. Each `LiveDataReader` saves its data independently.

**Recording Process:**

1. **Data Collection**: Each `LiveDataReader` continuously collects data from its instrument
2. **Data Aggregation**: Data is aggregated to maintain a maximum number of rows (`max_rows` attribute) in memory and generate the plots live
3. **File Saving**: Raw data is saved directly to `output_%.npy` files within each reader's folder. Each file contains one single recording from an instrument, for speed and disk space optimization

**Folder Structure:**

```
output_directory/                   # `output_directory` value in the [GENERAL] section of your config file
└── <recording_name>/
    ├── info.json                    # Recording metadata (at root)
    ├── sensor1/
    │   ├── output_0.npy            # First data block from sensor 1
    │   ├── output_1.npy            # Second data block
    │   └── ...                     # Additional data blocks
    └── sensor2/
        ├── output_0.npy            # First data block from sensor 2
        ├── output_1.npy
        └── ...
```

At the root of the recording folder, you have:
- `info.json` - Contains recording metadata, configuration, timestamps, and instrument parameters
- **Reader subfolders** - Each reader (e.g., `sensor1/`, `sensor2/`) contains its own `output_*.npy` files

The `info.json` file contains:
- Recording configuration (instrument settings, sampling rates)
- Timestamps (recording start time and duration)
- Instrument parameters (IP addresses, gain settings, coefficients)
- Measurement settings (view name, parameters, etc.)
- List of all readers that contributed data

**Important Notes:**
- Each reader's data is saved independently
- Files are named `output_0.npy`, `output_1.npy`, etc., for each reader
- The numbering starts at 0 and increments with each save operation
- If a reader doesn't collect data, its folder may not exist or contain files
- The `max_rows` attribute controls how many rows are kept in memory, but do not influence the size of data that are saved. Every data recorded is saved into these files. 

## Reading Recorded Data

There are two ways to read recorded data: using processed data from readers, or directly from the raw numpy files. Processed data is recommended for most use cases.

### Option 1: Using Processed Data (Recommended)

The processed data approach uses the reader classes to load and convert data into structured formats. This is the recommended method because it provides clean, well-defined data objects with proper field names and types.

**Example: Loading Data from Multiple Readers**

This example demonstrates loading data from various instruments. Each reader handles its own data loading and processing, returning a structured `ProcessedData` object.

```python
"""
Loading Recorded Data from LabPilot
===================================

This script demonstrates how to load recorded data from LabPilot recordings
using the reader classes. It shows how to:
1. Set up readers without connecting to instruments
2. Load data from a recording folder
3. Retrieve processed data from each reader
4. Access the structured data fields

Usage:
    python load_recording_data.py <path-to-recording>

Example:
    python load_recording_data.py /path/to/my_recording

Authors: Damien Jaccoud
Date: 2026-09-01
"""

from pathlib import Path
import numpy as np

# Import the reader classes
# ====================================
# Readers are the core components that handle data acquisition and processing.
# Each reader corresponds to one instrument.
import src.readers as r
import src.temperature_readers as tr


def load_recording_data(recording_path: Path):
    """
    Load processed data from a LabPilot recording.
    
    This function sets up reader objects, loads their data from the recording
    folder, and returns the processed data objects with structured fields.
    
    Args:
        recording_path: Path to the recording folder (containing info.json at root)
                        Example: /path/to/my_recording
    
    Returns:
        A tuple of processed data objects, one for each reader that collected data.
        The order depends on the reader implementation.
    
    Example:
        >>> data = load_recording_data(Path("/path/to/recording"))
        >>> data[0].time.shape  # View time array shape
    """
    
    # -------------------------------------------------------------------------
    # Step 1: Instantiate all readers
    # -------------------------------------------------------------------------
    
    # Create a voltage sensor reader
    # This reader will handle data from a voltage/oscilloscope instrument
    voltage_reader = r.OscilloscopeAveragedMeasurements()
    
    # Create a laser controller reader
    # This reader will handle data from a temperature-controlled device
    laser_reader = r.LaserController()
    
    # Create a temperature/humidity reader
    # This reader will handle data from environmental sensors
    temp_reader = tr.TemperatureHumidityReader()
    
    # -------------------------------------------------------------------------
    # Step 2: Setup readers (without connecting to instruments)
    # -------------------------------------------------------------------------
    
    # Call _setup() on each reader to prepare them for data loading.
    # We pass None as the argument because we have no GUI interface 
    # and want to load from disk.
    voltage_reader._setup(None)
    laser_reader._setup(None)
    temp_reader._setup(None)
    
    # -------------------------------------------------------------------------
    # Step 3: Load the recording configuration
    # -------------------------------------------------------------------------
    
    # The RecordingInfos class parses the info.json file at the root of the
    # recording folder to extract configuration parameters.
    
    from labpilot.data_management.measurement_information import RecordingInfos
    
    # Create a RecordingInfos instance
    infos = RecordingInfos()
    
    # Load the recording configuration
    # 
    # Arguments:
    #   - path: Path to the recording (string, not Path object)
    #   - apply_parameters: Whether to apply the parameters to the readers (True, because we want to apply the parameters of the recording to perform a correct data processing...)
    infos.load(str(recording_path), True)
    
    # You can access configuration from infos:
    # print(f"Recording: {infos.recording_name}")
    # print(f"Parameters: {infos.parameters}")
    
    # -------------------------------------------------------------------------
    # Step 4: Load raw data from each reader
    # -------------------------------------------------------------------------
    
    # Call load_data() on each reader to load their respective data files.
    # Each reader looks for files in its own subfolder (sensor1/, sensor2/, etc.)
    # 
    # The reader automatically:
    #   - Finds all output_*.npy files in its folder
    #   - Loads them into memory
    #   - Keeps track of the maximum number of rows (max_rows attribute)
    voltage_reader.load_data(str(recording_path))
    laser_reader.load_data(str(recording_path))
    temp_reader.load_data(str(recording_path))
    
    # You can check if data was loaded:
    # print(f"Voltage sensor has data: {voltage_reader.has_data}")
    # print(f"Laser controller has data: {laser_reader.has_data}")
    # print(f"Temperature sensor has data: {temp_reader.has_data}")
    
    # -------------------------------------------------------------------------
    # Step 5: Retrieve processed data from each reader
    # -------------------------------------------------------------------------
    
    # Call get_data() on each reader to retrieve the processed data object.
    # 
    # The reader returns:
    #   - The latest data if available
    #   - Or the aggregated data if no individual data is available
    # 
    # Returns a ProcessedData subclass (e.g., OscilloscopeData, LaserData)
    voltage_data = voltage_reader.get_data()
    if voltage_data is None:
        # If get_data() returned None, return an empty data object of the correct type
        voltage_data = r.OscilloscopeData()
    
    laser_data = laser_reader.get_data()
    if laser_data is None:
        laser_data = r.LaserData()
    
    temp_data = temp_reader.get_data()
    if temp_data is None:
        temp_data = tr.TemperatureData()
    
    # Return the processed data objects
    # You can now access their fields:
    # print(voltage_data.time)  # Time array from voltage sensor
    # print(laser_data.temperature)  # Temperature from laser controller
    
    return voltage_data, laser_data, temp_data


# Example usage (uncomment when running):
# if __name__ == "__main__":
#     # Load data from a recording
#     recording = Path("/path/to/your/recording")
#     
#     # Load the data
#     voltage_data, laser_data, temp_data = load_recording_data(recording)
#     
#     # Access the data fields
#     print(f"Voltage sensor time range: {voltage_data.time.min()} to {voltage_data.time.max()}")
#     print(f"Laser temperature: {laser_data.temperature}")
#     print(f"Temperature probe: {temp_data.temperature}")
```

**What You Get:**

In this example, each reader returns a `ProcessedData` subclass that contains:

- **OscilloscopeData**: Time array, channel voltages, power measurements, transmission
- **LaserData**: Temperature, current, voltage
- **TemperatureData**: Temperature from environmental sensor

**Accessing Data Fields:**

```python
voltage_data, laser_data, temp_data = load_recording_data(recording_path)

# Time array (common to all instruments)
time_array = voltage_data.time

# Voltage sensor channel 1 voltage
ch1_voltage = voltage_data.ch1

# Laser temperature
laser_temp = laser_data.temperature

# Power meter reading
# power = power_meter_data.power
```

**Data Structure:**

Each `ProcessedData` object implements the `to_numpy()` method to convert to a numpy array, if you prefer working with numpy arrays:

```python
# Convert to numpy array
numpy_data = voltage_data.to_numpy()
print(f"Shape: {numpy_data.shape}")  # (n_time_points, n_fields)
print(f"Columns: {numpy_data.shape[1]}")  # Number of fields/columns
```

The columns correspond to each field defined in the dataclass. Please, refer to the corresponding implementation for more information

### Option 2: Using Raw Data Directly

Read aggregated raw data using `utils.read_data()`:

```python
from labpilot.utils import read_data
from pathlib import Path

# Path to an output file (any output_*.npy file works)
recording_path = Path("/path/to/recording")
output_file = recording_path / "sensor1" / "output_0.npy"

# Read aggregated data
raw_data = read_data(str(output_file))
```

**Understanding the Data Structure:**

The `read_data()` function:
1. Checks if an aggregated `data.npy` file exists
2. If not, loads and concatenates all `output_*.npy` files
3. Saves the aggregated data to `data.npy`
4. Optionally zips and deletes original files

**Finding Column Definitions:**

To understand what each column in the final array represents:
1. Check the `pull_data()` method of the specific instrument. The array returned by this method has the same structure as the one you will get from `read_data()`
2. Look at the `process_data()` method to see how raw data is converted to the final format
3. Each column corresponds to a field/property in the `ProcessedData` dataclass

Example for voltage sensor data:
```python
# OscilloscopeData has these fields:
# - t: time array
# - ch1: channel 1 voltage
# - ch2: channel 2 voltage
# - ch1_power: channel 1 power
# - ch2_power: channel 2 power
# - transmission: calculated transmission
```

## Important Concepts

### Reader

The `Reader` is a subclass of `LiveDataReader` that manages data acquisition for a specific instrument.

**Key Responsibilities:**
- Implement `pull_data()`: Fetch raw data from the instrument
- Implement `process_data()`: Convert raw data to a structured format
- Handle `on_start()` and `on_stop()`: Lifecycle management
- Manage data aggregation and queuing
- Manage threads for optimized data recording and speed

**Example:**

```python
from labpilot.DataReceiver import ProcessedData, LiveDataReader
import numpy as np


class MyCustomData(ProcessedData):
    """Custom processed data class."""
    time: np.ndarray
    voltage: np.ndarray
    temperature: float

class MyInstrumentReader(LiveDataReader[MyCustomData]):
    name: str = "My Instrument"
    dirname: str = "my_instrument"
    refresh_delay: float = 0.1
    
    def __init__(self):
        super().__init__(refresh_delay=0.1)
    
    def pull_data(self) -> np.ndarray:
        """Pull raw data from the instrument."""
        # Example: return raw voltage readings
        return np.array([[1.0, 2.0], [1.01, 2.01]])
    
    def process_data(self, raw_data: np.ndarray) -> MyCustomData:
        """Process raw data into structured format."""
        time = raw_data[:, 0]
        voltage = raw_data[:, 1]
        return MyCustomData(time=time, voltage=voltage, temperature=25.0)
    
    def on_start(self) -> bool:
        """Called when data acquisition starts."""
        return True
    
    def on_stop(self) -> None:
        """Called when data acquisition stops."""
        pass
```


### Analysis

The `Analysis` is a `DataAnalysis` subclass that manages specific plots and is associated with specific data readers.

**Key Responsibilities:**
- Implement `refresh_plots()`: Update plots with new data
- Define reader properties using the `@reader` decorator
- Control plot visibility via `.show` property

**Example:**

```python
from typing import List
import labpilot.analysis as ana
import src.readers as r
from labpilot.GUI.binding import Binding

class MyAnalysis(ana.DataAnalysis):
    """Analysis for custom measurements."""
    
    @reader
    def my_reader(self) -> r.LaserController:
        """My instrument reader."""
        ...
    
    def __init__(self):
        super().__init__()
        self.plot_value = pb.GraphSet()
    
    def refresh_plots(self, window, view) -> None:
        """Update plots with new data."""
        data = self.my_reader.get_data()
        if data is not None:
            self.plot_value.set_data(data.time, data.voltage)
    
```

### View

The `View` defines what analyses should be performed for a specific measurement type. Views are responsible for selecting the appropriate `Analysis` components.

**Key Responsibilities:**
- Implement `get_analysis()`: Return a list of `DataAnalysis` objects
- Control which plots are visible via `.show` property

**Example:**

```python
from typing import List
import labpilot.analysis as ana
import src.readers as r

class MyView(ana.View):
    """View for displaying custom measurements."""
    name: str = "Custom View"
    ignore: bool = False
    
    def get_analysis(self) -> List[ana.DataAnalysis]:
        """Return analysis components for this view."""
        analysis = MyAnalysis()
        
        analysis.plot_value.show = True
        
        return [analysis]
```


### Binding

The `Binding` is a Qt-compatible reactive variable class for managing GUI state. It provides:
- Qt signal emission for reactive updates
- Persistent state saved across sessions
- Thread-safe change notifications
- Automatic main instance management for multi-instance scenarios

**Example:**

```python
from labpilot.GUI.binding import Binding

class MyInstrument(r.OscilloscopeReader):
    @Binding
    def IP(cls) -> str:
        """Instrument IP address."""
        return "192.168.0.2"
    
    @IP.onchange
    def __IP(self, value: str) -> None:
        """Callback when IP address changes."""
        print(f"IP changed to {value}")
        self.IP_ADDRESS = value
```

### Using the Library

To use the LabPilot library in your own project, it is recommended to initialize the example project and start from there. However, you can also create it manually

1. **Create a Python file** with your views and analysis definitions:

```python
# my_analysis.py
from typing import List
import labpilot.analysis as ana
import labpilot.DataReceiver as dr

class MyCustomData(dr.ProcessedData):
    """Custom processed data class."""
    time: np.ndarray
    voltage: np.ndarray
    temperature: float

class MyReader(dr.LiveDataReader[MyCustomData]):
    name: str = "My Instrument"
    dirname: str = "my_instrument"
    refresh_delay: float = 0.1
    
    def __init__(self):
        super().__init__(refresh_delay=0.1)
    
    def pull_data(self) -> np.ndarray:
        """Pull raw data from the instrument."""
        # Example: return raw voltage readings
        return np.array([[1.0, 2.0], [1.01, 2.01]])
    
    def process_data(self, raw_data: np.ndarray) -> MyCustomData:
        """Process raw data into structured format."""
        time = raw_data[:, 0]
        voltage = raw_data[:, 1]
        return MyCustomData(time=time, voltage=voltage, temperature=25.0)
    
    def on_start(self) -> bool:
        """Called when data acquisition starts."""
        return True


class MyAnalysis(ana.DataAnalysis):
    @reader
    def my_reader(self) -> dr.LiveDataReader:
        return MyReader()

    def __init__(self):
        super().__init__()
        self.plot_data = pb.GraphSet()
    
    def refresh_plots(self, window, view) -> None:
        data = self.my_reader.get_data()
        self.plot_data.set_data(data.time, data.voltage)

class MyView(ana.View):
    name: str = "My View"
    ignore: bool = False
    
    def get_analysis(self) -> List[ana.DataAnalysis]:
        analysis = MyAnalysis()
        analysis.plot_data.show = True
        return [analysis]
    
```

2. **Reference the file in `config.ini`**:

```ini
[GENERAL]
extra_code = my_analysis.py
```

3. **Create an entry point**: 

Create a file (generally called `main.py`) that calls the `labpilot.main()` method. Example from the sample project: 

```python
"""Entry point of labpilot
"""
#!/usr/bin/env python
import os


def main():
    """Run administrative tasks."""
    os.environ.setdefault("LABPILOT_PROJECT_DESCRIPTION", "Automatic Measurement system for Two Photons Measurements")
    try:
        import labpilot
    except ImportError as exc:
        raise ImportError(
            "Couldn't import LabPilot. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    labpilot.main()


if __name__ == "__main__":
    main()


```

## Project Structure

```
<YOUR-PROJECT-FOLDER>/
├── src/
│   ├── readers.py               # Various instrument readers
│   ├── temperature_readers.py   # Temperature/humidity reader
│   ├── ofdr_reader.py           # OFDR instrument reader
│   └── views.py                 # View implementations
├── tests/                       # Unit tests
├── config.ini                   # Configuration file
├── main.py                      # Application launcher
└── requirements.txt             # Python dependencies
```

## Configuration

The `config.ini` file controls application behavior:

```ini
[GENERAL]
# Output directory for recorded data
output_directory=outputs
# Location for saved plots
plots_output_dir=plots
# Analysis data folder
data_analysis_folder=saved_outputs

# File containing the extra code definition. This is the entry point of the extension – Make sure you define all your views in this file, or make them available there! Otherwise, they won't be discovered!
extra_code = src/views.py

# Indicates if errors must be shown using an alert
error_alert = true
[QT]
# Indicates the frequency at which the plots are refreshed [ms]
plot_refresh_rate = 500
```

## Support

For questions or issues, please refer to the instrument documentation or create an issue on the repository.