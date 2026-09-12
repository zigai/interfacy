from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter as InspectParameter
from typing import TYPE_CHECKING, Any

from objinspect import Parameter

from interfacy.exceptions import ReservedFlagError
from interfacy.schema.arguments import EffectiveCommandSettings, ParamSpec
from interfacy.schema.schema import MODEL_DEFAULT_UNSET, Argument
from interfacy.schema.typing import normalize_basic_annotation

if TYPE_CHECKING:
    from interfacy.schema.builder import ParserSchemaBuilder

_ABBREVIATION_SCOPE_ALL_OPTIONS = "all_options"


@dataclass
class ModelExpansionBuilder:
    """Build expanded CLI arguments for one model parameter."""

    builder: ParserSchemaBuilder
    param: Parameter
    taken_flags: list[str]
    settings: EffectiveCommandSettings

    def build(self, *, model_type: type, is_optional_model: bool) -> list[Argument]:
        translated_name = self.builder.context.flag_strategy.argument_translator.translate(
            self.param.name
        )
        if translated_name in self.taken_flags:
            raise ReservedFlagError(translated_name)

        self.taken_flags.append(translated_name)

        model_default = self.param.default if self.param.has_default else MODEL_DEFAULT_UNSET

        return self._fields(
            model_type=model_type,
            root_name=self.param.name,
            path=(self.param.name,),
            depth=1,
            parent_optional=is_optional_model,
            parent_has_default=self.param.has_default,
            original_model_type=model_type,
            model_default=model_default,
            root_is_optional=is_optional_model,
        )

    def _fields(
        self,
        *,
        model_type: type,
        root_name: str,
        path: tuple[str, ...],
        depth: int,
        parent_optional: bool,
        parent_has_default: bool,
        original_model_type: type,
        model_default: Any,
        root_is_optional: bool,
    ) -> list[Argument]:
        arguments: list[Argument] = []
        max_depth = self.settings.model_expansion_max_depth

        for field in self.builder.model_argument_mapper.model_fields_for_expansion(model_type):
            annotation = normalize_basic_annotation(field.annotation)
            inner_type, is_optional_model = self.builder.model_argument_mapper.unwrap_optional(
                annotation
            )
            new_path = (*path, field.name)

            if self.builder._should_expand_model(inner_type, settings=self.settings) and (
                depth < max_depth
            ):
                arguments.extend(
                    self._fields(
                        model_type=inner_type,
                        root_name=root_name,
                        path=new_path,
                        depth=depth + 1,
                        parent_optional=parent_optional or is_optional_model,
                        parent_has_default=parent_has_default,
                        original_model_type=original_model_type,
                        model_default=model_default,
                        root_is_optional=root_is_optional,
                    )
                )
                continue

            arguments.append(
                self._argument_for_field(
                    field=field,
                    annotation=annotation,
                    path=new_path,
                    root_name=root_name,
                    is_optional_model=is_optional_model,
                    parent_optional=parent_optional,
                    parent_has_default=parent_has_default,
                    original_model_type=original_model_type,
                    model_default=model_default,
                    root_is_optional=root_is_optional,
                )
            )

        return arguments

    def _argument_for_field(
        self,
        *,
        field: Any,
        annotation: Any,
        path: tuple[str, ...],
        root_name: str,
        is_optional_model: bool,
        parent_optional: bool,
        parent_has_default: bool,
        original_model_type: type,
        model_default: Any,
        root_is_optional: bool,
    ) -> Argument:
        translated_path = tuple(
            self.builder.context.flag_strategy.argument_translator.translate(part) for part in path
        )
        nested_separator = self.builder._nested_separator
        display_name = nested_separator.join(translated_path)
        if display_name in self.taken_flags:
            raise ReservedFlagError(display_name)

        arg_name = nested_separator.join(path)
        flags = self._option_flags(
            display_name=display_name,
            annotation=annotation,
            field_default=field.default,
        )
        self.taken_flags.append(display_name)

        is_required = field.required and not (
            parent_optional or is_optional_model or parent_has_default
        )
        spec = ParamSpec(
            name=arg_name,
            type=annotation,
            is_typed=annotation is not None,
            has_default=not field.required,
            default=field.default,
            is_required=is_required,
            is_optional=is_optional_model,
            kind=InspectParameter.POSITIONAL_OR_KEYWORD,
            description=field.description or field.name,
        )

        return self.builder._argument_from_spec(
            spec=spec,
            translated_name=display_name,
            flags=flags,
            taken_flags=self.taken_flags,
            pipe_param_names=None,
            allow_optional_union_list=False,
            suppress_parse_default=True,
            force_optional=False,
            help_text=None,
            is_expanded_from=root_name,
            expansion_path=path,
            original_model_type=original_model_type,
            parent_is_optional=root_is_optional,
            model_default=model_default,
            settings=self.settings,
        )

    def _option_flags(
        self,
        *,
        display_name: str,
        annotation: Any,
        field_default: Any,
    ) -> tuple[str, ...]:
        long_flag = f"--{display_name}"
        flags: tuple[str, ...] = (long_flag,)
        if self.settings.abbreviation_scope != _ABBREVIATION_SCOPE_ALL_OPTIONS:
            return flags

        abbrev_name = display_name
        if annotation is bool and field_default is True:
            abbrev_name = f"no-{display_name}"

        short = self.builder.context.abbreviation_gen.generate(abbrev_name, self.taken_flags)
        if short and short not in (display_name, abbrev_name):
            return (f"-{short}", long_flag)

        return flags
