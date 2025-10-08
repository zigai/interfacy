from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs

from interfacy.exceptions import ConfigurationError, InvalidCommandError
from interfacy.logger import get_logger
from interfacy.naming import reverse_translations
from interfacy.pipe import apply_pipe_values
from interfacy.schema.schema import Command

if TYPE_CHECKING:
    from interfacy.argparse_backend.argparser import Argparser

logger = get_logger(__name__)


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

    def run(self):
        commands = self.builder.commands
        if len(commands) == 0:
            raise ConfigurationError("No commands were provided")
        if len(commands) == 1:
            return self.run_command(self.builder.get_commands()[0], self.namespace)
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
        func_args, func_kwargs = split_args_kwargs(args, func)
        logger.info(f"Calling function '{func.name}' with args: {func_args}, kwargs: {func_kwargs}")
        result = func.call(*func_args, **func_kwargs)
        logger.info(f"Result: {result}")
        return result

    def run_method(self, method: Method, args: dict) -> Any:
        cli_args = reverse_translations(args, self.builder.flag_strategy.argument_translator)
        instance = method.class_instance
        if instance:
            method_args, method_kwargs = split_args_kwargs(cli_args, method)
            return method.call(*method_args, **method_kwargs)

        instance = Class(method.cls)
        args_init, args_method = split_init_args(cli_args, instance, method)
        if not instance.init_method:
            raise ValueError(f"No __init__ method found for class '{instance.name}'")

        init_args, init_kwargs = split_args_kwargs(args_init, instance.init_method)
        logger.info(f"__init__ method args: {init_args}, kwargs: {init_kwargs}")
        instance.init(*init_args, **init_kwargs)

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

        if cls.init_method and not cls.is_initialized:
            args = self._apply_pipe(command, args, subcommand="__init__")
            init_args, init_kwargs = split_args_kwargs(args, cls.init_method)
            logger.info(f"__init__ method args: {init_args}, kwargs: {init_kwargs}")
            cls.init(*init_args, **init_kwargs)

        command_args = self._apply_pipe(command, command_args, subcommand=command_name)
        method = cls.get_method(command_name)
        method_args, method_kwargs = split_args_kwargs(command_args, method)
        logger.info(
            f"Calling method '{command_name}' with args: {method_args}, kwargs: {method_kwargs}"
        )
        return cls.call_method(command_name, *method_args, **method_kwargs)

    def run_multiple(self, commands: dict[str, Command]) -> Any:
        command_name = self.namespace[self.COMMAND_KEY]
        command = self.builder.get_command_by_cli_name(command_name)
        args = self.namespace[command.canonical_name]
        return self.run_command(command, args)
