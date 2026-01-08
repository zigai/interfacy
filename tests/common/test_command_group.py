import pytest

from interfacy import CommandGroup
from interfacy.core import InterfacyParser
from interfacy.exceptions import ConfigurationError
from tests.conftest import Container, Database, Math, attach, detach, greet, pow


class TestBasicGroupConstruction:
    def test_create_group_with_name(self):
        """Verify group can be created with just a name."""
        group = CommandGroup("docker")
        assert group.name == "docker"
        assert group.description is None
        assert group.aliases == ()

    def test_create_group_with_description(self):
        """Verify group can have a description."""
        group = CommandGroup("docker", description="Docker CLI")
        assert group.description == "Docker CLI"

    def test_create_group_with_aliases(self):
        """Verify group can have aliases."""
        group = CommandGroup("docker", aliases=["d", "dock"])
        assert group.aliases == ("d", "dock")

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
        parent = CommandGroup("docker")
        child = CommandGroup("compose")
        parent.add_group(child)
        assert parent.has_subgroups
        assert "compose" in parent.subgroups

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
        """Verify nested groups work (3 levels: docker → compose → attach)."""
        docker = CommandGroup("docker")
        compose = CommandGroup("compose")
        docker.add_group(compose)
        compose.add_command(attach)

        parser.add_command(docker)
        assert parser.run(args=["docker", "compose", "attach", "web"]) == "Attached to web"

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
        docker = CommandGroup("docker")
        docker.add_command(Container)

        parser.add_command(docker)
        result = parser.run(args=["docker", "container", "run", "nginx"])
        assert result == "Running nginx with format table"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_init_args_become_group_flags(self, parser: InterfacyParser):
        """Verify class __init__ args become flags at group level."""
        docker = CommandGroup("docker")
        docker.add_command(Container)

        parser.add_command(docker)
        result = parser.run(args=["docker", "container", "--format", "json", "run", "nginx"])
        assert result == "Running nginx with format json"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_class_multiple_methods(self, parser: InterfacyParser):
        """Verify multiple class methods are accessible."""
        docker = CommandGroup("docker")
        docker.add_command(Container)

        parser.add_command(docker)
        assert (
            parser.run(args=["docker", "container", "run", "nginx"])
            == "Running nginx with format table"
        )
        assert (
            parser.run(args=["docker", "container", "stop", "mycontainer"]) == "Stopped mycontainer"
        )


class TestGroupWithInstances:
    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_instance_methods_become_subcommands(self, parser: InterfacyParser):
        """Verify instance methods become subcommands."""
        db = Database(host="localhost", port=5432)
        docker = CommandGroup("docker")
        docker.add_command(db, name="db")

        parser.add_command(docker)
        result = parser.run(args=["docker", "db", "query", "SELECT 1"])
        assert result == "Query on localhost:5432: SELECT 1"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_instance_no_init_args_in_cli(self, parser: InterfacyParser):
        """Verify instance has no __init__ args exposed in CLI."""
        db = Database(host="localhost", port=5432)
        docker = CommandGroup("docker")
        docker.add_command(db, name="db")

        parser.add_command(docker)
        # ping() has no args, just call it directly
        result = parser.run(args=["docker", "db", "ping"])
        assert result == "Pong from localhost:5432"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_multiple_instances_same_class(self, parser: InterfacyParser):
        """Verify multiple instances of same class can have different names."""
        local_db = Database(host="localhost", port=5432)
        prod_db = Database(host="prod.example.com", port=5432)

        docker = CommandGroup("docker")
        docker.add_command(local_db, name="db-local")
        docker.add_command(prod_db, name="db-prod")

        parser.add_command(docker)
        assert parser.run(args=["docker", "db-local", "ping"]) == "Pong from localhost:5432"
        assert parser.run(args=["docker", "db-prod", "ping"]) == "Pong from prod.example.com:5432"


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
        docker = CommandGroup("docker")
        compose = CommandGroup("compose")
        docker.add_group(compose)
        compose.add_command(attach)
        docker.add_command(Container)

        parser.add_command(docker)
        # Group path
        assert parser.run(args=["docker", "compose", "attach", "web"]) == "Attached to web"
        # Class path
        assert (
            parser.run(args=["docker", "container", "run", "nginx"])
            == "Running nginx with format table"
        )

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_mixed_nesting_groups_functions_instances(self, parser: InterfacyParser):
        """Verify mixing groups, functions, and instances."""
        docker = CommandGroup("docker")
        compose = CommandGroup("compose")
        db = Database(host="localhost", port=5432)

        docker.add_group(compose)
        docker.add_command(db, name="db")
        compose.add_command(attach)

        parser.add_command(docker)
        assert parser.run(args=["docker", "compose", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["docker", "db", "ping"]) == "Pong from localhost:5432"


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
        docker = CommandGroup("docker")
        compose = CommandGroup("compose")
        docker.add_group(compose)
        compose.add_command(attach)

        parser.add_command(docker)
        # Missing subcommand at compose level
        with pytest.raises(SystemExit):
            parser.run(args=["docker", "compose"])

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
        docker = CommandGroup("docker", aliases=["d"])
        docker.add_command(attach)

        parser.add_command(docker)
        assert parser.run(args=["d", "attach", "web"]) == "Attached to web"

    @pytest.mark.parametrize("parser", ["argparse_req_pos"], indirect=True)
    def test_command_in_group_with_aliases(self, parser: InterfacyParser):
        """Verify command within group can have aliases."""
        docker = CommandGroup("docker")
        docker.add_command(attach, aliases=["a", "conn"])

        parser.add_command(docker)
        assert parser.run(args=["docker", "a", "web"]) == "Attached to web"
        assert parser.run(args=["docker", "conn", "web"]) == "Attached to web"


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
        docker = CommandGroup("docker")
        kubectl = CommandGroup("kubectl")

        docker.add_command(attach)
        kubectl.add_command(greet)

        parser.add_command(docker)
        parser.add_command(kubectl)

        assert parser.run(args=["docker", "attach", "web"]) == "Attached to web"
        assert parser.run(args=["kubectl", "greet", "Ada"]) == "Hello, Ada!"

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
