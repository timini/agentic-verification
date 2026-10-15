"""Deterministic deletion mutants: whole-function body replacement and call-statement deletion.

Mutants are spliced by line so that every line keeps its number: the first line of the removed
region becomes ``return <value>`` or ``pass`` and the rest become blank. Coverage data and the
activation check can then refer to the same line numbers in original and mutant.

Eligibility matches the classical population (mutmut): top-level functions and methods of
top-level classes, undecorated apart from ``staticmethod``/``classmethod``.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

from .model import Mutant

NEVER_MUTATE = {"__getattribute__", "__setattr__", "__new__"}  # same as mutmut
ALLOWED_DECORATORS = {"staticmethod", "classmethod"}

# Return-annotation name -> replacement expressions, after the always-tried ``None``.
CONSTANTS_BY_ANNOTATION = {
    "int": ["0", "1"],
    "float": ["0.0"],
    "str": ['""'],
    "bytes": ['b""'],
    "bool": ["True", "False"],
    "list": ["[]"], "List": ["[]"], "Sequence": ["[]"], "Iterable": ["[]"], "Iterator": ["iter(())"],
    "dict": ["{}"], "Dict": ["{}"], "Mapping": ["{}"],
    "set": ["set()"], "Set": ["set()"], "frozenset": ["frozenset()"],
    "tuple": ["()"], "Tuple": ["()"],
}


@dataclass(frozen=True)
class FunctionSite:
    qualname: str
    node: ast.FunctionDef


def eligible_functions(tree: ast.Module) -> list[FunctionSite]:
    out = []
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and _eligible(stmt):
            out.append(FunctionSite(stmt.name, stmt))
        elif isinstance(stmt, ast.ClassDef):
            for m in stmt.body:
                if isinstance(m, ast.FunctionDef) and _eligible(m):
                    out.append(FunctionSite(f"{stmt.name}.{m.name}", m))
    return out


def _eligible(fn: ast.FunctionDef) -> bool:
    if fn.name in NEVER_MUTATE:
        return False
    for d in fn.decorator_list:
        if not (isinstance(d, ast.Name) and d.id in ALLOWED_DECORATORS):
            return False
    return True


def generate(root: Path, rel_file: str) -> list[Mutant]:
    source = (root / rel_file).read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines(keepends=True)
    out: list[Mutant] = []
    for site in eligible_functions(tree):
        out.extend(_body_mutants(rel_file, source, lines, site))
        out.extend(_call_mutants(rel_file, source, lines, site))
    return out


def body_replacements(fn: ast.FunctionDef) -> list[str]:
    values = ["None"]
    ann = fn.returns
    name = None
    if isinstance(ann, ast.Name):
        name = ann.id
    elif isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
        name = ann.value.id
    elif isinstance(ann, ast.Attribute):
        name = ann.attr
    elif isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        name = ann.value.split("[", 1)[0].rsplit(".", 1)[-1]
    if fn.name == "__init__" or (isinstance(ann, ast.Constant) and ann.value is None):
        return values
    values.extend(CONSTANTS_BY_ANNOTATION.get(name or "", []))
    return values


def _body_mutants(rel_file, source, lines, site: FunctionSite) -> list[Mutant]:
    fn = site.node
    body = list(fn.body)
    if body and _is_docstring(body[0]):
        body = body[1:]
    if not body or _is_trivial(body) or _is_generator(fn):
        return []
    first, last = body[0], body[-1]
    if first.lineno == fn.lineno or not _starts_line(lines, first) or not _ends_line(lines, last):
        return []
    indent = lines[first.lineno - 1][: first.col_offset]
    out = []
    for value in body_replacements(fn):
        new_first = f"{indent}return {value}\n"
        mutated = _splice(lines, first.lineno, last.end_lineno, new_first)
        out.append(Mutant(
            file=rel_file, population="deletion", operator=f"body:{value}",
            start_line=first.lineno, end_line=last.end_lineno,
            original="".join(lines[first.lineno - 1 : last.end_lineno]),
            replacement=new_first, function=site.qualname, mutated_source=mutated,
        ))
    return out


def _call_mutants(rel_file, source, lines, site: FunctionSite) -> list[Mutant]:
    out = []
    for node in ast.walk(site.node):
        if not isinstance(node, ast.Expr):
            continue
        value = node.value.value if isinstance(node.value, ast.Await) else node.value
        if not isinstance(value, ast.Call):
            continue
        if not _starts_line(lines, node) or not _ends_line(lines, node):
            continue
        indent = lines[node.lineno - 1][: node.col_offset]
        new_first = f"{indent}pass\n"
        out.append(Mutant(
            file=rel_file, population="deletion", operator="call-delete",
            start_line=node.lineno, end_line=node.end_lineno,
            original="".join(lines[node.lineno - 1 : node.end_lineno]),
            replacement=new_first, function=site.qualname,
            mutated_source=_splice(lines, node.lineno, node.end_lineno, new_first),
        ))
    return out


def _splice(lines: list[str], start: int, end: int, first: str) -> str:
    blanks = ["\n"] * (end - start)
    return "".join(lines[: start - 1] + [first] + blanks + lines[end:])


def _starts_line(lines, node) -> bool:
    return lines[node.lineno - 1][: node.col_offset].strip() == ""


def _ends_line(lines, node) -> bool:
    rest = lines[node.end_lineno - 1][node.end_col_offset :].strip()
    return rest == "" or rest.startswith("#")


def _is_docstring(stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def _is_trivial(body) -> bool:
    """Bodies with no behaviour to remove: pass, ``...``, or raising NotImplementedError."""
    if len(body) != 1:
        return False
    s = body[0]
    if isinstance(s, ast.Pass):
        return True
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis:
        return True
    if isinstance(s, ast.Raise) and s.exc is not None:
        exc = s.exc.func if isinstance(s.exc, ast.Call) else s.exc
        return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"
    if isinstance(s, ast.Return) and (s.value is None or (isinstance(s.value, ast.Constant) and s.value.value is None)):
        return True
    return False


def _is_generator(fn: ast.FunctionDef) -> bool:
    """True if ``fn`` itself (not a nested function) yields."""
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.Yield, ast.YieldFrom)):
            return True
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(n))
    return False
