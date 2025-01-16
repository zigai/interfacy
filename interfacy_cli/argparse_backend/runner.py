from typing import TYPE_CHECKING, Any

from objinspect import Class, Function, Method
from objinspect._class import split_init_args
from objinspect.method import split_args_kwargs

from interfacy_cli.exceptions import InvalidCommandError, InvalidConfigurationError
from interfacy_cli.util import revese_arg_translations

if TYPE_CHECKING:
    from interfacy_cli.argparse_backend.argparser import Argparser


class ArgparseRunner:
    def __init__(
        self,
        commands: dict[str, Function | Class | Method],
        namespace: dict,
        builder: "Argparser",
        args: list[str],
        parser,
    ) -> None:
        self._parser = parser
        self.commands = commands
        self.namespace = namespace
        self.args = args
        self.builder = builder
        self.COMMAND_KEY = self.builder.COMMAND_KEY

    def run(self):
        if len(self.commands) == 0:
            raise InvalidConfigurationError("No commands were provided")
        if len(self.commands) == 1:
            command = list(self.commands.values())[0]
            return self.run_command(command, self.namespace)
        return self.run_multiple(self.commands)

    def run_command(self, command: Function | Method | Class, args: dict[str, Any]) -> Any:
        handlers = {
            Function: self.run_function,
            Method: self.run_method,
            Class: self.run_class,
        }
        t = type(command)
        if t not in handlers:
            raise InvalidCommandError(command)
        return handlers[t](command, args)

    def run_function(self, func: Function | Method, args: dict) -> Any:
        func_args, func_kwargs = split_args_kwargs(args, func)
        return func.call(*func_args, **func_kwargs)

    def run_method(self, method: Method, args: dict) -> Any:
        cli_args = revese_arg_translations(args, self.builder.flag_strategy.argument_translator)
        instance = method.class_instance
        if instance:
            method_args, method_kwargs = split_args_kwargs(cli_args, method)
            return method.call(*method_args, **method_kwargs)

        instance = Class(method.cls)
        args_init, args_method = split_init_args(cli_args, instance, method)
        if not instance.init_method:
            raise ValueError("No __init__ method found for class")
        init_args, init_kwargs = split_args_kwargs(args_init, instance.init_method)
        instance.init(*init_args, **init_kwargs)
        method_args, method_kwargs = split_args_kwargs(args_method, method)
        return instance.call_method(method.name, *method_args, **method_kwargs)

    def run_class(self, cls: Class, args: dict) -> Any:
        command_name = args[self.COMMAND_KEY]
        command_args = args[command_name]
        del args[self.COMMAND_KEY]
        del args[command_name]

        if cls.init_method and not cls.is_initialized:
            init_args, init_kwargs = split_args_kwargs(args, cls.init_method)
            cls.init(*init_args, **init_kwargs)

        method_args, method_kwargs = split_args_kwargs(command_args, cls.get_method(command_name))
        return cls.call_method(command_name, *method_args, **method_kwargs)

    def run_multiple(self, commands: dict[str, Function | Class | Method]) -> Any:
        command_name = self.namespace[self.COMMAND_KEY]
        command = commands[command_name]
        args = self.namespace[command_name]
        return self.run_command(command, args)
