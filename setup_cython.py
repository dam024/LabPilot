"""
SNAPSHOT Cython Compilation Setup Script
=========================================

This script compiles Python files to Cython extension modules (.so on macOS, .pyd on Windows).

The compiled modules are placed in the 'cython' directory to keep source files clean.

Usage:
    python setup_cython.py build_ext --inplace

This will:
1. Compile all Cython-eligible Python files to .so extensions
2. Place compiled modules in the 'cython' directory (not overwriting source files)
3. Maintain Python compatibility (can run with or without compiled extensions)

Note: Some files with advanced type annotations (PEP 695 syntax) are compiled
as pure Python and will be improved in Step 2 of the migration.

PEP 695 Generic Syntax Files (will be improved in Step 2):
- labtools.DataReceiver
- labtools.GUI.objects
- labtools.data_management.local_storage
- labtools.data_management.measurement_information
- labtools.plots.plot_backend
- labtools.plots.plots
- labtools.utils

These files use Python 3.12+ PEP 695 syntax (e.g., class Foo[T]:) which is not
yet fully supported by Cython. They will be compiled as pure Python for now
and documented for future migration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add the project root to the path
# HERE = Path(__file__).parent.resolve()
# sys.path.insert(0, str(HERE))

import numpy as np
from setuptools import setup, Extension, find_packages
from setuptools.command import build_ext
from Cython.Build import cythonize


# ============================================================================
# Source Files for Cython Compilation
# ============================================================================

# All Python source files in the 'src' directory that can be compiled to Cython
# Excluded from Cython compilation:
# - Files with PEP 695 generic syntax (e.g., class Foo[T]:) - not supported by Cython yet
# These will be improved in Step 2 of the migration

source_files = []

# Core modules at src/ level
core_modules = [
    ("config", "config.py"),
    ("main", "main.py"),
    ("specific_modules", "specific_modules.py"),
    ("ofdr_reader", "ofdr_reader.py"),
    ("readers", "readers.py"),
    ("temperature_readers", "temperature_readers.py"),
    ("thorlabs_power_meter", "thorlabs_power_meter.py"),
    ("views", "views.py"),
]

# Labtools package
labtools_files = [
    ("labtools", "labtools/__init__.py"),
    ("labtools.analysis", "labtools/analysis.py"),
    ("labtools.measurement_procedure", "labtools/measurement_procedure.py"),
    ("labtools.scpi_instrument", "labtools/scpi_instrument.py"),
    # Note: labtools.utils excluded due to PEP 695 syntax
    ("labtools._logging", "labtools/_logging.py"),
    ("labtools.MainLoopHandler", "labtools/MainLoopHandler.py"),
    # Note: labtools.DataReceiver excluded due to PEP 695 syntax
]

# Labtools GUI subpackage
gui_files = [
    ("labtools.GUI.binding", "labtools/GUI/binding.py"),
    ("labtools.GUI.parameters", "labtools/GUI/parameters.py"),
    ("labtools.GUI.internal_parameters", "labtools/GUI/internal_parameters.py"),
    ("labtools.GUI.mainGUI", "labtools/GUI/mainGUI.py"),
    # Note: labtools.GUI.objects excluded due to PEP 695 syntax
]

# Labtools plots subpackage
# Note: plot_backend and plots excluded due to PEP 695 syntax
plots_files = [
    ("labtools.plots", "labtools/plots/__init__.py"),
    ("labtools.plots.plots_implementation", "labtools/plots/plots_implementation.py"),
    # Note: labtools.plots.plot_backend excluded due to PEP 695 syntax
    # Note: labtools.plots.plots excluded due to PEP 695 syntax
    ("labtools.plots.matplotlib_backend", "labtools/plots/matplotlib_backend.py"),
    ("labtools.plots.pyqt_backend", "labtools/plots/pyqt_backend.py"),
]

# Labtools data_management subpackage
# Note: Both files excluded due to PEP 695 syntax
# data_files = []  # Empty - all files excluded

# Collect all source files
source_files = (
    core_modules + labtools_files + gui_files + plots_files + []
)  # No data files

# ============================================================================
# Create Extension Modules with Cython Compiler Directives
# ============================================================================

ext_modules = []

for module_name, source_path in source_files:
    ext = Extension(
        name=module_name,
        sources=[f"src/{source_path}"],
        include_dirs=[np.get_include()],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    )
    ext_modules.append(ext)


# ============================================================================
# Apply Cython compiler directives
# ============================================================================

# Cython compiler directives for all extensions
cython_directives = {
    "language_level": 3,
    "binding": True,  # Enable C API binding
    "always_allow_keywords": True,  # Allow keyword arguments
}

# Apply directives to each extension
for ext in ext_modules:
    for directive, value in cython_directives.items():
        setattr(ext, directive, value)


# ============================================================================
# Define the custom build class
# ============================================================================


class CleanBuildExt(build_ext.build_ext):
    """
    Custom build_ext that:
    1. Builds extensions to build/ directory
    2. Copies them to cython/ directory with clean module names
    3. Leaves source files in src/ untouched
    """

    def run(self):
        # Run normal build first
        super().run()
        return

        # Copy compiled extensions to cython/ directory
        build_dir = Path("build/lib.macosx-26.5-arm64-cpython-313")

        if build_dir.exists():
            # Find all .so files in build directory
            for so_file in build_dir.glob("*.so"):
                # Get the module name from the filename
                stem = so_file.stem
                # Remove the version/platform suffix
                if "cpython-313-darwin" in stem:
                    module_name = stem.replace("cpython-313-darwin", "")
                else:
                    module_name = stem

                # Create target directory structure matching source
                # Remove trailing dots if any
                module_name = module_name.rstrip(".")
                target_path = Path("labtools_so") / module_name / f"{module_name}.so"
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy the compiled extension
                import shutil

                shutil.copy(so_file, target_path)
                print(f"  Copied {so_file.name} -> {target_path}")

        print(f"\n{'='*80}")
        print(f"Compiled extensions are now in: labtools_so/")
        print(f"{'='*80}\n")
        print("Source files in src/ remain unchanged.")
        print("Import the compiled modules from: from cython.module_name import ...")


# ============================================================================
# Setup Configuration with cython/ output directory
# ============================================================================

setup(
    name="SNAPSHOT",
    version="1.0.0",
    description="SNAPSHOT - Scientific data acquisition and analysis with Cython support",
    author="SNAPSHOT Team",
    author_email="",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "cython": ["*.so", "*.pyd"],
    },
    ext_modules=cythonize(ext_modules, language_level=3),
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
        "PySide6>=6.4.0",
        "pyvisa>=1.12.0",
        "pyqtgraph>=0.13.0",
        "scipy>=1.7.0",
        "colorama>=0.4.0",
    ],
    extras_require={
        "dev": [
            "cython>=0.29.0",
            "setuptools>=61.0",
        ],
    },
    # Custom command to copy compiled extensions to cython/ directory
    cmdclass={
        "build_ext": CleanBuildExt,
    },
)
