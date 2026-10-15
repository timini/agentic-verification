"""Classical mutants from mutmut's operator set, replayed as whole-file patches.

mutmut's own runner applies mutants through trampolines and stops at the first failing test.
We only use its operator generator (``create_mutations``) and run each mutant ourselves, so
the kill matrix and statuses are under our control. That generator is not a public API,
hence the exact version pin in pyproject.toml.
"""

import os
import tempfile
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
from mutmut import configuration as mutmut_configuration
from mutmut.mutation.file_mutation import create_mutations

from .model import Mutant


def _default_config() -> None:
    """Load mutmut's configuration once, from an empty directory, so its defaults apply.

    mutmut reads ``setup.cfg``/``pyproject.toml`` in the current directory and fails if it
    cannot guess a source path. The audited project's mutmut settings must not change the
    operator population, so we load the defaults from a neutral location.
    """
    if mutmut_configuration._config is not None:
        return
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.mkdir(os.path.join(tmp, "src"))
        os.chdir(tmp)
        try:
            mutmut_configuration.config()
        finally:
            os.chdir(cwd)


def generate(root: Path, rel_file: str) -> list[Mutant]:
    _default_config()
    code = (root / rel_file).read_text()
    module, mutations, _, _ = create_mutations(rel_file, code)
    positions = MetadataWrapper(module, unsafe_skip_copy=True).resolve(PositionProvider)
    out: list[Mutant] = []
    for m in mutations:
        func = m.contained_by_top_level_function
        if not isinstance(func, cst.FunctionDef) or func.asynchronous is not None:
            # mutmut only applies mutants inside top-level functions and methods. Async
            # functions are excluded so eligibility matches the deletion population.
            continue
        pos = positions.get(m.original_node)
        if pos is None:
            continue
        mutated = module.deep_replace(m.original_node, m.mutated_node)
        assert isinstance(mutated, cst.Module)
        out.append(Mutant(
            file=rel_file,
            population="classical",
            operator="mutmut:" + type(m.original_node).__name__,
            start_line=pos.start.line,
            end_line=pos.end.line,
            original=module.code_for_node(m.original_node),
            replacement=module.code_for_node(m.mutated_node),
            function=_qualname(module, func, positions),
            mutated_source=mutated.code,
        ))
    return out


def _qualname(module: cst.Module, func: cst.FunctionDef, positions) -> str:
    # Top-level function or method; enclosing class found by position containment.
    fpos = positions[func]
    for stmt in module.body:
        if isinstance(stmt, cst.ClassDef):
            cpos = positions[stmt]
            if cpos.start.line <= fpos.start.line <= cpos.end.line:
                return f"{stmt.name.value}.{func.name.value}"
    return func.name.value
