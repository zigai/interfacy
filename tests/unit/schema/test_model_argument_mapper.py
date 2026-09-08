from typing import Any

import pytest

from interfacy.schema.model_argument_mapper import ModelArgumentMapper


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
    mapper = ModelArgumentMapper()

    assert mapper.is_plain_class_model(model_type)
    fields = mapper.model_fields_for_expansion(model_type)
    assert [(field.name, field.annotation, field.required, field.default) for field in fields] == [
        ("name", str, True, None),
        ("count", int, False, 2),
    ]
    assert mapper._plain_class_param_annotations(model_type) == {"name": str, "count": int}


def test_plain_class_field_descriptions_keep_class_docstring_fallback() -> None:
    mapper = ModelArgumentMapper()

    fields = mapper.model_fields_for_expansion(NamedModel)

    assert [(field.name, field.description) for field in fields] == [
        ("name", "Display name."),
        ("count", "Number of copies."),
    ]


@pytest.mark.parametrize("model_type", [str, int, float, bool, bytes, list, dict, tuple, set])
def test_plain_class_discovery_excludes_builtins(model_type: type) -> None:
    assert ModelArgumentMapper().is_plain_class_model(model_type) is False


def test_plain_class_discovery_does_not_cache_initializer_parameters(monkeypatch) -> None:
    class ChangingModel:
        def __init__(self, first: int) -> None:
            self.first = first

    class ReplacementModel:
        def __init__(self, second: str) -> None:
            self.second = second

    mapper = ModelArgumentMapper()
    assert mapper._plain_class_param_annotations(ChangingModel) == {"first": int}

    monkeypatch.setattr(ChangingModel, "__init__", ReplacementModel.__init__)

    assert mapper._plain_class_param_annotations(ChangingModel) == {"second": str}
    assert [field.name for field in mapper.model_fields_for_expansion(ChangingModel)] == ["second"]


@pytest.mark.parametrize("error_type", [AttributeError, TypeError, ValueError])
def test_plain_class_discovery_tolerates_reflection_failures(
    monkeypatch,
    error_type: type[Exception],
) -> None:
    def failed_inspection(*args: Any, **kwargs: Any) -> Any:
        raise error_type("unsupported reflection target")

    monkeypatch.setattr("interfacy.schema.model_argument_mapper.Class", failed_inspection)
    mapper = ModelArgumentMapper()

    assert mapper.is_plain_class_model(NamedModel) is False
    assert mapper._plain_class_model_fields_for_expansion(NamedModel) == []
    assert mapper._plain_class_param_annotations(NamedModel) == {}
