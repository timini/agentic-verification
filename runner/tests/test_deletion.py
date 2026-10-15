import ast
import textwrap

from tsa.mutation import deletion


def _gen(tmp_path, src):
    (tmp_path / "m.py").write_text(textwrap.dedent(src))
    return deletion.generate(tmp_path, "m.py")


def test_line_numbers_preserved_and_code_compiles(tmp_path):
    muts = _gen(tmp_path, '''
        def f(x: int) -> int:
            """Doc."""
            y = x + 1
            log(
                y,
            )
            return y
    ''')
    assert {m.operator for m in muts} == {"body:None", "body:0", "body:1", "call-delete"}
    original_lines = (tmp_path / "m.py").read_text().count("\n")
    for m in muts:
        compile(m.mutated_source, "m.py", "exec")
        assert m.mutated_source.count("\n") == original_lines
    call = next(m for m in muts if m.operator == "call-delete")
    assert call.mutated_source.splitlines()[call.start_line - 1].strip() == "pass"
    body = next(m for m in muts if m.operator == "body:0")
    assert '"""Doc."""' in body.mutated_source  # docstring kept


def test_generators_async_and_decorated_are_not_body_replaced(tmp_path):
    muts = _gen(tmp_path, '''
        import contextlib

        def gen():
            yield 1

        async def coro():
            await other()

        @contextlib.contextmanager
        def cm():
            setup()
            yield

        class C:
            @staticmethod
            def s():
                return 2
    ''')
    funcs = {(m.function, m.operator) for m in muts}
    assert ("gen", "body:None") not in funcs
    assert not any(f in ("coro", "cm") for f, _ in funcs)
    assert ("C.s", "body:None") in funcs


def test_trivial_bodies_skipped(tmp_path):
    muts = _gen(tmp_path, '''
        def a():
            pass

        def b():
            raise NotImplementedError

        def c():
            ...
    ''')
    assert muts == []


def test_shared_line_statements_skipped(tmp_path):
    muts = _gen(tmp_path, '''
        def f():
            a(); b()
            return 1
    ''')
    assert not [m for m in muts if m.operator == "call-delete"]


def test_body_replacements_follow_annotation():
    fn = ast.parse("def f() -> list[int]:\n    return [1]\n").body[0]
    assert deletion.body_replacements(fn) == ["None", "[]"]
    init = ast.parse("def __init__(self) -> None:\n    self.x = 1\n").body[0]
    assert deletion.body_replacements(init) == ["None"]
