from __future__ import annotations

import inspect
from dataclasses import asdict, fields, is_dataclass
from types import NoneType
from typing import Any

from objinspect import Class
from objinspect.typing import is_union_type, type_args

from interfacy.schema.schema import MODEL_DEFAULT_UNSET, Argument
from interfacy.util import resolve_type_alias

OBJINSPECT_CLASS_ERRORS = (AttributeError, TypeError, ValueError)


class ModelArgumentMapper:
    """Shared model flattening/reconstruction helpers for schema builder and runner."""

    def unwrap_optional(self, annotation: object) -> tuple[object, bool]:
        annotation = resolve_type_alias(annotation)
        if not is_union_type(annotation):
            return annotation, False
        union_args = type_args(annotation)
        if NoneType not in union_args or len(union_args) != 2:
            return annotation, False
        inner = next(arg for arg in union_args if arg is not NoneType)
        return inner, True

    @staticmethod
    def is_pydantic_model(typ: object) -> bool:
        return isinstance(typ, type) and (
            hasattr(typ, "model_fields") or hasattr(typ, "__fields__")
        )

    def is_plain_class_model(self, annotation: object) -> bool:
        if not isinstance(annotation, type):
            return False
        if annotation in {str, int, float, bool, bytes, list, dict, tuple, set}:
            return False
        try:
            cls_info = Class(
                annotation,
                init=True,
                public=True,
                inherited=True,
                static_methods=True,
                protected=False,
                private=False,
                classmethod=True,
            )
        except OBJINSPECT_CLASS_ERRORS:
            return False
        init_method = cls_info.init_method
        if init_method is None:
            return False
        params = [
            param
            for param in init_method.params
            if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        return len(params) > 0

    def is_model_type(self, annotation: object) -> bool:
        if not isinstance(annotation, type):
            return False
        if (
            is_dataclass(annotation)
            or hasattr(annotation, "model_fields")
            or hasattr(annotation, "__fields__")
        ):
            return True
        return self.is_plain_class_model(annotation)

    def should_expand_model(self, param_type: object, *, expand_model_params: bool = True) -> bool:
        if not expand_model_params:
            return False
        if not isinstance(param_type, type):
            return False
        if is_dataclass(param_type) or self.is_pydantic_model(param_type):
            return True
        return self.is_plain_class_model(param_type)

    def reconstruct_expanded_models(
        self,
        args: dict[str, Any],
        arguments: list[Argument],
    ) -> dict[str, Any]:
        grouped = self._group_expanded_arguments(arguments)
        if not grouped:
            return args

        for root_name, group in grouped.items():
            self._reconstruct_expanded_model_group(args, root_name, group)

        return args

    @staticmethod
    def _group_expanded_arguments(arguments: list[Argument]) -> dict[str, list[Argument]]:
        grouped: dict[str, list[Argument]] = {}
        for arg in arguments:
            if arg.is_expanded_from is None:
                continue
            grouped.setdefault(arg.is_expanded_from, []).append(arg)
        return grouped

    def _reconstruct_expanded_model_group(
        self,
        args: dict[str, Any],
        root_name: str,
        group: list[Argument],
    ) -> None:
        model_type = group[0].original_model_type
        if model_type is None:
            return
        if root_name in args and not any(arg.name in args for arg in group):
            return

        model_default = group[0].model_default
        has_model_default = model_default is not MODEL_DEFAULT_UNSET
        values, provided = self._collect_model_values(args, group)
        args[root_name] = self._build_reconstructed_model_value(
            model_type,
            group,
            values,
            provided,
            model_default,
            has_model_default,
        )

        for arg in group:
            args.pop(arg.name, None)

    def _build_reconstructed_model_value(
        self,
        model_type: type,
        group: list[Argument],
        values: dict[str, Any],
        provided: bool,
        model_default: object,
        has_model_default: bool,
    ) -> object:
        if not provided:
            if has_model_default:
                return model_default
            if any(arg.parent_is_optional for arg in group):
                return None
            return self._build_model_instance(model_type, values)

        if has_model_default and model_default is not None:
            base_values = self._model_instance_to_values(model_type, model_default)
            merged = self._deep_merge(base_values, values)
            return self._build_model_instance(model_type, merged)

        return self._build_model_instance(model_type, values)

    def _deep_merge(self, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _model_instance_to_values(self, model_type: type, instance: object) -> dict[str, Any]:
        if instance is None:
            return {}
        if is_dataclass(model_type):
            return asdict(instance)
        dumped_values = self._dump_model_instance(instance)
        if dumped_values is not None:
            return dumped_values
        if hasattr(instance, "__dict__"):
            return self._values_from_instance_dict(instance)
        if self.is_plain_class_model(model_type):
            return self._values_from_plain_class(model_type, instance)
        return {}

    @staticmethod
    def _dump_model_instance(instance: object) -> dict[str, Any] | None:
        if hasattr(instance, "model_dump"):
            dumped = instance.model_dump()
            if isinstance(dumped, dict):
                return dumped
        if hasattr(instance, "dict"):
            dumped = instance.dict()
            if isinstance(dumped, dict):
                return dumped
        return None

    def _values_from_instance_dict(self, instance: object) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, value in vars(instance).items():
            if self.is_model_type(type(value)):
                values[key] = self._model_instance_to_values(type(value), value)
            else:
                values[key] = value
        return values

    def _values_from_plain_class(self, model_type: type, instance: object) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key in self._plain_class_param_annotations(model_type):
            if not hasattr(instance, key):
                continue
            values[key] = getattr(instance, key)
        return values

    @staticmethod
    def _collect_model_values(
        args: dict[str, Any],
        expanded_args: list[Argument],
    ) -> tuple[dict[str, Any], bool]:
        values: dict[str, Any] = {}
        provided = False

        for arg in expanded_args:
            if arg.name not in args:
                continue
            provided = True
            path = arg.expansion_path[1:] if arg.expansion_path else ()
            if not path:
                continue
            current = values
            for part in path[:-1]:
                current = current.setdefault(part, {})
            current[path[-1]] = args[arg.name]

        return values, provided

    def _build_model_instance(self, model_type: type, values: dict[str, Any]) -> object:
        if is_dataclass(model_type):
            kwargs: dict[str, Any] = {}
            for field in fields(model_type):
                if field.name in values:
                    kwargs[field.name] = self._coerce_model_value(field.type, values[field.name])
            return model_type(**kwargs)

        if hasattr(model_type, "model_fields"):
            kwargs = self._coerce_pydantic_values(model_type, values)
            return model_type(**kwargs)

        if hasattr(model_type, "__fields__"):
            kwargs = self._coerce_pydantic_values(model_type, values)
            return model_type(**kwargs)

        if self.is_plain_class_model(model_type):
            annotations = self._plain_class_param_annotations(model_type)
            kwargs = {}
            for key, value in values.items():
                ann = annotations.get(key)
                kwargs[key] = self._coerce_model_value(ann, value)
            return model_type(**kwargs)

        return values

    def _coerce_pydantic_values(self, model_type: type, values: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        field_map = getattr(model_type, "model_fields", None) or getattr(
            model_type, "__fields__", {}
        )
        for name, info in field_map.items():
            if name not in values:
                continue
            annotation = getattr(info, "annotation", None)
            if annotation is None:
                annotation = getattr(info, "outer_type_", None) or getattr(info, "type_", None)
            kwargs[name] = self._coerce_model_value(annotation, values[name])
        return kwargs

    def _coerce_model_value(self, annotation: object, value: object) -> object:
        if value is None:
            return None

        inner, is_optional = self.unwrap_optional(annotation)
        if isinstance(value, dict) and self.is_model_type(inner):
            if not value and is_optional:
                return None
            return self._build_model_instance(inner, value)
        return value

    def _plain_class_param_annotations(self, model_type: type) -> dict[str, Any]:
        try:
            cls_info = Class(
                model_type,
                init=True,
                public=True,
                inherited=True,
                static_methods=True,
                protected=False,
                private=False,
                classmethod=True,
            )
        except OBJINSPECT_CLASS_ERRORS:
            return {}
        init_method = cls_info.init_method
        if init_method is None:
            return {}
        annotations: dict[str, Any] = {}
        for param in init_method.params:
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            annotations[param.name] = param.type if param.is_typed else None
        return annotations


__all__ = ["ModelArgumentMapper"]
