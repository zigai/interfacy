import asyncio
import inspect
import threading
from typing import TYPE_CHECKING, Any, cast

from objinspect import Class, Function, Method, Parameter
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs

from interfacy.exceptions import ConfigurationError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import reverse_translations
from interfacy.pipe import apply_pipe_values
from interfacy.schema.model_argument_mapper import ModelArgumentMapper
from interfacy.schema.schema import Argument, Command

if TYPE_CHECKING:
    from interfacy.core import InterfacyParser

logger = get_logger(__name__)

COMMAND_KEY_BASE = "command"


class SchemaRunner:
    """
    Execute parsed CLI commands against inspected callables.

    Args:
        namespace (dict[str, Any]): Parsed argument namespace.
        builder (InterfacyParser): Parser instance that built the schema.
        args (list[str]): Raw CLI arguments.
    """

    def __init__(
        self,
        namespace: dict[str, Any],
        builder: "InterfacyParser",
        args: list[str],
    ) -> None:
        self.namespace = namespace
        self.args = args
        self.builder = builder
        self.COMMAND_KEY = self.builder.COMMAND_KEY
        self._instance_chain: list[Any] = []
        self.model_argument_mapper = ModelArgumentMapper()

    def run(self) -> object:
        """Execute commands based on the parsed namespace."""
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

    def _run_awaitable(self, awaitable: object) -> object:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cast(Any, awaitable))

        result: object | None = None
        error: BaseException | None = None

        def _runner() -> None:
            nonlocal result, error
            try:
                result = asyncio.run(cast(Any, awaitable))
            except BaseException as exc:  # noqa: BLE001 - propagate user/runtime errors
                error = exc

        thread = threading.Thread(target=_runner)
        thread.start()
        thread.join()

        if error is not None:
            raise error
        return result

    def _resolve_result(self, value: object) -> object:
        if not inspect.isawaitable(value):
            return value
        return self._run_awaitable(value)

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
        if payload is None or payload == "":
            return args

        parameters = self.builder.get_parameters_for(command, subcommand=subcommand)
        return apply_pipe_values(
            payload,
            config=config,
            arguments=args,
            parameters=parameters,
            type_parser=self.builder.type_parser,
        )

    def run_command(self, command: Command, args: dict[str, Any]) -> object:
        """
        Dispatch a command to its underlying callable.

        Args:
            command (Command): Command schema to execute.
            args (dict[str, Any]): Parsed arguments for the command.
        """
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
        raise InvalidCommandError(command.canonical_name)

    def run_function(self, func: Function | Method, args: dict[str, Any]) -> object:
        """
        Invoke a function or method with parsed arguments.

        Args:
            func (Function | Method): Callable to execute.
            args (dict): Parsed argument mapping.
        """
        positional_args, keyword_args = self._build_call_args(func, args)

        logger.info(
            "Calling function '%s' with args: %s, kwargs: %s",
            func.name,
            positional_args,
            keyword_args,
        )
        result = func.call_async(*positional_args, **keyword_args)
        result = self._resolve_result(result)

        logger.info("Result: %s", result)
        return result

    def run_method(self, method: Method, args: dict[str, Any]) -> object:
        """
        Invoke a method, instantiating its class if needed.

        Args:
            method (Method): Method to execute.
            args (dict): Parsed argument mapping.
        """
        cli_args = reverse_translations(args, self.builder.flag_strategy.argument_translator)
        instance = method.class_instance
        if instance:
            method_args, method_kwargs = self._build_call_args(method, cli_args)
            result = method.call_async(*method_args, **method_kwargs)
            return self._resolve_result(result)

        instance = Class(method.cls)
        if instance.init_method:
            args_init, args_method = split_init_args(cli_args, instance, method)
            init_args, init_kwargs = split_args_kwargs(args_init, instance.init_method)
            logger.info("__init__ method args: %s, kwargs: %s", init_args, init_kwargs)
            instance.init(*init_args, **init_kwargs)
        else:
            args_method = cli_args
            if not method.is_static:
                instance.init()

        method_args, method_kwargs = self._build_call_args(method, args_method)
        logger.info(
            "Calling method '%s' with args: %s, kwargs: %s",
            method.name,
            method_args,
            method_kwargs,
        )
        result = instance.call_method_async(method.name, *method_args, **method_kwargs)
        return self._resolve_result(result)

    def run_class(self, command: Command, args: dict[str, Any]) -> object:
        """
        Execute a class subcommand, instantiating as necessary.

        Args:
            command (Command): Command schema for the class.
            args (dict): Parsed argument mapping containing subcommand data.
        """
        cls = command.obj
        if not isinstance(cls, Class):
            raise TypeError(f"Expected {Class}, got {type(cls)}")
        runtime_cls = cls
        if not cls.is_initialized:
            runtime_cls = Class(cls.cls)

        command_name = args[self.COMMAND_KEY]
        command_args = args[command_name]
        del args[self.COMMAND_KEY]
        del args[command_name]
        logger.info("Namespace: %s", command_args)

        resolved_name = self.builder.flag_strategy.command_translator.reverse(command_name)
        try:
            method = runtime_cls.get_method(command_name)
        except KeyError:
            method = runtime_cls.get_method(resolved_name)

        if not runtime_cls.is_initialized and not method.is_static:
            if runtime_cls.init_method:
                args = self._apply_pipe(command, args, subcommand="__init__")
                args = self._reconstruct_expanded_models(args, self._initializer_for(command))
                init_args, init_kwargs = split_args_kwargs(args, runtime_cls.init_method)
                logger.info("__init__ method args: %s, kwargs: %s", init_args, init_kwargs)
                runtime_cls.init(*init_args, **init_kwargs)
            else:
                runtime_cls.init()

        command_args = self._apply_pipe(command, command_args, subcommand=command_name)
        subcommand_spec = self._schema_subcommand_for(command, command_name)
        if subcommand_spec is not None:
            command_args = self._reconstruct_expanded_models(
                command_args, subcommand_spec.parameters
            )
        method_args, method_kwargs = self._build_call_args(method, command_args)
        logger.info(
            "Calling method '%s' with args: %s, kwargs: %s",
            method.name,
            method_args,
            method_kwargs,
        )
        result = runtime_cls.call_method_async(method.name, *method_args, **method_kwargs)
        return self._resolve_result(result)

    def run_multiple(
        self,
        commands: dict[str, Command],  # noqa: ARG002 - uniform runner API
    ) -> object:
        """
        Execute one of multiple registered commands.

        Args:
            commands (dict[str, Command]): Command mapping by canonical name.
        """
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
        parent_instance: object | None = None,
    ) -> object:
        """
        Execute a command with chain instantiation support.

        For groups/classes: instantiate at this level, then recurse to subcommand.
        For leaf commands: execute with the accumulated instance chain.
        """
        current_instance, normalized_args = self._prepare_chain_level(
            command,
            args,
            parent_instance,
        )
        if command.is_leaf:
            return self._execute_leaf(command, normalized_args, current_instance)

        subcommand, subcommand_args = self._resolve_chain_subcommand(
            command,
            normalized_args,
            depth,
        )
        return self._run_with_chain(subcommand, subcommand_args, depth + 1, current_instance)

    def _prepare_chain_level(
        self,
        command: Command,
        args: dict[str, Any],
        parent_instance: object | None,
    ) -> tuple[object | None, dict[str, Any]]:
        current_instance = parent_instance
        normalized_args = args

        initializer = self._initializer_for(command)
        if initializer:
            normalized_args = self._reconstruct_expanded_models(normalized_args, initializer)

        if command.is_instance and command.stored_instance is not None:
            return command.stored_instance, normalized_args

        instantiated = self._instantiate_chain_class(command, normalized_args)
        if instantiated is None:
            return current_instance, normalized_args

        self._attach_parent_instance(instantiated, parent_instance)
        return instantiated, normalized_args

    def _instantiate_chain_class(
        self,
        command: Command,
        args: dict[str, Any],
    ) -> object | None:
        if command.command_type != "class" or command.obj is None:
            return None

        cls = command.obj
        if not isinstance(cls, Class):
            return None

        cls.is_initialized = False
        cls.instance = None
        init_args = self._extract_init_args(args, command.initializer)
        if init_args:
            assert cls.init_method
            init_a, init_kw = split_args_kwargs(init_args, cls.init_method)
            cls.init(*init_a, **init_kw)
        else:
            cls.init()
        return cls.instance

    def _attach_parent_instance(
        self,
        current_instance: object | None,
        parent_instance: object | None,
    ) -> None:
        if current_instance is None or parent_instance is None:
            return
        instance_dict = getattr(current_instance, "__dict__", None)
        if isinstance(instance_dict, dict):
            instance_dict["_parent"] = parent_instance
            return
        try:
            object.__setattr__(current_instance, "_parent", parent_instance)
        except (AttributeError, TypeError):
            return

    def _resolve_chain_subcommand(
        self,
        command: Command,
        args: dict[str, Any],
        depth: int,
    ) -> tuple[Command, dict[str, Any]]:
        dest_key = f"{COMMAND_KEY_BASE}_{depth}" if depth > 0 else COMMAND_KEY_BASE
        if dest_key not in args:
            raise ConfigurationError(
                f"No subcommand specified for '{command.cli_name}'. "
                f"Available: {', '.join(command.subcommands.keys()) if command.subcommands else 'none'}"
            )

        subcommand_name = args[dest_key]
        if command.subcommands is None:
            raise ConfigurationError(f"Command '{command.cli_name}' has no subcommands")

        subcommand = self._match_subcommand(command.subcommands, subcommand_name)
        if subcommand is None:
            raise ConfigurationError(f"Unknown subcommand '{subcommand_name}'")

        subcommand_args = args.get(subcommand.cli_name, args.get(subcommand_name, {}))
        if not isinstance(subcommand_args, dict):
            subcommand_args = {}
        return subcommand, subcommand_args

    def _match_subcommand(
        self,
        subcommands: dict[str, Command],
        subcommand_name: str,
    ) -> Command | None:
        for sub_cmd in subcommands.values():
            if sub_cmd.cli_name == subcommand_name or subcommand_name in sub_cmd.aliases:
                return sub_cmd
        return None

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
        instance: object | None,
    ) -> object:
        """Execute a leaf command (function or method)."""
        obj = command.obj

        if isinstance(obj, Method):
            if instance is not None:
                args = self._apply_pipe(command, args)
                args = self._reconstruct_expanded_models(
                    args, [*self._initializer_for(command), *self._arguments_for(command)]
                )
                method_args, method_kwargs = self._build_call_args(obj, args)
                logger.info(
                    "Calling method '%s' on instance with args: %s, kwargs: %s",
                    obj.name,
                    method_args,
                    method_kwargs,
                )
                result = obj.call_async(instance, *method_args, **method_kwargs)
                return self._resolve_result(result)
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(
                args, [*self._initializer_for(command), *self._arguments_for(command)]
            )
            return self.run_method(obj, args)

        if isinstance(obj, Function):
            args = self._apply_pipe(command, args)
            args = self._reconstruct_expanded_models(args, self._arguments_for(command))
            return self.run_function(obj, args)

        raise InvalidCommandError(command.canonical_name)

    def _build_call_args(
        self,
        callable_obj: Function | Method,
        args: dict[str, Any],
    ) -> tuple[list[Any], dict[str, Any]]:
        """Build positional and keyword arguments from parsed CLI values."""
        positional_args: list[Any] = []
        keyword_args: dict[str, Any] = {}
        handlers = {
            inspect.Parameter.POSITIONAL_ONLY: self._append_positional_param,
            inspect.Parameter.POSITIONAL_OR_KEYWORD: self._append_positional_param,
            inspect.Parameter.VAR_POSITIONAL: self._append_var_positional_param,
            inspect.Parameter.KEYWORD_ONLY: self._append_keyword_only_param,
            inspect.Parameter.VAR_KEYWORD: self._append_var_keyword_param,
        }

        for param in callable_obj.params:
            if self._should_skip_call_param(param, args):
                continue
            handler = handlers.get(param.kind)
            if handler is not None:
                handler(param, args, positional_args, keyword_args)

        return positional_args, keyword_args

    def _should_skip_call_param(self, param: Parameter, args: dict[str, Any]) -> bool:
        return param.name not in args and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )

    def _append_positional_param(
        self,
        param: Parameter,
        args: dict[str, Any],
        positional_args: list[Any],
        _keyword_args: dict[str, Any],
    ) -> None:
        if param.name in args:
            positional_args.append(args[param.name])

    def _append_var_positional_param(
        self,
        param: Parameter,
        args: dict[str, Any],
        positional_args: list[Any],
        _keyword_args: dict[str, Any],
    ) -> None:
        varargs = args.get(param.name)
        if not varargs:
            return
        if isinstance(varargs, (list, tuple)):
            positional_args.extend(varargs)
            return
        positional_args.append(varargs)

    def _append_keyword_only_param(
        self,
        param: Parameter,
        args: dict[str, Any],
        _positional_args: list[Any],
        keyword_args: dict[str, Any],
    ) -> None:
        if param.name in args:
            keyword_args[param.name] = args[param.name]

    def _append_var_keyword_param(
        self,
        param: Parameter,
        args: dict[str, Any],
        _positional_args: list[Any],
        keyword_args: dict[str, Any],
    ) -> None:
        var_kwargs = args.get(param.name)
        if isinstance(var_kwargs, dict):
            keyword_args.update(var_kwargs)

    def _reconstruct_expanded_models(
        self,
        args: dict[str, Any],
        arguments: list[Argument],
    ) -> dict[str, Any]:
        return self.model_argument_mapper.reconstruct_expanded_models(args, arguments)

    def _schema_command_for(self, command: Command) -> Command | None:
        schema = self.builder.get_last_schema()
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


__all__ = [
    "COMMAND_KEY_BASE",
    "SchemaRunner",
]
