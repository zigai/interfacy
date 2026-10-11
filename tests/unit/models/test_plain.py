import pytest

from interfacy import Interfacy
from interfacy.models import (
    build_model_instance,
    is_plain_class_model,
    model_fields_for_expansion,
)
from interfacy.models.plain import plain_class_param_annotations


class NamedModel:
    """A model with variadic constructor details that are not CLI fields.

    Args:
        name: Display name.
        count: Number of copies.
    """

    def __init__(self, name: str, *extras: str, count: int = 2, **metadata: str) -> None:
        self.name = name
        self.count = count


class InheritedModel(NamedModel):
    """Reuse the parent's initializer."""


@pytest.mark.parametrize("model_type", [NamedModel, InheritedModel])
def test_plain_class_discovery_keeps_named_initializer_parameters(model_type: type) -> None:
    assert is_plain_class_model(model_type)
    fields = model_fields_for_expansion(model_type)
    assert [(field.name, field.annotation, field.required, field.default) for field in fields] == [
        ("name", str, True, None),
        ("count", int, False, 2),
    ]
    assert plain_class_param_annotations(model_type) == {"name": str, "count": int}


def test_plain_class_field_descriptions_keep_class_docstring_fallback() -> None:
    fields = model_fields_for_expansion(NamedModel)

    assert [(field.name, field.description) for field in fields] == [
        ("name", "Display name."),
        ("count", "Number of copies."),
    ]


@pytest.mark.parametrize("model_type", [str, int, float, bool, bytes, list, dict, tuple, set])
def test_plain_class_discovery_excludes_builtins(model_type: type) -> None:
    assert is_plain_class_model(model_type) is False


class PositionalModel:
    def __init__(
        self,
        name: str,
        count: int = 2,
        suffix: str = "!",
        /,
        *,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.count = count
        self.suffix = suffix
        self.enabled = enabled


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"name": "x"}, ("x", 2, "!", True)),
        ({"name": "x", "suffix": "?", "enabled": False}, ("x", 2, "?", False)),
        ({"name": "x", "count": 3, "suffix": "?"}, ("x", 3, "?", True)),
    ],
)
def test_plain_class_reconstructs_positional_only_with_defaults(
    values: dict[str, object],
    expected: tuple[str, int, str, bool],
) -> None:
    model = build_model_instance(PositionalModel, values)

    assert (model.name, model.count, model.suffix, model.enabled) == expected


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_plain_class_cli_reconstructs_positional_only_and_keyword_only(backend: str) -> None:
    def command(model: PositionalModel) -> PositionalModel:
        return model

    model = Interfacy(backend=backend).invoke(
        command,
        args=["--model.name", "x", "--model.suffix", "?", "--no-model.enabled"],
    )

    assert (model.name, model.count, model.suffix, model.enabled) == ("x", 2, "?", False)
