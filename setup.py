from setuptools import Extension, setup, find_packages
from setuptools.command.build_py import build_py
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


EXAMPLE_FILES = (
    "views.py",
    "readers.py",
    "analysis.py",
    "config.ini",
)


class BuildPy(build_py):
    def run(self):
        super().run()

        src_dir = ROOT / "src"
        dest_dir = Path(self.build_lib) / "labpilot_data"

        self.mkpath(str(dest_dir))

        for filename in EXAMPLE_FILES:
            source = src_dir / filename
            destination = dest_dir / filename

            if not source.is_file():
                raise FileNotFoundError(f"Required example file not found: {source}")

            self.copy_file(str(source), str(destination))

    def get_source_files(self):
        return super().get_source_files() + [
            str(Path("src") / filename) for filename in EXAMPLE_FILES
        ]

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        outputs.extend(
            str(Path(self.build_lib) / "labpilot_data" / filename)
            for filename in EXAMPLE_FILES
        )
        return outputs


setup(
    name="labpilot",
    version="0.2.0",
    author="Damien Jaccoud",
    author_email="damien.jaccoud@hotmail.com",
    url="https://github.com/dam024/LabPilot",
    description="Automatic measurement interface for experiments",
    package_dir={"": "src"},
    packages=find_packages("src"),
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    include_package_data=True,
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
        "sqlalchemy>=2.1.0",
    ],
    license="Apache 2.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Adaptive Technologies",
        "Topic :: Database :: Front-Ends",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Instrument Drivers",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
    project_urls={
        "Source": "https://github.com/dam024/LabPilot",
        "Issues": "https://github.com/dam024/LabPilot/issues",
    },
    python_requires=">=3.13",
    extras_require={
        "dev": ["setuptools", "psutil"],
    },
    entry_points={
        "console_scripts": [
            "labpilot=labpilot.cli:main",
        ],
    },
    cmdclass={"build_py": BuildPy},
)
