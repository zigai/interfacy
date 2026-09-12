import asyncio
import inspect
from typing import Any

from objinspect import Class, Function, Method
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs

from interfacy.exceptions import ConfigurationError, InvalidCommandError, UsageError
from interfacy.logger import get_logger
from interfacy.naming import reverse_translations
from interfacy.runtime.context import ExecutionContext
from interfacy.runtime.piping import apply_pipe_values, validate_required_pipe_targets
from interfacy.schema.model_argument_mapper import ExpandedModelValidationError, ModelArgumentMapper
from interfacy.schema.schema import Argument, Command, find_command

logger = get_logger(__name__)

COMMAND_KEY_BASE = "command"
SUBCOMMANDS_KEY = "_subcommands"


class SchemaRunner:
    """
    Execute parsed CLI commands against inspected callables.

    Args:
        namespace: Parsed argument namespace.
        context: Explicit command execution dependencies.
        args: Raw CLI arguments.
    """

    def __init__(
        self,
        namespace: dict[str, Any],
        context: ExecutionContext,
        args: list[str],
    ) -> None:
        self.namespace = namespace
        self.args = args
        self.context = context
        self.COMMAND_KEY = context.command_key
        self.model_argument_mapper = ModelArgumentMapper()
        self._async_mode = False

    def run(self) -> Any:
        """Execute commands based on the parsed namespace."""
        commands = self.context.commands
        if len(commands) == 0:
            raise ConfigurationError("No commands were provided")

        if len(commands) == 1:
            command = self.context.get_commands()[0]
            if not command.is_leaf and not isinstance(command.obj, Class):
                group_args = self.namespace.get(command.canonical_name, {})
                return self._run_with_chain(command, group_args, depth=0)

            return self.run_command(command, self.namespace)

        return self.run_multiple(commands)

    async def run_async(self) -> Any:
        """Execute commands and await an asynchronous command result."""
        self._async_mode = True
        try:
            result = self.run()
            if inspect.isawaitable(result):
                return await result

            return result
        finally:
            self._async_mode = False

    def run_command(self, command: Command, args: dict[str, Any]) -> Any:
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

    def run_function(self, func: Function | Method, args: dict[str, Any]) -> Any:
        """
        Invoke a function or method with parsed arguments.

        Args:
            func (Function | Method): Callable to execute.
            args (dict): Parsed argument mapping.
        """
        cli_args = reverse_translations(args, self.context.argument_names)
        positional_args, keyword_args = self._build_call_args(func, cli_args)

        logger.info(
            "Calling function '%s' with %d positional arg(s) and %d keyword arg(s)",
            func.name,
            len(positional_args),
            len(keyword_args),
        )
        result = func.call(*positional_args, **keyword_args)
        result = self._resolve_result(result)

        logger.info("Function '%s' completed", func.name)

        return result

    def run_method(self, method: Method, args: dict[str, Any]) -> Any:
        """
        Invoke a method, instantiating its class if needed.

        Args:
            method (Method): Method to execute.
            args (dict): Parsed argument mapping.
        """
        cli_args = reverse_translations(args, self.context.argument_names)
        instance = method.class_instance
        if instance is not None:
            method_args, method_kwargs = self._build_call_args(method, cli_args)
            result = method.call(*method_args, **method_kwargs)
            return self._resolve_result(result)

        instance = Class(method.cls)
        if instance.init_method:
            args_init, args_method = split_init_args(cli_args, instance, method)
            init_args, init_kwargs = split_args_kwargs(args_init, instance.init_method)
            logger.info(
                "__init__ received %d positional arg(s) and %d keyword arg(s)",
                len(init_args),
                len(init_kwargs),
            )
            instance.init(*init_args, **init_kwargs)
        else:
            args_method = cli_args

            if not method.is_static:
                instance.init()

        method_args, method_kwargs = self._build_call_args(method, args_method)
        logger.info(
            "Calling method '%s' with %d positional arg(s) and %d keyword arg(s)",
            method.name,
            len(method_args),
            len(method_kwargs),
        )
        result = instance.call_method(method.name, *method_args, **method_kwargs)
        return self._resolve_result(result)

    def run_class(self, command: Command, args: dict[str, Any]) -> Any:
        """
        Execute a class subcommand, instantiating as necessary.

        Args:
            command (Command): Command schema for the class.
            args (dict): Parsed argument mapping containing subcommand data.
        """
        args = dict(args)
        cls = command.obj
        if not isinstance(cls, Class):
            raise TypeError(f"Expected {Class}, got {type(cls)}")

        runtime_cls = cls
        if not cls.is_initialized:
            runtime_cls = Class(cls.cls)

        command_name = args[self.COMMAND_KEY]
        command_args = self._subcommand_bucket(args, command_name)
        del args[self.COMMAND_KEY]
        args.pop(command_name, None)
        logger.info("Subcommand namespace keys: %s", sorted(command_args))

        resolved_name = self.context.command_names.reverse(command_name)
        try:
            method = runtime_cls.get_method(command_name)
        except KeyError:
            method = runtime_cls.get_method(resolved_name)

        if not runtime_cls.is_initialized and not method.is_static:
            if runtime_cls.init_method:
                args = self._apply_pipe(command, args, subcommand="__init__")
                args = self._reconstruct_expanded_models(args, self._initializer_for(command))
                init_args, init_kwargs = split_args_kwargs(args, runtime_cls.init_method)
                logger.info(
                    "__init__ received %d positional arg(s) and %d keyword arg(s)",
                    len(init_args),
                    len(init_kwargs),
                )
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
            "Calling method '%s' with %d positional arg(s) and %d keyword arg(s)",
            method.name,
            len(method_args),
            len(method_kwargs),
        )
        result = runtime_cls.call_method(method.name, *method_args, **method_kwargs)

        return self._resolve_result(result)

    def run_multiple(
        self,
        commands: dict[str, Command],  # noqa: ARG002 - uniform runner API
    ) -> Any:
        """
        Execute one of multiple registered commands.

        Args:
            commands (dict[str, Command]): Command mapping by canonical name.
        """
        command_name = self.namespace[self.COMMAND_KEY]
        command = self.context.get_command_by_cli_name(command_name)
        args = self.namespace.get(command.canonical_name, {})

        if not command.is_leaf and not isinstance(command.obj, Class):
            return self._run_with_chain(command, args, depth=0)

        return self.run_command(command, args)

    def _run_awaitable(self, awaitable: Any) -> Any:
        if self._async_mode:
            return awaitable

        if isinstance(awaitable, asyncio.Future):
            loop = awaitable.get_loop()
            if loop.is_running():
                raise RuntimeError(
                    "invoke() cannot execute an async command inside a running event loop; "
                    "use 'await invoke_async(...)'"
                )

            return loop.run_until_complete(awaitable)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(awaitable)

        if inspect.iscoroutine(awaitable):
            awaitable.close()

        raise RuntimeError(
            "invoke() cannot execute an async command inside a running event loop; "
            "use 'await invoke_async(...)'"
        )

    def _resolve_result(self, value: Any) -> Any:
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
        config = self.context.resolve_pipe_targets(command, subcommand)
        if config is None:
            return args

        payload = self.context.read_piped_input()
        parameters = self.context.parameters_for(command, subcommand)
        cli_supplied_parameters = self.context.cli_supplied_parameters_for(
            command,
            subcommand,
        )
        if payload is None:
            return validate_required_pipe_targets(
                config=config,
                arguments=args,
                parameters=parameters,
                cli_supplied_parameters=cli_supplied_parameters,
            )

        return apply_pipe_values(
            payload,
            config=config,
            arguments=args,
            parameters=parameters,
            type_parser=self.context.type_parser,
            cli_supplied_parameters=cli_supplied_parameters,
        )

    def _run_with_chain(
        self,
        command: Command,
        args: dict[str, Any],
        depth: int,
        parent_instance: Any | None = None,
    ) -> Any:
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
        parent_instance: Any | None,
    ) -> tuple[Any | None, dict[str, Any]]:
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
    ) -> Any | None:
        if command.command_type != "class" or command.obj is None:
            return None

        cls = command.obj
        if not isinstance(cls, Class):
            return None

        cls.is_initialized = False
        cls.instance = None

        if command.initializer:
            args = self._apply_pipe(command, args, subcommand="__init__")
            args = self._reconstruct_expanded_models(args, command.initializer)

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
        current_instance: Any | None,
        parent_instance: Any | None,
    ) -> None:
        if current_instance is None or parent_instance is None:
            return

        try:
            current_instance._parent = parent_instance
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

        subcommand_args = self._subcommand_bucket(
            args,
            subcommand.cli_name,
            fallback_name=subcommand_name,
        )

        return subcommand, subcommand_args

    def _subcommand_bucket(
        self,
        args: dict[str, Any],
        subcommand_name: str,
        *,
        fallback_name: str | None = None,
    ) -> dict[str, Any]:
        nested = args.get(SUBCOMMANDS_KEY)
        if isinstance(nested, dict):
            bucket = nested.get(subcommand_name)
            if isinstance(bucket, dict):
                return bucket

            if fallback_name is not None:
                fallback_bucket = nested.get(fallback_name)
                if isinstance(fallback_bucket, dict):
                    return fallback_bucket

        direct_bucket = args.get(subcommand_name)
        if isinstance(direct_bucket, dict):
            return direct_bucket

        if fallback_name is not None:
            fallback_direct_bucket = args.get(fallback_name)
            if isinstance(fallback_direct_bucket, dict):
                return fallback_direct_bucket

        return {}

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
                method_args, method_kwargs = self._build_call_args(obj, args)
                logger.info(
                    "Calling method '%s' on instance with %d positional arg(s) and %d keyword arg(s)",
                    obj.name,
                    len(method_args),
                    len(method_kwargs),
                )
                result = obj.call(instance, *method_args, **method_kwargs)

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

    @staticmethod
    def _append_call_arg(
        kind: inspect._ParameterKind,
        name: str,
        args: dict[str, Any],
        positional: list[Any],
        keyword: dict[str, Any],
    ) -> None:
        if name not in args:
            return

        val = args[name]
        match kind:
            case inspect.Parameter.POSITIONAL_ONLY | inspect.Parameter.POSITIONAL_OR_KEYWORD:
                positional.append(val)
            case inspect.Parameter.VAR_POSITIONAL:
                if val:
                    positional.extend(val) if isinstance(val, (list, tuple)) else positional.append(
                        val
                    )
            case inspect.Parameter.KEYWORD_ONLY:
                keyword[name] = val
            case inspect.Parameter.VAR_KEYWORD:
                if isinstance(val, dict):
                    keyword.update(val)

    def _build_call_args(
        self,
        callable_obj: Function | Method,
        args: dict[str, Any],
    ) -> tuple[list[Any], dict[str, Any]]:
        """Build positional and keyword arguments from parsed CLI values."""
        positional_args: list[Any] = []
        keyword_args: dict[str, Any] = {}

        for param in callable_obj.params:
            self._append_call_arg(param.kind, param.name, args, positional_args, keyword_args)

        return positional_args, keyword_args

    def _reconstruct_expanded_models(
        self,
        args: dict[str, Any],
        arguments: list[Argument],
    ) -> dict[str, Any]:
        try:
            return self.model_argument_mapper.reconstruct_expanded_models(args, arguments)
        except ExpandedModelValidationError as e:
            raise UsageError(e.message) from e

    def _schema_command_for(self, command: Command) -> Command | None:
        schema = self.context.schema
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

        return find_command(schema_cmd.subcommands, name)


__all__ = [
    "COMMAND_KEY_BASE",
    "SchemaRunner",
]
