from typing import Dict, List, Optional, Union

from stdl.fs import File

from tests.fixtures.models import Color, ColorLiteral


def pow(base: int, exponent: int = 2) -> int:  # noqa: A001 - intentional command name
    """
    Raise base to the power of exponent.

    Args:
        base (int): The base number.
        exponent (int, optional): The power to which the base is raised.

    Returns:
        int: Result of base raised to exponent.
    """
    return base**exponent


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}!"


def fn_enum_arg(color: Color):
    return color


def fn_literal_arg(color: ColorLiteral):
    return color


def fn_enum_optional(color: Color | None = None):
    return color


def fn_literal_optional(color: ColorLiteral | None = None):
    return color


def fn_bool_required(value: bool):
    return value


def fn_bool_default_true(value: bool = True):
    return value


def fn_bool_default_false(value: bool = False):
    return value


def fn_bool_short_flag(x: bool = False):
    return x


def fn_list_int(values: list[int]):
    return values


def fn_list_with_default(values: list[int] = [1, 2]):  # noqa: B006 - intentional for tests
    return values


def fn_two_lists(strings: list[str], ints: list[int]) -> tuple[int, int]:
    return len(strings), len(ints)


def fn_list_str(items: list[str]):
    """Required list of strings."""
    return items


def fn_list_str_optional(items: list[str] | None = None):
    """Optional union list of strings (defaults to None)."""
    return items


def fn_list_int_optional(values: list[int] | None = None):
    """Optional union list of ints (defaults to None)."""
    return values


def fn_str_required(name: str) -> str:
    return name


def fn_str_optional(name: str = "default") -> str:
    return name


def fn_float_required(value: float) -> float:
    return value


def fn_path_required(path: File) -> File:
    return path


def fn_optional_str(value: str | None = None) -> str | None:
    return value


def fn_optional_int(value: int | None = None) -> int | None:
    return value


def fn_mixed_optional(
    required: str,
    optional_int: int | None = None,
    optional_str: str = "default",
) -> dict[str, object]:
    return {
        "required": required,
        "optional_int": optional_int,
        "optional_str": optional_str,
    }


def fn_positional_only(a: int, b: int, /) -> int:
    return a + b


def fn_keyword_only(*, a: int, b: int) -> int:
    return a + b


def fn_varargs(*args: int) -> int:
    return sum(args)


def fn_positional_varargs(head: str, *tail: str) -> tuple[str, tuple[str, ...]]:
    """Collect one required positional value with trailing varargs."""
    return head, tail


def fn_positional_varargs_kwonly(
    head: str,
    *tail: str,
    mode: str = "default",
) -> tuple[str, tuple[str, ...], str]:
    """Collect required positional + varargs + keyword-only option."""
    return head, tail, mode


def fn_positional_varargs_varkw(
    head: str,
    *tail: str,
    **options: dict[str, str],
) -> tuple[str, tuple[str, ...], dict[str, str]]:
    """Collect required positional + varargs + catch-all keyword mapping."""
    return head, tail, options


def fn_kwargs(**kwargs: str) -> dict[str, str]:
    return kwargs


def fn_all_zones(a: int, /, b: int, *, c: int) -> int:
    return a + b + c


def fn_legacy_list(x: List[int]) -> List[int]:
    return x


def fn_legacy_dict(x: Dict[str, int]) -> Dict[str, int]:
    return x


def fn_legacy_optional(x: Optional[int] = None) -> Optional[int]:
    return x


def fn_legacy_union(x: Union[int, str]) -> Union[int, str]:
    return x


def attach(container: str) -> str:
    """Attach to a container."""
    return f"Attached to {container}"


def detach(container: str) -> str:
    """Detach from a container."""
    return f"Detached from {container}"
