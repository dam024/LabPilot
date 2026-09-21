from setuptools import Extension, setup, find_packages
from setuptools.command.build_py import build_py
from Cython.Build import cythonize
from pathlib import Path
import shutil

extensions = cythonize(
    [
        Extension("*", ["src/labtools/**/*.pyx"]),
        Extension("DataReceiver", ["src/labtools/DataReceiver.py"]),
        Extension("utils", ["src/labtools/utils.py"]),
    ],
    build_dir="build/cython",
    compiler_directives={
        "language_level": "3",
    },
)


class BuildPy(build_py):
    def run(self):
        super().run()

        # Copy the test files
        files = ["views.py", "readers.py", "analysis.py", "config.ini"]
        src = Path("src")

        for f in files:
            path = src / f

            d = Path(self.build_lib) / "labtools_data"
            d.mkdir(exist_ok=True)
            dst = d / f

            shutil.copyfile(path, dst)


setup(
    name="labtools",
    version="0.1.1",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={
        ".": ["views.py"],
    },
    install_requires=[
        "colorama>=0.4.0",
        "matplotlib>=3.11.0",
        "numpy>=2.5.0",
        "pyqtgraph>=0.14.0",
        "pyside6>=6.11.0",
        "rocksdict>=0.3.29",
        "scipy>=1.18.0",
        "tqdm>=4.70.0",
        "typing_extensions>=4.16.0",
    ],
    ext_modules=extensions,
    options={
        "egg_info": {
            "egg_base": "build",
        },
    },
    extras_require={
        "dev": ["setuptools", "cython", "psutil"],
    },
    entry_points={
        "console_scripts": [
            "labtools=labtools.cli:main",
        ],
    },
    cmdclass={"build_py": BuildPy},
)
