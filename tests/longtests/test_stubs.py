"""This module makes sure that all the stubs files (.pyi) match their implementation file"""

import os
from pathlib import Path
from typing import Never
import unittest
import queue
import tests.stubtesting as st


class TestStubs(unittest.TestCase):
    @classmethod
    def _test_stub_wrapper(cls, module: Path):
        def wrapper(self):
            source = module.with_suffix(".py")
            stub = module
            m = str(module.with_suffix("")).replace("/", ".")

            # Check the source
            self.assertTrue(
                st.check_source(source, stub, verbose=False),
                f"Run `python tests/stubtesting.py {m}` for more infos",
            )

            # Check the signatures
            self.assertTrue(
                st.check_signatures(source, stub, verbose=False),
                f"Run `python tests/stubtesting.py {m}` for more infos",
            )

            # Check with stubtest
            self.assertTrue(
                st.run_stubtest(m, verbose=False),
                f"Run `python tests/stubtesting.py {m}` for more infos",
            )

            # Check with mypy
            self.assertTrue(
                st.run_mypy(stub, verbose=False),
                f"Run `python tests/stubtesting.py {m}` for more infos",
            )

        return wrapper


# Dynamically add a test for each .pyi file
basepath = Path("src/labtools")
files = queue.Queue[Path]()
for file in os.listdir(basepath):
    files.put_nowait(Path(file))

while not files.empty():
    f = files.get_nowait()
    path = basepath / f

    if path.suffix == ".pyi":
        module = path  # str(path).replace("/", ".").replace("src.", "")
        setattr(
            TestStubs,
            "test_" + path.name,
            TestStubs._test_stub_wrapper(module),
        )
    elif path.is_dir():
        for file in os.listdir(path):
            files.put_nowait(path / file)
