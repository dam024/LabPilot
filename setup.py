from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize

extensions = cythonize(
    "src/labtools/**/*.pyx",
    build_dir="build/cython",
    compiler_directives={
        "language_level": "3",
    },
)


setup(
    name="labtools",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "colorama>=0.4.0",
        "matplotlib>=3.11.0",
        "numpy>=2.5.0",
        "pyqtgraph>=0.14.0",
        "pyside6>=6.11.0",
        "pyside6_addons==6.11.2",
        "pyside6_essentials==6.11.2",
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
        "dev": [
            "setuptools",
            "cython",
        ],
    },
)
