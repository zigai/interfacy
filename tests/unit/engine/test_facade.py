import argparse
from typing import get_type_hints

import click
import pytest

import interfacy
from interfacy import CommandGroup, DuplicatePluginError, Interfacy, Param
from interfacy.exceptions import ConfigurationError, UsageError
from interfacy.help import HelpContent, HelpContext
from interfacy.plugins import ConfigureContext, InterfacyPlugin, SchemaTransformContext
from interfacy.schema.model import ParserSchema
from tests.fixtures.help import render_help


def test_interfacy_defaults_to_argparse_backend() -> None:
    parser = Interfacy(print_result=False)

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

    assert parser.invoke(args=["--enabled"]) == (True, True)

    with pytest.raises(UsageError):
        parser.invoke(args=["--enabled", "--no-cached"])


@pytest.mark.parametrize(
    ("backend", "native_type"),
    [("argparse", argparse.ArgumentParser), ("click", click.Command)],
)
def test_build_parser_returns_native_backend_value(backend: str, native_type: type) -> None:
    def command() -> None:
        return None

    parser = Interfacy(backend=backend)
    parser.add_command(command)

    assert isinstance(parser.build_parser(), native_type)


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
    help_text = render_help(parser)

    assert help_text.startswith("main:")
    assert help_text.endswith("\n")
    assert not help_text.endswith("\n\n")


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


def test_unknown_top_level_attribute_raises_attribute_error() -> None:
    assert not hasattr(interfacy, "not_a_public_export")

    with pytest.raises(AttributeError, match="not_a_public_export"):
        interfacy.not_a_public_export  # noqa: B018


def test_interfacy_rejects_unknown_backend() -> None:
    with pytest.raises(ConfigurationError, match="backend must be one of: argparse, click"):
        Interfacy(backend="unknown")


def test_apply_setup_duplicate_plugins_is_atomic(capsys: pytest.CaptureFixture[str]) -> None:
    class ExistingPlugin(InterfacyPlugin):
        name = "existing"

    class CandidatePlugin(InterfacyPlugin):
        name = "candidate"

        def __init__(self) -> None:
            self.configured = False

        def configure(self, context: ConfigureContext) -> None:
            del context
            self.configured = True

    parser = Interfacy(print_result=False, sys_exit_enabled=False, plugins=[ExistingPlugin()])
    candidate = CandidatePlugin()

    with pytest.raises(DuplicatePluginError):
        parser.apply_setup(
            print_result=True,
            plugins=[candidate, ExistingPlugin()],
        )

    assert candidate.configured is False
    assert parser.run(lambda: "quiet", args=[]) == "quiet"
    assert capsys.readouterr().out == ""
    parser.add_plugin(candidate)
    assert candidate.configured is True


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
    class MetadataDescriptionPlugin(InterfacyPlugin):
        def transform_schema(self, context: SchemaTransformContext, schema: ParserSchema):
            schema.raw_description = f"metadata value {context.metadata['nested']['value']}"
            return schema

    def command() -> None:
        return None

    parser = Interfacy(backend=backend, plugins=[MetadataDescriptionPlugin()])
    parser.metadata["nested"] = {"value": 1}
    parser.add_command(command)
    assert "metadata value 1" in render_help(parser)

    parser.metadata["nested"]["value"] = 2

    assert "metadata value 2" in render_help(parser)


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


def test_help_sort_follows_current_setup() -> None:
    def zz() -> None:
        """Short name."""

    def aaaa() -> None:
        """Long name."""

    parser = Interfacy(help_subcommand_sort=["alphabetical"])
    parser.add_command(zz)
    parser.add_command(aaaa)
    alphabetical = render_help(parser)

    parser.apply_setup(help_subcommand_sort=["name_length_asc"])
    by_length = render_help(parser)

    assert alphabetical.index("aaaa") < alphabetical.index("zz")
    assert by_length.index("zz") < by_length.index("aaaa")
