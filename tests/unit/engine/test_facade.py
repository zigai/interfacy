import inspect
from typing import get_type_hints

import pytest

import interfacy
from interfacy import UNSET, CommandGroup, DuplicatePluginError, Interfacy, Param, help
from interfacy.exceptions import ConfigurationError
from interfacy.help import HelpContent, HelpContext, presets
from interfacy.plugins import ConfigureContext, InterfacyPlugin


def test_interfacy_defaults_to_argparse_backend() -> None:
    parser = Interfacy(print_result=False)

    assert parser.backend == "argparse"


def test_interfacy_preserves_metadata_and_parser_identity() -> None:
    parser = Interfacy()

    assert isinstance(parser.metadata, dict)
    assert parser.type_parser is not None


def test_public_unset_is_identical_across_exports() -> None:
    from interfacy.engine import UNSET as ENGINE_SENTINEL

    assert UNSET is ENGINE_SENTINEL


def test_interfacy_accepts_explicit_argparse_backend() -> None:
    parser = Interfacy(backend="argparse", print_result=False)

    assert parser.backend == "argparse"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_sys_exit_disabled_preserves_embedded_run_result(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    parser = Interfacy(backend=backend, sys_exit_enabled=False)

    assert parser.run(lambda: 7, args=[]) == 7


def test_none_bool_negative_prefix_disables_generated_inverse_flag() -> None:
    def command(enabled: bool, cached: bool = True) -> tuple[bool, bool]:
        return enabled, cached

    parser = Interfacy(bool_negative_prefix=None)
    parser.add_command(command)
    arguments = parser.build_parser_schema().commands["command"].parameters

    assert all(argument.boolean_behavior is not None for argument in arguments)
    assert all(argument.boolean_behavior.negative_flags == () for argument in arguments)
    assert parser.invoke(args=["--enabled"]) == (True, True)


def test_interfacy_accepts_click_backend() -> None:
    pytest.importorskip("click")

    parser = Interfacy(backend="click", print_result=False)

    assert parser.backend == "click"


@pytest.mark.parametrize(
    ("backend", "native_module"),
    [
        ("argparse", "interfacy.argparse_backend.argument_parser"),
        ("click", "interfacy.click_backend.commands"),
    ],
)
def test_build_parser_returns_native_backend_value(
    backend: str,
    native_module: str,
) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def command() -> None:
        return None

    parser = Interfacy(backend=backend)
    parser.add_command(command)

    assert type(parser.build_parser()).__module__ == native_module


def test_interfacy_init_is_fully_typed_without_variadic_kwargs() -> None:
    parameters = inspect.signature(Interfacy.__init__).parameters.values()

    assert inspect.Parameter.VAR_POSITIONAL not in {param.kind for param in parameters}
    assert inspect.Parameter.VAR_KEYWORD not in {param.kind for param in parameters}


def test_interfacy_is_declared_final() -> None:
    assert getattr(Interfacy, "__final__", False) is True


def test_interfacy_facade_hides_backend_specific_parser_construction_helpers() -> None:
    parser = Interfacy()

    for name in (
        "install_tab_completion",
        "parser_from_class",
        "parser_from_command",
        "parser_from_function",
        "parser_from_multiple_commands",
    ):
        assert not hasattr(parser, name)


def test_public_parameter_settings_type_hints_resolve() -> None:
    assert "parameter_settings" in get_type_hints(Interfacy.add_command)
    assert "parameter_settings" in get_type_hints(CommandGroup.add_command)


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_configured_help_renderer_is_backend_neutral(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def command() -> None:
        """Run the command."""

    parser = Interfacy(
        backend=backend,
        help_renderer=lambda context, content: f"{context.prog}:{len(content.sections)}",
    )
    parser.add_command(command)
    built_parser = parser.build_parser()
    if backend == "click":
        import click

        help_text = built_parser.get_help(click.Context(built_parser))
    else:
        help_text = built_parser.format_help()

    assert help_text.startswith("main:")
    assert help_text.endswith("\n")
    assert not help_text.endswith("\n\n")


def test_interfacy_runs_with_selected_backend() -> None:
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    parser = Interfacy()

    assert parser.invoke(greet, args=["Ada"]) == "Hello, Ada!"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_interfacy_invoke_does_not_render_result(
    backend: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def summarize(project: str) -> str:
        return f"summary:{project}"

    parser = Interfacy(backend=backend, print_result=True)

    assert parser.invoke(summarize, args=["apollo"]) == "summary:apollo"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_interfacy_add_command_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def choose(output_format: str = "text") -> str:
        return output_format

    parser = Interfacy(backend=backend)
    parser.add_command(
        choose,
        parameter_settings={"output_format": Param(long="style", short="s")},
    )

    assert parser.invoke(args=["--style", "json"]) == "json"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_interfacy_instance_method_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    class Tool:
        def render(self, output_format: str = "text") -> str:
            return output_format

    parser = Interfacy(backend=backend)
    parser.add_command(
        Tool(),
        parameter_settings={"output_format": Param(long="style", short="s")},
    )

    assert parser.invoke(args=["render", "--style", "json"]) == "json"


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_command_group_instance_method_accepts_parameter_settings(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    class Tool:
        def render(self, output_format: str = "text") -> str:
            return output_format

    group = CommandGroup("tools")
    group.add_command(
        Tool(),
        name="tool",
        parameter_settings={"output_format": Param(long="style", short="s")},
    )
    parser = Interfacy(backend=backend)
    parser.add_command(group)

    assert parser.invoke(args=["tools", "tool", "render", "--style", "json"]) == "json"


def test_interfacy_rejects_unknown_backend() -> None:
    with pytest.raises(ConfigurationError, match="backend must be one of: argparse, click"):
        Interfacy(backend="unknown")


@pytest.mark.parametrize(
    "backend_name",
    ["ArgparseBackend", "ArgparseSession", "ClickBackend", "ClickSession"],
)
def test_backend_classes_are_not_top_level_exports(backend_name: str) -> None:
    assert "Interfacy" in interfacy.__all__
    assert "Param" in interfacy.__all__
    assert "params" in interfacy.__all__
    assert backend_name not in interfacy.__all__

    with pytest.raises(AttributeError):
        getattr(interfacy, backend_name)


def test_help_does_not_export_simple_layout_alias() -> None:
    assert "SimpleLayout" not in help.__all__
    assert "SimpleLayout" not in presets.__all__
    assert not hasattr(help, "SimpleLayout")
    assert not hasattr(presets, "SimpleLayout")


def test_apply_setup_duplicate_plugins_is_atomic() -> None:
    class ExistingPlugin(InterfacyPlugin):
        name = "existing"

    class CandidatePlugin(InterfacyPlugin):
        name = "candidate"

        def __init__(self) -> None:
            self.configured = False

        def configure(self, context: ConfigureContext) -> None:
            del context
            self.configured = True

    parser = Interfacy(plugins=[ExistingPlugin()])
    candidate = CandidatePlugin()
    settings_before = parser._engine.settings
    layout_before = parser._engine.help_layout
    generation_before = parser._engine.plugin_manager.generation

    with pytest.raises(DuplicatePluginError):
        parser.apply_setup(
            print_result=True,
            plugins=[candidate, ExistingPlugin()],
        )

    assert parser._engine.settings is settings_before
    assert parser._engine.help_layout is layout_before
    assert parser._engine.plugin_manager.generation == generation_before
    assert candidate.configured is False


@pytest.mark.parametrize(
    "field",
    [
        "print_result",
        "tab_completion",
        "full_error_traceback",
        "allow_args_from_file",
        "abbreviation_max_generated_len",
        "abbreviation_scope",
        "include_inherited_methods",
        "include_protected_methods",
        "include_private_methods",
        "include_staticmethods",
        "include_classmethods",
        "silent_interrupt",
        "expand_model_params",
        "model_expansion_max_depth",
        "bool_negative_prefix",
        "parse_recovery_max_attempts",
        "plugins",
    ],
)
def test_apply_setup_rejects_none_for_non_resettable_fields(field: str) -> None:
    parser = Interfacy()

    with pytest.raises(ConfigurationError, match=f"{field}.*cannot be None"):
        parser.apply_setup(**{field: None})


def test_apply_setup_omission_retains_and_none_resets() -> None:
    def renderer(context: HelpContext, content: HelpContent) -> str:
        del context, content
        return "custom"

    parser = Interfacy(help_renderer=renderer, help_flags=("-h", "--help"))
    type_parser = parser.type_parser

    parser.apply_setup()
    schema = parser.build_parser_schema()
    assert schema.help_flags == ("-h", "--help")
    assert parser.type_parser is type_parser

    parser.apply_setup(help_renderer=None, help_flags=None, type_parser=None)
    schema_reset = parser.build_parser_schema()
    assert schema_reset.help_flags == ("--help",)
    assert parser.type_parser is not type_parser


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_complete_generation_invalidates_on_nested_metadata_change(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    def command() -> None:
        return None

    parser = Interfacy(backend=backend)
    parser.metadata["nested"] = {"value": 1}
    parser.add_command(command)
    first = parser.build_parser()

    parser.metadata["nested"]["value"] = 2
    second = parser.build_parser()

    assert second is not first


@pytest.mark.parametrize("backend", ["argparse", "click"])
def test_inline_base_exception_restores_registered_commands(backend: str) -> None:
    if backend == "click":
        pytest.importorskip("click")

    class StopInvocation(BaseException):
        pass

    def persistent() -> str:
        return "persistent"

    def stop() -> None:
        raise StopInvocation

    parser = Interfacy(backend=backend)
    parser.add_command(persistent)

    with pytest.raises(StopInvocation):
        parser.invoke(stop, args=["stop"])

    assert [command.canonical_name for command in parser.get_commands()] == ["persistent"]
    assert parser.invoke(args=[]) == "persistent"


def test_sort_refresh_uses_current_setup() -> None:
    parser = Interfacy(
        help_option_sort=["alphabetical"],
        help_subcommand_sort=["alphabetical"],
    )

    assert parser.refresh_help_option_sort_rules() == ["alphabetical"]
    assert parser.refresh_help_subcommand_sort_rules() == ["alphabetical"]

    parser.apply_setup(
        help_option_sort=["name_length"],
        help_subcommand_sort=["insert_order"],
    )

    assert parser.refresh_help_option_sort_rules() == ["name_length"]
    assert parser.refresh_help_subcommand_sort_rules() == ["insert_order"]
