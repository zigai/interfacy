import inspect
from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs

from interfacy.exceptions import ConfigurationError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import reverse_translations
from interfacy.pipe import apply_pipe_values
from interfacy.schema.schema import Argument, Command

if TYPE_CHECKING:
    from interfacy.argparse_backend.argparser import Argparser

logger = get_logger(__name__)

COMMAND_KEY_BASE = "command"


class ArgparseRunner:
    def __init__(
        self,
        namespace: dict,
        builder: "Argparser",
        args: list[str],
        parser,
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
            return self.run_function(obj, args)
        if isinstance(obj, Method):
            args = self._apply_pipe(command, args)
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
                init_args, init_kwargs = split_args_kwargs(args, cls.init_method)
                logger.info(f"__init__ method args: {init_args}, kwargs: {init_kwargs}")
                cls.init(*init_args, **init_kwargs)
            else:
                cls.init()

        command_args = self._apply_pipe(command, command_args, subcommand=command_name)
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
                method_args, method_kwargs = split_args_kwargs(args, obj)
                logger.info(
                    f"Calling method '{obj.name}' on instance with args: {method_args}, kwargs: {method_kwargs}"
                )
                return obj.func(instance, *method_args, **method_kwargs)
            args = self._apply_pipe(command, args)
            return self.run_method(obj, args)

        if isinstance(obj, Function):
            args = self._apply_pipe(command, args)
            return self.run_function(obj, args)

        raise InvalidCommandError(obj)
