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
from libcst._nodes.internal import CodegenState
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
    base = module.code
    # Character span of each top-level statement, and of each statement directly inside a
    # top-level class. A mutant is applied by rewriting only the smallest of these that contains
    # it, which gives exactly the text module.deep_replace(...) would at the cost of that block.
    spans: list[tuple[cst.CSTNode, int, int, tuple[str, ...]]] = []
    cursor = 0
    for stmt in module.body:
        text = module.code_for_node(stmt)
        at = base.find(text, cursor)
        cursor = at + len(text)
        if isinstance(stmt, cst.ClassDef) and isinstance(stmt.body, cst.IndentedBlock):
            indent = (stmt.body.indent or module.default_indent,)
            inner = at
            for child in stmt.body.body:
                ctext = _render(module, child, indent)
                cat = base.find(ctext, inner)
                if cat < 0 or cat >= cursor:
                    break
                spans.append((child, cat, cat + len(ctext), indent))
                inner = cat + len(ctext)
        spans.append((stmt, at, at + len(text), ()))
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
        stmt, s0, s1, indent = _containing(spans, positions, pos.start.line)
        mutated_stmt = stmt.deep_replace(m.original_node, m.mutated_node)
        out.append(Mutant(
            file=rel_file,
            population="classical",
            operator="mutmut:" + type(m.original_node).__name__,
            start_line=pos.start.line,
            end_line=pos.end.line,
            original=module.code_for_node(m.original_node),
            replacement=module.code_for_node(m.mutated_node),
            function=_qualname(module, func, positions),
            base=base, edit_start=s0, edit_end=s1, edit_text=_render(module, mutated_stmt, indent),
        ))
    return out


def _containing(spans, positions, line: int):
    """Smallest recorded block containing ``line``: class members are listed before their class."""
    for stmt, s0, s1, indent in spans:
        p = positions[stmt]
        if p.start.line <= line <= p.end.line:
            return stmt, s0, s1, indent
    raise LookupError(f"no top-level statement contains line {line}")


def _render(module: cst.Module, node: cst.CSTNode, indent: tuple[str, ...]) -> str:
    """Code for ``node`` as it appears in the module, at the given indentation."""
    state = CodegenState(default_indent=module.default_indent, default_newline=module.default_newline)
    state.indent_tokens.extend(indent)
    node._codegen(state)
    return "".join(state.tokens)


def _reference(root: Path, rel_file: str) -> list[str]:
    """The original whole-module construction, kept to test that generate() is identical."""
    _default_config()
    code = (root / rel_file).read_text()
    module, mutations, _, _ = create_mutations(rel_file, code)
    positions = MetadataWrapper(module, unsafe_skip_copy=True).resolve(PositionProvider)
    out = []
    for m in mutations:
        func = m.contained_by_top_level_function
        if not isinstance(func, cst.FunctionDef) or func.asynchronous is not None:
            continue
        if positions.get(m.original_node) is None:
            continue
        out.append(module.deep_replace(m.original_node, m.mutated_node).code)
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
