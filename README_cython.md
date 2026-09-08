# SNAPSHOT Cython Compilation Setup

This document describes the Cython compilation infrastructure for the SNAPSHOT project.

## Project Structure

```
SNAPSHOT/
├── src/                    # Cython-eligible source files
│   ├── config.py          # Configuration module
│   ├── main.py            # Main entry point
│   ├── specific_modules.py # Specific modules
│   ├── ofdr_reader.py     # OFDR reader
│   ├── readers.py         # Readers collection
│   ├── temperature_readers.py # Temperature readers
│   ├── thorlabs_power_meter.py # Thorlabs power meter
│   ├── views.py           # Views definitions
│   ├── config.cpython-313-darwin.so  # Compiled extension
│   ├── main.cpython-313-darwin.so    # Compiled extension
│   ├── specific_modules.cpython-313-darwin.so  # Compiled extension
│   ├── ...                # All compiled extensions
│   └── labtools/          # Labtools package
│       ├── DataReceiver.py
│       ├── analysis.py
│       ├── measurement_procedure.py
│       ├── scpi_instrument.py
│       ├── utils.py
│       ├── _logging.py
│       ├── MainLoopHandler.py
│       ├── config.cpython-313-darwin.so  # Compiled extension
│       ├── MainLoopHandler.cpython-313-darwin.so  # Compiled extension
│       └── GUI/           # GUI subpackage
│       └── plots/         # Plots subpackage
├── tests/                  # Pure Python test files (unchanged)
├── config/                 # Configuration files
│   └── config.ini
├── cython/                 # Compiled extension modules
│   └── *.so/*.pyd         # Compiled modules (after build)
├── setup_cython.py        # Cython build script
├── README_cython.md       # This file
└── CYTHON_OPTIMIZATION_REPORT.md  # Detailed compilation report
```

## Compilation

To compile Cython-eligible files to extension modules:

```bash
python setup_cython.py build_ext --inplace
```

This will:
1. Compile all Cython-eligible Python files to `.so` extensions
2. Place compiled modules in the `src/` directory (overwriting .py files)
3. Maintain Python compatibility

## Usage

After compilation, the modules can be imported:

```python
import src.config
import src.main
from src.specific_modules import TestReader
from src.labtools.DataReceiver import LiveDataReader
from src.labtools.analysis import DataAnalysis
```

The compiled extensions take precedence over pure Python modules. If compiled modules are not available, the project will fall back to pure Python.

## Files Compiled Successfully (24 modules)

### Core Modules
- `config` - Configuration module
- `main` - Main entry point
- `specific_modules` - Specific modules with readers/analysis
- `ofdr_reader` - OFDR reader
- `readers` - Readers collection
- `temperature_readers` - Temperature readers
- `thorlabs_power_meter` - Thorlabs power meter
- `views` - Views definitions

### Labtools Package
- `labtools` - Main labtools package
- `labtools.analysis` - Analysis module
- `labtools.measurement_procedure` - Measurement procedure
- `labtools.scpi_instrument` - SCPI instrument base class
- `labtools._logging` - Logging module
- `labtools.MainLoopHandler` - Main loop handler
- `labtools.utils` - Utility functions

### Labtools GUI Subpackage
- `labtools.GUI.binding` - GUI binding system
- `labtools.GUI.parameters` - GUI parameters
- `labtools.GUI.internal_parameters` - Internal parameters
- `labtools.GUI.mainGUI` - Main GUI

### Labtools Plots Subpackage
- `labtools.plots` - Plots package
- `labtools.plots.plots_implementation` - Plot implementations
- `labtools.plots.matplotlib_backend` - Matplotlib backend
- `labtools.plots.pyqt_backend` - PyQt backend

## Files NOT Compiled (4 modules)

The following files could not be compiled to Cython due to Python 3.12+ PEP 695 syntax:

### 1. labtools.DataReceiver
```python
class LiveDataReader[T: ProcessedData](params.GUIParametrable):
```

**Reason:** Cython does not support PEP 695 type parameters.

**Fix:** Replace with traditional typing:
```python
from typing import TypeVar, Generic, TYPE_CHECKING
if TYPE_CHECKING:
    T = TypeVar("T", bound=ProcessedData)

class LiveDataReader(Generic[T], params.GUIParametrable):
```

### 2. labtools.GUI.objects
```python
class NumericalValueInput[T: int | float](LabelledWidget):
```

**Reason:** Cython does not support PEP 695 type parameters.

**Fix:** Replace with traditional typing:
```python
from typing import TypeVar, Generic
T = TypeVar("T", bound=(int, float))

class NumericalValueInput(LabelledWidget, Generic[T]):
```

### 3. labtools.data_management.local_storage
```python
def get[T](self, owner: object | Type, key: str) -> T:
```

**Reason:** Cython does not support PEP 695 type parameters.

**Fix:** Replace with traditional typing.

### 4. labtools.data_management.measurement_information
```python
def get_parameter[T](self, owner: object | Type, key: str) -> T:
```

**Reason:** Cython does not support PEP 695 type parameters.

**Fix:** Replace with traditional typing.

See `CYTHON_OPTIMIZATION_REPORT.md` for detailed recommendations and estimated effort.

## Test Files (18 modules - unchanged)

The following test files remain as pure Python:
- `tests/__init__.py`
- `tests/dummy_classes.py`
- `tests/utils.py`
- `tests/config.ini`
- `tests/unittests/__init__.py`
- `tests/unittests/GUI/__init__.py`
- `tests/unittests/GUI/test_mainGUI.py`
- `tests/unittests/GUI/test_objects.py`
- `tests/unittests/GUI/test_parameters.py`
- `tests/unittests/test_DataReceiver.py`
- `tests/unittests/test_analysis.py`
- `tests/unittests/test_binding.py`
- `tests/unittests/test_data_flow.py`
- `tests/unittests/test_measurement_procedure.py`
- `tests/unittests/test_utils.py`
- `tests/workflows/__init__.py`
- `tests/workflows/test_ui_workflows.py`

All test files are untouched and continue to run without modification.

## Dependencies

The compiled modules require:
- `numpy>=1.20.0`
- `PySide6>=6.4.0`
- `pyvisa>=1.12.0`
- `pyqtgraph>=0.13.0`
- `scipy>=1.7.0`
- `colorama>=0.4.0`

Install with:
```bash
pip install numpy PySide6 pyvisa pyqtgraph scipy colorama
```

For development:
```bash
pip install numpy PySide6 pyvisa pyqtgraph scipy colorama cython setuptools
```

## Migration Status

### Step 1 (Completed)
- ✅ Set up compilation infrastructure
- ✅ Reorganize project structure
- ✅ Compile all Cython-eligible files
- ✅ Document files needing improvement

### Step 2 (Future)
- 🔲 Fix PEP 695 syntax in 4 files
- 🔲 Add Cython type declarations for performance
- 🔲 Profile and optimize hot paths
- 🔲 Complete migration of remaining files

## Building the Package

To build the complete package with compiled extensions:

```bash
python setup_cython.py build_ext --inplace
```

To build for installation (creates wheel):

```bash
python setup_cython.py bdist_wheel
```

## Troubleshooting

### Compilation fails for a specific module

If a module fails to compile due to PEP 695 syntax, see the "Files NOT Compiled" section above for the fix.

### Runtime errors after compilation

If you encounter import errors:
1. Ensure the `src/` directory is in the Python path
2. Check that all dependencies are installed
3. Verify that the compiled modules are being imported correctly

### Using pure Python only

To use pure Python without compiled extensions:

```bash
# Remove compiled extensions
rm -f src/*.so src/labtools/*.so src/labtools/GUI/*.so src/labtools/plots/*.so

# The project will automatically use pure Python modules
```

## License

This setup follows the project's main license. See `LICENSE` for details.