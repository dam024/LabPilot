#!/usr/bin/env python3

"""
Check consistency between a Python/Cython implementation and its .pyi stub.

Checks:

1. Static source definitions:
   - functions
   - async functions
   - classes
   - methods
   - nested classes
   - properties

2. Runtime stubtest:
   - names present in runtime but missing from stub
   - names present in stub but missing at runtime
   - function/method signatures
   - defaults
   - positional-only arguments
   - runtime attributes where discoverable
   - class inheritance-related inconsistencies where detectable

3. The .pyi is separately checked by mypy for type correctness.

Usage:

    python check_stubs.py mypackage.mymodule

or:

    python check_stubs.py mypackage.mymodule --source mymodule.py

The module must be importable in the current environment.
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# AST/source checker
# ---------------------------------------------------------------------------

Definition = tuple[str, str]


def is_private(name: str) -> bool:
    """
    Return True for names that are normally considered private.

    We keep dunder methods because they are part of a class API.
    """
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def collect_definitions(
    filename: Path,
    *,
    include_private: bool = False,
) -> set[str]:
    """
    Collect qualified names of classes/functions/methods/properties.

    Example:

        class A:
            def foo(self): ...
            @property
            def value(self): ...

    produces:

        A
        A.foo
        A.value
    """

    source = filename.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filename))

    result: set[str] = set()

    def visit_body(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                name = node.name

                if not include_private and is_private(name):
                    continue

                qualified = f"{prefix}.{name}" if prefix else name
                result.add(qualified)

                # Recurse into classes and functions.
                #
                # We only really care about members of classes. Nested
                # functions inside functions aren't part of the public API.
                if isinstance(node, ast.ClassDef):
                    visit_body(node.body, qualified)

                continue

            # A property may be represented by a function, so it is already
            # handled above.
            #
            # Handle decorated aliases only insofar as the underlying
            # function/class is present.

    visit_body(tree.body)

    return result


def check_source(
    source_file: Path,
    stub_file: Path,
    *,
    include_private: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Compare definitions statically between .py and .pyi.
    """

    source_defs = collect_definitions(
        source_file,
        include_private=include_private,
    )

    stub_defs = collect_definitions(
        stub_file,
        include_private=include_private,
    )

    missing = sorted(source_defs - stub_defs)
    extra = sorted(stub_defs - source_defs)

    ok = True

    if verbose:
        print("=" * 72)
        print("SOURCE CHECK")
        print("=" * 72)

    if missing:
        ok = False
        print("\nDefinitions in .py but missing from .pyi:\n")

        for name in missing:
            print(f"  ERROR  {name}")

    else:
        if verbose:
            print("\n✓ No definitions are missing from the .pyi.")

    if extra:
        print("\nDefinitions in .pyi but missing from .py:\n")

        for name in extra:
            print(f"  WARNING  {name}")

        # Don't necessarily fail here.
        #
        # A .pyi is allowed to contain typing-only things such as:
        #
        #   TypeVar
        #   overloads
        #   type aliases
        #   @type_check_only classes
        #
        # Therefore this is informational rather than automatically fatal.

    return ok


# ---------------------------------------------------------------------------
# Stubtest
# ---------------------------------------------------------------------------


def run_stubtest(
    module: str,
    *,
    allowlist: Path | None = None,
    concise: bool = False,
    ignore_missing_stub: bool = False,
    ignore_positional_only: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Run mypy.stubtest against the compiled/runtime module.
    """

    module = module.replace("src.", "")

    command = [
        sys.executable,
        "-m",
        "mypy.stubtest",
        module,
    ]

    if concise:
        command.append("--concise")

    if allowlist:
        command.extend(
            [
                "--allowlist",
                str(allowlist),
            ]
        )
    command.append("--mypy-config-file ../mypy.ini")
    command.append("--ignore-missing-stub")

    if ignore_missing_stub:
        command.append("--ignore-missing-stub")

    if ignore_positional_only:
        command.append("--ignore-positional-only")

    if verbose:
        print()
        print("=" * 72)
        print("STUBTEST")
        print("=" * 72)
        print()
        print("$", " ".join(command))
        print()

    result = subprocess.run(
        command, capture_output=not verbose, cwd=Path(os.getcwd()) / "src"
    )

    return result.returncode == 0


# ---------------------------------------------------------------------------
# Mypy
# ---------------------------------------------------------------------------


def run_mypy(target: Path, *, strict: bool = False, verbose: bool = True) -> bool:
    """
    Run mypy on the stub/source target.

    This checks the correctness of the annotations themselves.
    """

    command = [
        sys.executable,
        "-m",
        "mypy",
        str(target),
    ]

    if strict:
        command.append("--strict")

    if verbose:
        print()
        print("=" * 72)
        print("MYPY")
        print("=" * 72)
        print()
        print("$", " ".join(command))
        print()

    result = subprocess.run(command, capture_output=not verbose)

    return result.returncode == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a Python/Cython implementation against its .pyi stub."
    )

    parser.add_argument(
        "module",
        help="Importable module name, e.g. labtools.GUI.parameters",
    )

    parser.add_argument(
        "--source",
        type=Path,
        help="Path to the implementation .py file.",
    )

    parser.add_argument(
        "--stub",
        type=Path,
        help="Path to the .pyi file. Defaults to source with .pyi suffix.",
    )

    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Also check private definitions.",
    )

    parser.add_argument(
        "--no-stubtest",
        action="store_true",
        help="Do not run mypy.stubtest.",
    )

    parser.add_argument(
        "--no-mypy",
        action="store_true",
        help="Do not run mypy.",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Run mypy in strict mode.",
    )

    parser.add_argument(
        "--allowlist",
        type=Path,
        help="stubtest allowlist file.",
    )

    parser.add_argument(
        "--concise",
        action="store_true",
        help="Use concise stubtest output.",
    )

    parser.add_argument(
        "--ignore-positional-only",
        action="store_true",
        help="Pass --ignore-positional-only to stubtest.",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Locate source/stub
    # ------------------------------------------------------------------

    if args.source is None:
        module_path = Path(*args.module.split("."))

        candidates = [
            module_path.with_suffix(".py"),
            module_path / "__init__.py",
        ]

        for candidate in candidates:
            if candidate.exists():
                args.source = candidate
                break

    if args.source is None:
        print(
            f"ERROR: Could not find source file for {args.module}",
            file=sys.stderr,
        )
        return 2

    if args.stub is None:
        args.stub = args.source.with_suffix(".pyi")

    if not args.source.exists():
        print(
            f"ERROR: Source file does not exist: {args.source}",
            file=sys.stderr,
        )
        return 2

    if not args.stub.exists():
        print(
            f"ERROR: Stub file does not exist: {args.stub}",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # Source check
    # ------------------------------------------------------------------

    source_ok = check_source(
        args.source,
        args.stub,
        include_private=args.include_private,
    )

    # ------------------------------------------------------------------
    # Runtime stubtest
    # ------------------------------------------------------------------

    stubtest_ok = True

    if not args.no_stubtest:
        stubtest_ok = run_stubtest(
            args.module,
            allowlist=args.allowlist,
            concise=args.concise,
            ignore_positional_only=args.ignore_positional_only,
        )

    # ------------------------------------------------------------------
    # Mypy
    # ------------------------------------------------------------------

    mypy_ok = True

    if not args.no_mypy:
        mypy_ok = run_mypy(
            args.stub,
            strict=args.strict,
        )

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    print(f"Source definitions : {'PASS' if source_ok else 'FAIL'}")
    print(f"stubtest           : {'PASS' if stubtest_ok else 'FAIL'}")
    print(f"mypy               : {'PASS' if mypy_ok else 'FAIL'}")

    print()

    return 0 if source_ok and stubtest_ok and mypy_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
