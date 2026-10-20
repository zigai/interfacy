from pathlib import Path
from textwrap import dedent

import pytest
from objinspect import inspect

from interfacy.common.sentinels import UNSET
from interfacy.exceptions import ConfigurationError
from interfacy.introspection.static_metadata import StaticMetadata, read_static_metadata
from interfacy.introspection.targets import ImportTarget


def _target(tmp_path: Path, source: str, symbol: str) -> ImportTarget:
    path = tmp_path / "commands.py"
    path.write_text(dedent(source), encoding="utf-8")
    return ImportTarget(str(path), symbol)


@pytest.mark.parametrize(
    "source",
    [
        '''
        def run(value: int) -> int:
            """Run the job.

            Args:
                value: Input value.
            """
        ''',
        '''
        def run(value: int) -> int:
            """
            Run the job with a longer summary
            that wraps onto two lines.

            More detail.
            """
        ''',
        '''
        def run() -> None:
            """Args:
                value: Only a parameter section.
            """
        ''',
        """
        def run() -> None:
            pass
        """,
        '''
        class run:
            """Grouped tools."""

            def add(self, a: int) -> int:
                return a
        ''',
        """
        class run:
            def add(self, a: int) -> int:
                return a
        """,
    ],
)
def test_description_matches_imported_target(tmp_path: Path, source: str) -> None:
    target = _target(tmp_path, source, "run")

    metadata = read_static_metadata(target, group_factory=False)

    inspected = inspect(target.load(), init=True, public=True)
    expected = inspected.description if inspected.has_docstring else None
    assert metadata == StaticMetadata(name="run", description=expected)


@pytest.mark.parametrize(
    "source",
    [
        """
        import functools

        @functools.cache
        def run() -> None:
            pass
        """,
        """
        class Base:
            '''Base docs.'''

        class run(Base):
            pass
        """,
    ],
)
def test_undocumented_target_that_may_inherit_a_docstring_has_unknown_description(
    tmp_path: Path, source: str
) -> None:
    metadata = read_static_metadata(_target(tmp_path, source, "run"), group_factory=False)

    assert metadata.name == "run"
    assert metadata.description is UNSET


def test_group_literal_is_read(tmp_path: Path) -> None:
    source = """
    from interfacy import CommandGroup

    ops = CommandGroup("ops", description="Operations", aliases=("o", "op"))
    """

    metadata = read_static_metadata(_target(tmp_path, source, "ops"), group_factory=False)

    assert metadata == StaticMetadata(
        name="ops", description="Operations", aliases=("o", "op"), is_group=True
    )


@pytest.mark.parametrize(
    "assignment",
    [
        'group = interfacy.CommandGroup("tools", "Tool commands")',
        'group: interfacy.CommandGroup = interfacy.CommandGroup("tools", "Tool commands")',
    ],
)
def test_group_factory_reads_the_returned_group(tmp_path: Path, assignment: str) -> None:
    source = f"""
    import interfacy

    def create() -> interfacy.CommandGroup:
        child = interfacy.CommandGroup("child", "Child group")
        {assignment}
        group.add_group(child)
        return group
    """

    metadata = read_static_metadata(_target(tmp_path, source, "create"), group_factory=True)

    assert metadata == StaticMetadata(name="tools", description="Tool commands", is_group=True)


@pytest.mark.parametrize(
    ("source", "symbol"),
    [
        (
            """
            from interfacy import CommandGroup
            NAME = "ops"
            ops = CommandGroup(NAME, description="Operations")
            """,
            "ops",
        ),
        (
            """
            from interfacy import CommandGroup

            def create(flag: bool) -> CommandGroup:
                if flag:
                    return CommandGroup("a")
                return CommandGroup("b")
            """,
            "create",
        ),
    ],
)
def test_group_without_a_literal_name_has_unknown_name(
    tmp_path: Path, source: str, symbol: str
) -> None:
    metadata = read_static_metadata(_target(tmp_path, source, symbol), group_factory=True)

    assert metadata.is_group
    assert metadata.name is UNSET


def test_group_with_non_literal_aliases_is_rejected(tmp_path: Path) -> None:
    source = """
    from interfacy import CommandGroup
    ALIASES = ("o",)
    ops = CommandGroup("ops", aliases=ALIASES)
    """

    with pytest.raises(ConfigurationError, match="aliases"):
        read_static_metadata(_target(tmp_path, source, "ops"), group_factory=False)


@pytest.mark.parametrize(
    "source",
    [
        "from os.path import join as run\n",
        "run = len\n",
    ],
)
def test_other_bindings_have_unknown_metadata(tmp_path: Path, source: str) -> None:
    metadata = read_static_metadata(_target(tmp_path, source, "run"), group_factory=False)

    assert metadata == StaticMetadata()


def test_missing_symbol_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="'missing' is not defined"):
        read_static_metadata(_target(tmp_path, "x = 1\n", "missing"), group_factory=False)


def test_missing_module_is_rejected() -> None:
    target = ImportTarget("tests.fixtures.no_such_module", "run")

    with pytest.raises(ConfigurationError, match="no_such_module"):
        read_static_metadata(target, group_factory=False)


def test_reading_does_not_execute_the_module(tmp_path: Path) -> None:
    source = '''
    raise RuntimeError("module executed")

    def run() -> None:
        """Run."""
    '''

    metadata = read_static_metadata(_target(tmp_path, source, "run"), group_factory=False)

    assert metadata == StaticMetadata(name="run", description="Run.")
