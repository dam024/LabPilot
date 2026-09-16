# SNAPSHOT Cython Compilation Setup

This document describes the Cython compilation infrastructure for the SNAPSHOT project.

## Build Artifacts Handling

The following directories are excluded from git version control:
- `build/` - Contains C source files and intermediate build artifacts
- `build/lib.macosx-*/` - Contains compiled `.so` files

To include the compiled extensions in git, remove them from `.gitignore`:
```gitignore
build/*.so
build/**/*.so
```

## Project Structure

```
SNAPSHOT/
├── src/                    # Python source files
├── tests/                  # Pure Python test files
├── config/                 # Configuration files
├── cython/                 # Compiled extension modules (generated after build)
│   ├── __init__.py
│   ├── config/config.so
│   ├── main/main.so
│   ├── ...
├── setup_cython.py        # Cython build script
└── ...
```

## Usage

### Using Python Source Files (Recommended)

For regular Python code, import directly from the source files in `src/`:

```python
from src.config import GeneralConfig, globalState
from src.main import run_tests_in_directory
from src.specific_modules import TestReader
from src.labtools.DataReceiver import LiveDataReader
from src.labtools.analysis import DataAnalysis, View
from src.labtools.utils import dynamic_import
```

### About Compiled Extensions

The compiled extensions in `cython/` provide:
- **Faster execution** for numerical/computationally intensive code
- **Binary compatibility** across Python versions (when recompiled)
- **Performance optimization** for CPU-bound operations

However, for typical Python applications:
- The source files in `src/` work correctly
- The compiled extensions are optional
- Import from `src/` ensures consistent behavior

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

**Fix:** Replace with traditional typing.

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

All test files remain as pure Python in `tests/` and continue to run without modification.

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
- ✅ Compile Cython-eligible files
- ✅ Place compiled modules in separate `cython/` directory
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

## Build Artifacts Location

- **Compiled extensions:** `cython/` directory
- **C source files:** `build/*.c` (in build directory)
- **Build output:** `build/` directory (can be safely ignored by git)

## Troubleshooting

### Import errors

If you encounter import errors:
1. Ensure the `src/` directory is in the Python path
2. Check that all dependencies are installed
3. Import directly from source files: `from src.module import ...`

## License

This setup follows the project's main license. See `LICENSE` for details.