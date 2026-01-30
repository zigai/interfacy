import inspect
from dataclasses import asdict, fields, is_dataclass
from types import NoneType
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs
from objinspect.typing import is_union_type, type_args

from interfacy.exceptions import ConfigurationError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import reverse_translations
from interfacy.pipe import apply_pipe_values
from interfacy.schema.schema import MODEL_DEFAULT_UNSET, Argument, Command
from interfacy.util import resolve_type_alias

if TYPE_CHECKING:
    from interfacy.argparse_backend.argparser import Argparser
    from interfacy.argparse_backend.argument_parser import ArgumentParser

logger = get_logger(__name__)

COMMAND_KEY_BASE = "command"


class ArgparseRunner:
    def __init__(
        self,
        namespace: dict[str, Any],
        builder: "Argparser",
        args: list[str],
        parser: "ArgumentParser",
    ) -> None:
        self._parser = parser
        self.namespace = namespace
        self.args = args
        self.builder = builder
        self.COMMAND_KEY = self.builder.COMMAND_KEY
        self._instance_chain: list[Any] = []

    def run(self) -> Any:
        commands = self.builder.commands
        if len(commands) == 0:
            raise ConfigurationError("No commands were provided")
        if len(commands) == 1:
            command = self.builder.get_commands()[0]
            if not command.is_leaf:
                group_args = self.namespace.get(command.canonical_name, {})
                return self._run_with_chain(command, group_args, depth=0)
            return self.run_command(command, self.namespace)
        return self.run_multiple(commands)

    def _apply_pipe(
        self,
        command: Command,
        args: dict[str, Any],
        *,
        subcommand: str | None = None,
    ) -> dict[str, Any]:
        config = self.builder.resolve_pipe_targets(command, subcommand=subcommand)
        if config is None:
            return args

        payload = self.builder.read_piped_input()
        if payload in (None, ""):
            return args

        parameters = self.builder.get_parameters_for(command, subcommand=subcommand)
        return apply_pipe_values(
            payload,
            config=config,
            arguments=args,
            parameters=parameters,
            type_parser=self.builder.type_parser,
        )

    def run_command(self, command: Command, args: dict[str, Any]) -> Any:
        obj = command.obj
        if isinstance(obj, Function):
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(args, self._arguments_for(command))
            return self.run_function(obj, args)
        if isinstance(obj, Method):
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(
                args, [*self._initializer_for(command), *self._arguments_for(command)]
            )
            return self.run_method(obj, args)
        if isinstance(obj, Class):
            return self.run_class(command, args)
        raise InvalidCommandError(command.obj)

    def run_function(self, func: Function | Method, args: dict) -> Any:
        positional_args = []
        keyword_args = {}

        for param in func.params:
            if (
                param.name not in args
                and param.kind != inspect.Parameter.VAR_POSITIONAL
                and param.kind != inspect.Parameter.VAR_KEYWORD
            ):
                continue

            val = args.get(param.name)
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                positional_args.append(val)
            elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                keyword_args[param.name] = val
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                if val:
                    positional_args.extend(val)
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                keyword_args[param.name] = val
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                if val:
                    keyword_args.update(val)

        logger.info(
            f"Calling function '{func.name}' with args: {positional_args}, kwargs: {keyword_args}"
        )
        result = func.call(*positional_args, **keyword_args)

        logger.info(f"Result: {result}")
        return result

    def run_method(self, method: Method, args: dict) -> Any:
        cli_args = reverse_translations(args, self.builder.flag_strategy.argument_translator)
        instance = method.class_instance
        if instance:
            method_args, method_kwargs = split_args_kwargs(cli_args, method)
            return method.call(*method_args, **method_kwargs)

        instance = Class(method.cls)
        if instance.init_method:
            args_init, args_method = split_init_args(cli_args, instance, method)
            init_args, init_kwargs = split_args_kwargs(args_init, instance.init_method)
            logger.info(f"__init__ method args: {init_args}, kwargs: {init_kwargs}")
            instance.init(*init_args, **init_kwargs)
        else:
            args_method = cli_args
            if not method.is_static:
                instance.init()

        method_args, method_kwargs = split_args_kwargs(args_method, method)
        logger.info(
            f"Calling method '{method.name}' with args: {method_args}, kwargs: {method_kwargs}"
        )
        return instance.call_method(method.name, *method_args, **method_kwargs)

    def run_class(self, command: Command, args: dict) -> Any:
        cls = command.obj
        if not isinstance(cls, Class):
            raise TypeError(f"Expected {Class}, got {type(cls)}")

        command_name = args[self.COMMAND_KEY]
        command_args = args[command_name]
        del args[self.COMMAND_KEY]
        del args[command_name]
        logger.info(f"Namespace: {command_args}")

        resolved_name = self.builder.flag_strategy.command_translator.reverse(command_name)
        try:
            method = cls.get_method(command_name)
        except KeyError:
            method = cls.get_method(resolved_name)

        if not cls.is_initialized and not method.is_static:
            if cls.init_method:
                args = self._apply_pipe(command, args, subcommand="__init__")
                args = self._reconstruct_expanded_models(args, self._initializer_for(command))
                init_args, init_kwargs = split_args_kwargs(args, cls.init_method)
                logger.info(f"__init__ method args: {init_args}, kwargs: {init_kwargs}")
                cls.init(*init_args, **init_kwargs)
            else:
                cls.init()

        command_args = self._apply_pipe(command, command_args, subcommand=command_name)
        subcommand_spec = self._schema_subcommand_for(command, command_name)
        if subcommand_spec is not None:
            command_args = self._reconstruct_expanded_models(
                command_args, subcommand_spec.parameters
            )
        method_args, method_kwargs = split_args_kwargs(command_args, method)
        logger.info(
            f"Calling method '{method.name}' with args: {method_args}, kwargs: {method_kwargs}"
        )
        return cls.call_method(method.name, *method_args, **method_kwargs)

    def run_multiple(self, commands: dict[str, Command]) -> Any:
        command_name = self.namespace[self.COMMAND_KEY]
        command = self.builder.get_command_by_cli_name(command_name)
        args = self.namespace.get(command.canonical_name, {})

        if not command.is_leaf:
            return self._run_with_chain(command, args, depth=0)
        return self.run_command(command, args)

    def _run_with_chain(
        self,
        command: Command,
        args: dict[str, Any],
        depth: int,
        parent_instance: Any = None,
    ) -> Any:
        """
        Execute a command with chain instantiation support.

        For groups/classes: instantiate at this level, then recurse to subcommand.
        For leaf commands: execute with the accumulated instance chain.
        """
        current_instance = parent_instance

        initializer = self._initializer_for(command)
        if initializer:
            args = self._reconstruct_expanded_models(args, initializer)

        if command.is_instance and command.stored_instance is not None:
            current_instance = command.stored_instance

        elif command.command_type == "class" and command.obj is not None:
            cls = command.obj
            if isinstance(cls, Class):
                cls.is_initialized = False
                cls.instance = None
                init_args = self._extract_init_args(args, command.initializer)
                if init_args:
                    init_a, init_kw = split_args_kwargs(init_args, cls.init_method)
                    cls.init(*init_a, **init_kw)
                else:
                    cls.init()
                current_instance = cls.instance

                if parent_instance is not None:
                    try:
                        current_instance._parent = parent_instance
                    except AttributeError:
                        pass

        if command.is_leaf:
            return self._execute_leaf(command, args, current_instance)

        dest_key = f"{COMMAND_KEY_BASE}_{depth}" if depth > 0 else COMMAND_KEY_BASE
        if dest_key not in args:
            raise ConfigurationError(
                f"No subcommand specified for '{command.cli_name}'. "
                f"Available: {', '.join(command.subcommands.keys()) if command.subcommands else 'none'}"
            )

        subcommand_name = args[dest_key]

        if command.subcommands is None:
            raise ConfigurationError(f"Command '{command.cli_name}' has no subcommands")

        subcommand = None
        for sub_cmd in command.subcommands.values():
            if sub_cmd.cli_name == subcommand_name:
                subcommand = sub_cmd
                break
            if subcommand_name in sub_cmd.aliases:
                subcommand = sub_cmd
                break

        if subcommand is None:
            raise ConfigurationError(f"Unknown subcommand '{subcommand_name}'")

        subcommand_args = args.get(subcommand.cli_name, args.get(subcommand_name, {}))
        if not isinstance(subcommand_args, dict):
            subcommand_args = {}

        return self._run_with_chain(subcommand, subcommand_args, depth + 1, current_instance)

    def _extract_init_args(
        self,
        args: dict[str, Any],
        initializer: list[Argument],
    ) -> dict[str, Any]:
        """Extract arguments belonging to this level's initializer."""
        param_names = {arg.name for arg in initializer}
        return {k: v for k, v in args.items() if k in param_names}

    def _execute_leaf(
        self,
        command: Command,
        args: dict[str, Any],
        instance: Any | None,
    ) -> Any:
        """Execute a leaf command (function or method)."""
        obj = command.obj

        if isinstance(obj, Method):
            if instance is not None:
                args = self._apply_pipe(command, args)
                args = self._reconstruct_expanded_models(
                    args, [*self._initializer_for(command), *self._arguments_for(command)]
                )
                method_args, method_kwargs = split_args_kwargs(args, obj)
                logger.info(
                    f"Calling method '{obj.name}' on instance with args: {method_args}, kwargs: {method_kwargs}"
                )
                return obj.func(instance, *method_args, **method_kwargs)
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(
                args, [*self._initializer_for(command), *self._arguments_for(command)]
            )
            return self.run_method(obj, args)

        if isinstance(obj, Function):
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(args, self._arguments_for(command))
            return self.run_function(obj, args)

        raise InvalidCommandError(obj)

    def _reconstruct_expanded_models(
        self,
        args: dict[str, Any],
        arguments: list[Argument],
    ) -> dict[str, Any]:
        expanded = [arg for arg in arguments if arg.is_expanded_from]
        if not expanded:
            return args

        grouped: dict[str, list[Argument]] = {}
        for arg in expanded:
            if arg.is_expanded_from is None:
                continue
            grouped.setdefault(arg.is_expanded_from, []).append(arg)

        for root_name, group in grouped.items():
            model_type = group[0].original_model_type
            if model_type is None:
                continue

            if root_name in args and not any(arg.name in args for arg in group):
                continue

            model_default = group[0].model_default
            has_model_default = model_default is not MODEL_DEFAULT_UNSET
            values, provided = self._collect_model_values(args, group)
            if not provided:
                if has_model_default:
                    args[root_name] = model_default
                elif any(arg.parent_is_optional for arg in group):
                    args[root_name] = None
                else:
                    args[root_name] = self._build_model_instance(model_type, values)
            else:
                if has_model_default and model_default is not None:
                    base_values = self._model_instance_to_values(model_type, model_default)
                    merged = self._deep_merge(base_values, values)
                    args[root_name] = self._build_model_instance(model_type, merged)
                else:
                    args[root_name] = self._build_model_instance(model_type, values)

            for arg in group:
                args.pop(arg.name, None)

        return args

    def _schema_command_for(self, command: Command) -> Command | None:
        schema = getattr(self.builder, "_last_schema", None)
        if schema is None:
            return None
        return schema.commands.get(command.canonical_name)

    def _arguments_for(self, command: Command) -> list[Argument]:
        schema_cmd = self._schema_command_for(command)
        if schema_cmd is None:
            return command.parameters
        return schema_cmd.parameters

    def _initializer_for(self, command: Command) -> list[Argument]:
        schema_cmd = self._schema_command_for(command)
        if schema_cmd is None:
            return command.initializer
        return schema_cmd.initializer

    def _schema_subcommand_for(self, command: Command, name: str) -> Command | None:
        schema_cmd = self._schema_command_for(command)
        if schema_cmd is None or not schema_cmd.subcommands:
            return None
        for sub_cmd in schema_cmd.subcommands.values():
            if sub_cmd.cli_name == name or name in sub_cmd.aliases:
                return sub_cmd
        return None

    def _deep_merge(self, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _model_instance_to_values(self, model_type: type, instance: Any) -> dict[str, Any]:
        if instance is None:
            return {}
        if is_dataclass(model_type):
            return asdict(instance)
        if hasattr(instance, "model_dump"):
            return instance.model_dump()
        if hasattr(instance, "dict"):
            return instance.dict()
        if hasattr(instance, "__dict__"):
            values: dict[str, Any] = {}
            for key, value in vars(instance).items():
                if self._is_model_type(type(value)):
                    values[key] = self._model_instance_to_values(type(value), value)
                else:
                    values[key] = value
            return values
        if self._is_plain_class_model(model_type):
            values: dict[str, Any] = {}
            for key in self._plain_class_param_annotations(model_type).keys():
                try:
                    values[key] = getattr(instance, key)
                except AttributeError:
                    continue
            return values
        return {}

    def _collect_model_values(
        self,
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

    def _build_model_instance(self, model_type: type, values: dict[str, Any]) -> Any:
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

        if self._is_plain_class_model(model_type):
            annotations = self._plain_class_param_annotations(model_type)
            kwargs: dict[str, Any] = {}
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

    def _coerce_model_value(self, annotation: Any, value: Any) -> Any:
        if value is None:
            return None

        inner, is_optional = self._unwrap_optional(annotation)
        if isinstance(value, dict) and self._is_model_type(inner):
            if not value and is_optional:
                return None
            return self._build_model_instance(inner, value)
        return value

    def _unwrap_optional(self, annotation: Any) -> tuple[Any, bool]:
        annotation = resolve_type_alias(annotation)
        if not is_union_type(annotation):
            return annotation, False
        union_args = type_args(annotation)
        if NoneType not in union_args or len(union_args) != 2:
            return annotation, False
        inner = next(arg for arg in union_args if arg is not NoneType)
        return inner, True

    def _is_model_type(self, annotation: Any) -> bool:
        if not isinstance(annotation, type):
            return False
        if (
            is_dataclass(annotation)
            or hasattr(annotation, "model_fields")
            or hasattr(annotation, "__fields__")
        ):
            return True
        return self._is_plain_class_model(annotation)

    def _is_plain_class_model(self, annotation: Any) -> bool:
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
        except Exception:
            return False
        init_method = cls_info.init_method
        if init_method is None:
            return False
        params = [
            p
            for p in init_method.params
            if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        return len(params) > 0

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
        except Exception:
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
