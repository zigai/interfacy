import typing
from typing import Any

import pytest

from interfacy.schema.typing import normalize_basic_annotation, simplified_type_name


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        ("dict[builtins.str, mypkg.Foo]", "dict[str, Foo]"),
        ("typing.Literal['a  b', 'a.b']", "Literal['a  b', 'a.b']"),
        ("Literal['a | None', 'None | b']", "Literal['a | None', 'None | b']"),
        (r"Literal['a\'  b', 'x[y],None']", r"Literal['a\'  b', 'x[y],None']"),
        ("list[int | None]", "list[int | None]"),
        ("dict[str, list[mypkg.Foo | None]]", "dict[str, list[Foo | None]]"),
        ("typing.Union[tuple[int, str], None]", "tuple[int, str]?"),
        ("typing.Union[None, tuple[int, str]]", "tuple[int, str]?"),
        ("typing.Optional[list[int | None]]", "list[int | None]?"),
        ("typing.Literal['a | None'] | None", "Literal['a | None']?"),
        ("int | str | None", "int | str?"),
        ("None | int", "int?"),
        ("Union[int, str]", "Union[int, str]"),
        ("  mypkg.Foo  |  None  ", "Foo?"),
        ("mypkg.Unknown[", "Unknown["),
        ("list[int | None", "list[int | None"),
        ("Union[int), None]", "Union[int), None]"),
    ],
)
def test_type_names_preserve_literal_and_nested_expression_boundaries(
    annotation: str,
    expected: str,
) -> None:
    assert simplified_type_name(annotation) == expected


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (bool, bool),
        ("bool", bool),
        ("builtins.int", int),
        ("Optional[float]", float),
        ("str | None", str),
    ],
)
def test_basic_annotation_normalization_resolves_supported_builtins(
    annotation: Any,
    expected: type,
) -> None:
    assert normalize_basic_annotation(annotation) is expected


@pytest.mark.parametrize(
    "annotation",
    [None, object(), bool | None, "mypkg.Unknown", "list[int]", "list[int | None]"],
)
def test_basic_annotation_normalization_preserves_other_annotation_objects(
    annotation: Any,
) -> None:
    assert normalize_basic_annotation(annotation) is annotation


def test_basic_annotation_normalization_resolves_type_aliases() -> None:
    alias_type = getattr(typing, "TypeAliasType", None)
    if alias_type is None:
        pytest.skip("PEP 695 aliases require Python 3.12+")

    assert normalize_basic_annotation(alias_type("Count", int)) is int
