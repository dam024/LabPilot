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

2. Static signature/type consistency:
   - missing arguments
   - extra arguments
   - argument names
   - argument kinds
   - defaults
   - argument annotations
   - return annotations
   - async/sync mismatch

3. Runtime stubtest:
   - names present in runtime but missing from stub
   - names present in stub but missing at runtime
   - runtime signatures
   - defaults
   - positional-only arguments
   - runtime attributes where discoverable

4. The .pyi is separately checked by mypy for type correctness.

Usage:

    python check_stubs.py mypackage.mymodule

or:

    python check_stubs.py mypackage.mymodule --source mymodule.py
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_private(name: str) -> bool:
    """
    Return True for names that are normally considered private.

    We keep dunder methods because they are part of a class API.
    """
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def annotation_to_string(node: ast.expr | None) -> str | None:
    """
    Convert an annotation AST node into a normalized string.

    ast.unparse() gives us a representation that is independent of
    insignificant whitespace.
    """
    if node is None:
        return None

    return ast.unparse(node)


def default_to_string(node: ast.expr | None) -> str | None:
    """
    Convert a default value into a normalized string.
    """
    if node is None:
        return None

    return ast.unparse(node)


# ---------------------------------------------------------------------------
# Definition collection
# ---------------------------------------------------------------------------


Definition = tuple[str, str]


def collect_definitions(
    filename: Path,
    *,
    include_private: bool = False,
) -> set[str]:
    """
    Collect qualified names of classes/functions/methods.

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

                if isinstance(node, ast.ClassDef):
                    visit_body(node.body, qualified)

    visit_body(tree.body)

    return result


# ---------------------------------------------------------------------------
# Function collection
# ---------------------------------------------------------------------------


FunctionInfo = tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]


def collect_functions(
    filename: Path,
    *,
    include_private: bool = False,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Collect all functions/methods by qualified name.

    Functions nested inside functions are deliberately ignored because
    they are not part of the module/class public API.
    """

    source = filename.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filename))

    result: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit_body(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                name = node.name

                if not include_private and is_private(name):
                    continue

                qualified = f"{prefix}.{name}" if prefix else name
                result[qualified] = node

            elif isinstance(node, ast.ClassDef):
                name = node.name

                if not include_private and is_private(name):
                    continue

                qualified = f"{prefix}.{name}" if prefix else name

                visit_body(node.body, qualified)

            # Do NOT recurse into function bodies.

    visit_body(tree.body)

    return result


# ---------------------------------------------------------------------------
# Signature representation
# ---------------------------------------------------------------------------


@dataclass
class ParameterInfo:
    name: str
    kind: str
    annotation: str | None
    default: str | None


@dataclass
class SignatureInfo:
    parameters: list[ParameterInfo]
    return_annotation: str | None
    is_async: bool


def get_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> SignatureInfo:
    """
    Extract the complete signature from a function AST node.
    """

    args = node.args

    parameters: list[ParameterInfo] = []

    # Positional-only arguments
    positional_only_count = len(args.posonlyargs)

    # Regular positional arguments
    positional_args = args.args

    all_positional = args.posonlyargs + positional_args

    # Defaults apply to the final N positional parameters.
    positional_defaults: list[ast.expr | None] = [None] * (
        len(all_positional) - len(args.defaults)
    ) + list(args.defaults)

    for index, (arg, default) in enumerate(zip(all_positional, positional_defaults)):
        if index < positional_only_count:
            kind = "positional-only"
        else:
            kind = "positional-or-keyword"

        parameters.append(
            ParameterInfo(
                name=arg.arg,
                kind=kind,
                annotation=annotation_to_string(arg.annotation),
                default=default_to_string(default),
            )
        )

    # *args
    if args.vararg is not None:
        parameters.append(
            ParameterInfo(
                name=args.vararg.arg,
                kind="var-positional",
                annotation=annotation_to_string(args.vararg.annotation),
                default=None,
            )
        )

    # Keyword-only arguments
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append(
            ParameterInfo(
                name=arg.arg,
                kind="keyword-only",
                annotation=annotation_to_string(arg.annotation),
                default=default_to_string(default),
            )
        )

    # **kwargs
    if args.kwarg is not None:
        parameters.append(
            ParameterInfo(
                name=args.kwarg.arg,
                kind="var-keyword",
                annotation=annotation_to_string(args.kwarg.annotation),
                default=None,
            )
        )

    # Return value - When the return is "-> None", we consider that there is no return value
    return_value = annotation_to_string(node.returns)
    if return_value == "None":
        return_value = None

    return SignatureInfo(
        parameters=parameters,
        return_annotation=return_value,
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


# ---------------------------------------------------------------------------
# Signature comparison
# ---------------------------------------------------------------------------


def compare_signatures(
    name: str,
    source_node: ast.FunctionDef | ast.AsyncFunctionDef,
    stub_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """
    Compare implementation and stub signatures.

    Returns a list of human-readable errors.
    """

    source_sig = get_signature(source_node)
    stub_sig = get_signature(stub_node)

    errors: list[str] = []

    # ------------------------------------------------------------------
    # async vs sync
    # ------------------------------------------------------------------

    if source_sig.is_async != stub_sig.is_async:
        source_kind = "async" if source_sig.is_async else "sync"
        stub_kind = "async" if stub_sig.is_async else "sync"

        errors.append(
            f"{name}: implementation is {source_kind}, " f"stub is {stub_kind}"
        )

    # ------------------------------------------------------------------
    # Number of parameters
    # ------------------------------------------------------------------

    if len(source_sig.parameters) != len(stub_sig.parameters):
        errors.append(
            f"{name}: argument count differs "
            f"(implementation={len(source_sig.parameters)}, "
            f"stub={len(stub_sig.parameters)})"
        )

    # ------------------------------------------------------------------
    # Compare parameters
    # ------------------------------------------------------------------

    common_count = min(
        len(source_sig.parameters),
        len(stub_sig.parameters),
    )

    for index in range(common_count):
        source_param = source_sig.parameters[index]
        stub_param = stub_sig.parameters[index]

        location = f"{name}: argument #{index + 1}"

        # Name
        if source_param.name != stub_param.name:
            errors.append(
                f"{location} name differs "
                f"(implementation={source_param.name!r}, "
                f"stub={stub_param.name!r})"
            )

        # Kind
        if source_param.kind != stub_param.kind:
            errors.append(
                f"{name}.{source_param.name}: argument kind differs "
                f"(implementation={source_param.kind}, "
                f"stub={stub_param.kind})"
            )

        # Annotation
        if source_param.annotation != stub_param.annotation:
            errors.append(
                f"{name}.{source_param.name}: argument type differs "
                f"(implementation={source_param.annotation!r}, "
                f"stub={stub_param.annotation!r})"
            )

        # Default
        if source_param.default != stub_param.default:
            errors.append(
                f"{name}.{source_param.name}: default differs "
                f"(implementation={source_param.default!r}, "
                f"stub={stub_param.default!r})"
            )

    # ------------------------------------------------------------------
    # Return annotation
    # ------------------------------------------------------------------

    if source_sig.return_annotation != stub_sig.return_annotation and not (
        source_sig.return_annotation is None and stub_sig.return_annotation is None
    ):
        print(
            source_sig.return_annotation,
            type(source_sig.return_annotation),
            stub_sig.return_annotation,
            type(stub_sig.return_annotation),
        )
        errors.append(
            f"{name}: return type differs "
            f"(implementation={source_sig.return_annotation!r}, "
            f"stub={stub_sig.return_annotation!r})"
        )

    return errors


# ---------------------------------------------------------------------------
# Signature checker
# ---------------------------------------------------------------------------


def check_signatures(
    source_file: Path,
    stub_file: Path,
    *,
    include_private: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Compare function/method signatures between .py and .pyi.
    """

    source_functions = collect_functions(
        source_file,
        include_private=include_private,
    )

    stub_functions = collect_functions(
        stub_file,
        include_private=include_private,
    )

    ok = True

    if verbose:
        print()
        print("=" * 72)
        print("SIGNATURE / TYPE CHECK")
        print("=" * 72)

    # Functions present in source
    for name in sorted(source_functions):
        source_node = source_functions[name]

        if name not in stub_functions:
            # Already reported by the definition checker.
            continue

        stub_node = stub_functions[name]

        errors = compare_signatures(
            name,
            source_node,
            stub_node,
        )

        if errors:
            ok = False

            for error in errors:
                print(f"  ERROR  {error}")

    if ok and verbose:
        print("\n✓ No signature or type differences found.")

    return ok


# ---------------------------------------------------------------------------
# Source checker
# ---------------------------------------------------------------------------


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

    result = subprocess.run(
        command,
        capture_output=not verbose,
    )

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
        "--no-signatures",
        action="store_true",
        help="Do not compare function/method signatures.",
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
    # Source definition check
    # ------------------------------------------------------------------

    source_ok = check_source(
        args.source,
        args.stub,
        include_private=args.include_private,
    )

    # ------------------------------------------------------------------
    # Signature/type check
    # ------------------------------------------------------------------

    signature_ok = True

    if not args.no_signatures:
        signature_ok = check_signatures(
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
    print(f"Signatures/types   : {'PASS' if signature_ok else 'FAIL'}")
    print(f"stubtest           : {'PASS' if stubtest_ok else 'FAIL'}")
    print(f"mypy               : {'PASS' if mypy_ok else 'FAIL'}")

    print()

    return 0 if source_ok and signature_ok and stubtest_ok and mypy_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
