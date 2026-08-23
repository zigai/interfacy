from dataclasses import dataclass
from interfacy import Interfacy

@dataclass
class Inner:
    val: int = 10

@dataclass
class Outer:
    inner: Inner

def main_outer(o: Outer) -> Outer:
    return o

def test_nested_model_defaults_argparse():
    app = Interfacy(backend="argparse", sys_exit_enabled=False)
    result = app.run(main_outer, args=[])
    assert isinstance(result, Outer)
    assert result.inner.val == 10

def test_nested_model_override_argparse():
    app = Interfacy(backend="argparse", sys_exit_enabled=False)
    result = app.run(main_outer, args=["--o.inner.val", "42"])
    assert isinstance(result, Outer)
    assert result.inner.val == 42
