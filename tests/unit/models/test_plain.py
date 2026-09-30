import pytest

from interfacy.models import is_plain_class_model, model_fields_for_expansion
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
