import pytest

from interfacy import CommandGroup
from interfacy.core import InterfacyParser
from interfacy.exceptions import ConfigurationError
from tests.conftest import Container, Database, Math, attach, detach, greet, pow


class TestBasicGroupConstruction:
    def test_create_group_with_name(self):
        """Verify group can be created with just a name."""
        group = CommandGroup("workspace")
        assert group.name == "workspace"
        assert group.description is None
        assert group.aliases == ()

    def test_create_group_with_description(self):
        """Verify group can have a description."""
        group = CommandGroup("workspace", description="Workspace CLI")
        assert group.description == "Workspace CLI"

    def test_create_group_with_aliases(self):
        """Verify group can have aliases."""
        group = CommandGroup("workspace", aliases=["ws", "wsp"])
        assert group.aliases == ("ws", "wsp")

    def test_add_command_with_function(self):
        """Verify function can be added to group."""
        group = CommandGroup("cli")
        group.add_command(attach)
        assert group.has_commands
        assert "attach" in group.commands

    def test_add_command_with_class(self):
        """Verify class can be added to group."""
        group = CommandGroup("cli")
        group.add_command(Container)
        assert group.has_commands
        assert "Container" in group.commands

    def test_add_command_with_instance(self):
        """Verify instance can be added to group."""
        db = Database(host="localhost", port=5432)
        group = CommandGroup("cli")
        group.add_command(db, name="db")
        assert group.has_commands
        assert "db" in group.commands
        assert group.commands["db"].is_instance

    def test_add_group_for_nesting(self):
        """Verify subgroups can be added."""
        parent = CommandGroup("workspace")
        child = CommandGroup("module")
        parent.add_group(child)
        assert parent.has_subgroups
        assert "module" in parent.subgroups

    def test_with_args_returns_self(self):
        """Verify with_args returns self for chaining."""
        group = CommandGroup("cli")
        result = group.with_args(Container)
        assert result is group

    def test_is_empty_property(self):
        """Verify is_empty is True when no commands or subgroups."""
        group = CommandGroup("cli")
        assert group.is_empty
        group.add_command(attach)
        assert not group.is_empty

    def test_fluent_api_chaining(self):
        """Verify fluent API allows chaining."""
        group = (
            CommandGroup("cli")
            .add_command(attach)
            .add_command(detach)
            .add_group(CommandGroup("sub"))
        )
        assert len(group.commands) == 2
        assert len(group.subgroups) == 1

    def test_repr(self):
        """Verify repr shows commands and subgroups."""
        group = CommandGroup("cli")
        group.add_command(attach)
        group.add_group(CommandGroup("sub"))
        repr_str = repr(group)
        assert "cli" in repr_str
        assert "attach" in repr_str
        assert "sub" in repr_str


class TestGroupWithFunctions:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_single_group_with_one_function(self, parser: InterfacyParser):
        """Verify single group with one function can be executed."""
        cli = CommandGroup("cli")
        cli.add_command(greet)

        parser.add_command(cli)
        assert parser.run(args=["cli", "greet", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_single_group_with_multiple_functions(self, parser: InterfacyParser):
        """Verify single group with multiple functions works."""
        cli = CommandGroup("cli")
        cli.add_command(attach)
        cli.add_command(detach)

        parser.add_command(cli)
        assert parser.run(args=["cli", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["cli", "detach", "web"]) == "Detached from web"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_nested_groups_with_function_three_levels(self, parser: InterfacyParser):
        """Verify nested groups work (3 levels: workspace → module → attach)."""
        workspace = CommandGroup("workspace")
        module = CommandGroup("module")
        workspace.add_group(module)
        module.add_command(attach)

        parser.add_command(workspace)
        assert parser.run(args=["workspace", "module", "attach", "web"]) == "Attached to web"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_function_with_custom_name(self, parser: InterfacyParser):
        """Verify function can have custom name in group."""
        cli = CommandGroup("cli")
        cli.add_command(attach, name="connect")

        parser.add_command(cli)
        assert parser.run(args=["cli", "connect", "web"]) == "Attached to web"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_function_with_custom_description(self, parser: InterfacyParser):
        """Verify function can have custom description."""
        cli = CommandGroup("cli")
        cli.add_command(attach, description="Connect to container")

        parser.add_command(cli)
        assert parser.run(args=["cli", "attach", "web"]) == "Attached to web"


class TestGroupWithClasses:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_in_group_methods_become_subcommands(self, parser: InterfacyParser):
        """Verify class methods become subcommands when class is added to group."""
        workspace = CommandGroup("workspace")
        workspace.add_command(Container)

        parser.add_command(workspace)
        result = parser.run(args=["workspace", "container", "run", "nginx"])
        assert result == "Running nginx with format table"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_init_args_become_group_flags(self, parser: InterfacyParser):
        """Verify class __init__ args become flags at group level."""
        workspace = CommandGroup("workspace")
        workspace.add_command(Container)

        parser.add_command(workspace)
        result = parser.run(args=["workspace", "container", "--format", "json", "run", "nginx"])
        assert result == "Running nginx with format json"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_multiple_methods(self, parser: InterfacyParser):
        """Verify multiple class methods are accessible."""
        workspace = CommandGroup("workspace")
        workspace.add_command(Container)

        parser.add_command(workspace)
        assert (
            parser.run(args=["workspace", "container", "run", "nginx"])
            == "Running nginx with format table"
        )
        assert (
            parser.run(args=["workspace", "container", "stop", "mycontainer"])
            == "Stopped mycontainer"
        )


class TestGroupWithInstances:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_instance_methods_become_subcommands(self, parser: InterfacyParser):
        """Verify instance methods become subcommands."""
        db = Database(host="localhost", port=5432)
        workspace = CommandGroup("workspace")
        workspace.add_command(db, name="db")

        parser.add_command(workspace)
        result = parser.run(args=["workspace", "db", "query", "SELECT 1"])
        assert result == "Query on localhost:5432: SELECT 1"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_instance_no_init_args_in_cli(self, parser: InterfacyParser):
        """Verify instance has no __init__ args exposed in CLI."""
        db = Database(host="localhost", port=5432)
        workspace = CommandGroup("workspace")
        workspace.add_command(db, name="db")

        parser.add_command(workspace)
        result = parser.run(args=["workspace", "db", "ping"])
        assert result == "Pong from localhost:5432"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multiple_instances_same_class(self, parser: InterfacyParser):
        """Verify multiple instances of same class can have different names."""
        local_db = Database(host="localhost", port=5432)
        prod_db = Database(host="prod.example.com", port=5432)

        workspace = CommandGroup("workspace")
        workspace.add_command(local_db, name="db-local")
        workspace.add_command(prod_db, name="db-prod")

        parser.add_command(workspace)
        assert parser.run(args=["workspace", "db-local", "ping"]) == "Pong from localhost:5432"
        assert (
            parser.run(args=["workspace", "db-prod", "ping"]) == "Pong from prod.example.com:5432"
        )


class TestDeeplyNestedGroups:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_three_levels_deep(self, parser: InterfacyParser):
        """Verify 3 levels of nesting works."""
        level1 = CommandGroup("level1")
        level2 = CommandGroup("level2")
        level1.add_group(level2)
        level2.add_command(greet)

        parser.add_command(level1)
        assert parser.run(args=["level1", "level2", "greet", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_four_levels_deep(self, parser: InterfacyParser):
        """Verify 4 levels of nesting works."""
        level1 = CommandGroup("level1")
        level2 = CommandGroup("level2")
        level3 = CommandGroup("level3")
        level1.add_group(level2)
        level2.add_group(level3)
        level3.add_command(greet)

        parser.add_command(level1)
        assert parser.run(args=["level1", "level2", "level3", "greet", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_mixed_nesting_groups_and_classes(self, parser: InterfacyParser):
        """Verify mixing groups and classes in nesting works."""
        workspace = CommandGroup("workspace")
        module = CommandGroup("module")
        workspace.add_group(module)
        module.add_command(attach)
        workspace.add_command(Container)

        parser.add_command(workspace)
        assert parser.run(args=["workspace", "module", "attach", "web"]) == "Attached to web"
        assert (
            parser.run(args=["workspace", "container", "run", "nginx"])
            == "Running nginx with format table"
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_mixed_nesting_groups_functions_instances(self, parser: InterfacyParser):
        """Verify mixing groups, functions, and instances."""
        workspace = CommandGroup("workspace")
        module = CommandGroup("module")
        db = Database(host="localhost", port=5432)

        workspace.add_group(module)
        workspace.add_command(db, name="db")
        module.add_command(attach)

        parser.add_command(workspace)
        assert parser.run(args=["workspace", "module", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["workspace", "db", "ping"]) == "Pong from localhost:5432"


class TestGroupErrors:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_empty_group_error(self, parser: InterfacyParser):
        """Verify empty group raises error on run."""
        cli = CommandGroup("cli")
        parser.add_command(cli)
        result = parser.run(args=["cli"])
        assert isinstance(result, (ConfigurationError, SystemExit))

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_missing_subcommand_error(self, parser: InterfacyParser):
        """Verify missing subcommand produces error."""
        workspace = CommandGroup("workspace")
        module = CommandGroup("module")
        workspace.add_group(module)
        module.add_command(attach)

        parser.add_command(workspace)
        with pytest.raises(SystemExit):  # Missing subcommand at module level
            parser.run(args=["workspace", "module"])

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_invalid_subcommand_error(self, parser: InterfacyParser):
        """Verify invalid subcommand produces error."""
        cli = CommandGroup("cli")
        cli.add_command(attach)

        parser.add_command(cli)
        with pytest.raises(SystemExit):
            parser.run(args=["cli", "nonexistent"])


class TestGroupAliases:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_group_with_aliases(self, parser: InterfacyParser):
        """Verify group can be invoked via aliases."""
        workspace = CommandGroup("workspace", aliases=["ws"])
        workspace.add_command(attach)

        parser.add_command(workspace)
        assert parser.run(args=["ws", "attach", "web"]) == "Attached to web"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_command_in_group_with_aliases(self, parser: InterfacyParser):
        """Verify command within group can have aliases."""
        workspace = CommandGroup("workspace")
        workspace.add_command(attach, aliases=["a", "conn"])

        parser.add_command(workspace)
        assert parser.run(args=["workspace", "a", "web"]) == "Attached to web"
        assert parser.run(args=["workspace", "conn", "web"]) == "Attached to web"


class TestGroupMixedWithDirectCommands:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_group_alongside_standalone_function(self, parser: InterfacyParser):
        """Verify group can coexist with standalone function."""
        cli = CommandGroup("cli")
        cli.add_command(attach)
        parser.add_command(cli)
        parser.add_command(greet)

        assert parser.run(args=["cli", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["greet", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_group_alongside_class(self, parser: InterfacyParser):
        """Verify group can coexist with class command."""
        cli = CommandGroup("cli")
        cli.add_command(attach)

        parser.add_command(cli)
        parser.add_command(Math)

        assert parser.run(args=["cli", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["math", "pow", "2", "-e", "3"]) == 8

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multiple_groups_in_parser(self, parser: InterfacyParser):
        """Verify multiple groups can be added to same parser."""
        workspace = CommandGroup("workspace")
        task = CommandGroup("task")
        workspace.add_command(attach)
        task.add_command(greet)
        parser.add_command(workspace)
        parser.add_command(task)

        assert parser.run(args=["workspace", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["task", "greet", "Ada"]) == "Hello, Ada!"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_group_class_function_all_together(self, parser: InterfacyParser):
        """Verify group, class, and function all work together."""
        cli = CommandGroup("cli")
        cli.add_command(attach)

        parser.add_command(cli)
        parser.add_command(Math)
        parser.add_command(pow)

        assert parser.run(args=["cli", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["math", "pow", "2", "-e", "2"]) == 4
        assert parser.run(args=["pow", "2", "-e", "3"]) == 8
