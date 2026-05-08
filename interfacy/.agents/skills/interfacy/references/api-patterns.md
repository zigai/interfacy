# High-Level API Patterns

Use Interfacy as a thin CLI boundary around ordinary Python code.

Before writing new command functions, look for existing typed functions, classes, or service instances that already represent the user's command. Reuse them directly when their signatures and docstrings are suitable. Add a wrapper only when you need to adapt parser-specific inputs, preserve old flag names, hide constructor details, or present a cleaner CLI surface.

## Start With A Function

Use a function when the command is one action.

```python
from pathlib import Path
from typing import Literal

from interfacy import Interfacy

def resize(
    image: Path,
    *,
    width: int,
    format: Literal["png", "jpg"] = "png",
    overwrite: bool = False,
) -> Path:
    """Resize an image.

    Args:
        image: Source image path.
        width: Output width in pixels.
        format: Output image format.
        overwrite: Replace the output file if it already exists.

    Returns:
        Path to the resized image.
    """
    output = image.with_suffix(f".{format}")
    # Do the work here.
    return output

if __name__ == "__main__":
    Interfacy(print_result=True).run(resize)
```

This is the preferred shape until the CLI genuinely needs multiple related commands or shared setup.

## Use A Class For Related Commands

Use a class when commands share configuration or naturally belong to one noun.

```python
from interfacy import Interfacy

class Project:
    def __init__(self, root: str = ".") -> None:
        self.root = root

    def init(self, name: str) -> str:
        """Create a project.

        Args:
            name: Project name.

        Returns:
            Created project identifier.
        """
        return f"{self.root}:{name}"

    def clean(self, *, dry_run: bool = False) -> str:
        """Remove generated files.

        Args:
            dry_run: Show what would be removed without deleting files.

        Returns:
            Cleanup result.
        """
        return "dry" if dry_run else "clean"

if __name__ == "__main__":
    Interfacy(print_result=True).run(Project)
```

Keep CLI classes small. If the application class has many public methods that are not commands, make a CLI adapter class instead of exposing the whole object.

Interfacy treats public instance methods as subcommands. Static methods are also command candidates. Classmethods and inherited methods should be included only when the CLI intentionally exposes them. Private methods, dunder methods, and properties are not good command targets.

## Use An Instance For Dependencies

Use an instance when commands need already-created dependencies: clients, config, services, or test doubles.

```python
service = Project(root="/work")
Interfacy(print_result=True).run(service)
```

This keeps construction outside the parser and makes tests easier.

For callable instances inside a manual group, design and test the instance as a command group surface rather than assuming only `__call__` will be exposed.

## Use CommandGroup For Command Trees

Use `CommandGroup` when you need an actual command namespace: commands come from different functions/classes, need a shared parent command, need nested subcommands, or need aliases/group-level arguments that are not naturally represented by one class.

```python
from interfacy import CommandGroup, Interfacy

def clone(url: str) -> str:
    """Clone a repository.

    Args:
        url: Repository URL.

    Returns:
        Clone result.
    """
    return f"clone:{url}"

ops = CommandGroup("ops", description="Operational commands")
ops.add_command(clone, aliases=["c"])

Interfacy(print_result=True).run(ops)
```

This creates a real command path such as `ops clone`.

## Use help_group For Help Headings

Use `help_group` when the command path is already right and the only goal is clearer `--help` output. `help_group` is help-only; it separates commands visually without adding another command path segment. Write help group names as display-ready headings.

```python
app = Interfacy(print_result=True)
setup_group = "Repository Setup"

app.add_command(clone, help_group=setup_group)
app.add_command(init, help_group=setup_group)
app.add_command(status, help_group="Repository Inspection")
```

In this example, `clone` and `init` appear under the same help heading, but their command paths stay flat.

Reach for `CommandGroup` when the user cares about command hierarchy, aliases, group-level arguments, or nested command paths. Reach for `help_group` when the user only wants help text separated for clarity.

## Organize Large CLIs By Command Area

When a CLI has many commands, keep leaf command implementations in focused modules and compose them in package-level `create_group()` functions. The top-level entrypoint should be a small wiring layer.

Recommended shape:

```text
src/app_cli/
  __init__.py              # top-level Interfacy wiring
  common.py                # shared CLI helpers
  projects/
    __init__.py            # create_group()
    create.py              # project_create()
    archive.py             # project_archive()
    list.py                # project_list()
  reports/
    __init__.py            # create_group()
    generate.py            # report_generate()
    publish.py             # report_publish()
```

Command area modules expose a group:

```python
from interfacy import CommandGroup

from app_cli.projects.archive import project_archive
from app_cli.projects.create import project_create
from app_cli.projects.list import project_list

def create_group() -> CommandGroup:
    """Create the project command group.

    Returns:
        Project command group.
    """
    group = CommandGroup(name="projects", description="Project management commands.")
    group.add_command(project_create, name="create")
    group.add_command(project_list, name="list")
    group.add_command(project_archive, name="archive")
    return group
```

The top-level module wires groups and uses reused `help_group` constants to keep `--help` scannable:

```python
from interfacy import Interfacy

from app_cli.projects import create_group as projects_group
from app_cli.reports import create_group as reports_group
from app_cli.status import status

WORKFLOW_COMMANDS = "Workflow Commands"
REPORTING_COMMANDS = "Reporting Commands"

def cli() -> None:
    """Run the application CLI."""
    parser = Interfacy(description="Application management CLI.")
    parser.add_command(status, help_group=WORKFLOW_COMMANDS)
    parser.add_group(projects_group(), help_group=WORKFLOW_COMMANDS)
    parser.add_group(reports_group(), help_group=REPORTING_COMMANDS)
    parser.run()
```

Use this pattern when the top-level file is becoming a long list of command implementations. Keep command implementation modules importable and testable on their own; keep grouping/wiring separate.

## Decorators Are For App Modules

Decorator registration is useful when a module owns a CLI app and commands live near their implementation.

```python
from interfacy import Interfacy

app = Interfacy(print_result=True)

@app.command(aliases=["hi"])
def greet(name: str) -> str:
    """Greet a person.

    Args:
        name: Person to greet.

    Returns:
        Greeting text.
    """
    return f"Hello, {name}!"

if __name__ == "__main__":
    app.run()
```

Avoid decorators when they make ordinary Python imports perform surprising registration work.

## Signature Design

Design the signature as the CLI contract:

- Required input: no default.
- Optional flag: default value.
- Option-only value: keyword-only parameter after `*`.
- Choices: `Literal[...]` or `Enum`.
- Repeated values: `list[T]` when the command accepts several values.
- File paths: `Path`, with any normalization done explicitly in the function.
- Groups of related settings: a small structured parameter object.
- Domain-specific scalar values: a custom type plus a custom parser.

Prefer clear Python names. Let Interfacy translate them into CLI names rather than hard-coding parser aliases unless compatibility requires aliases.

## Custom Type Parsers

Use a custom type parser when the command parameter is a real domain value that users should enter as one CLI token, and a normal annotation is not enough.

Good fits:

- IDs with a specific prefix or checksum.
- Compact domain strings such as `owner/repo`, `host:port`, or `name:version`.
- Existing value objects that should remain value objects inside the command.

Poor fits:

- Simple cleanup that belongs in the function, such as `Path(...).expanduser()`.
- A set of choices; use `Literal[...]` or an enum.
- Several related fields; use a structured parameter object.
- Parsing that needs network or database access; keep conversion local and predictable.

Prefer the high-level `Interfacy.add_type_parser(...)` API when adding project-specific types:

```python
from dataclasses import dataclass

from interfacy import Interfacy

@dataclass(frozen=True)
class Repository:
    owner: str
    name: str

def parse_repository(raw: str) -> Repository:
    """Parse an owner/name repository reference.

    Args:
        raw: Repository reference from the CLI.

    Returns:
        Parsed repository reference.

    Raises:
        ValueError: If the reference is not in owner/name form.
    """
    owner, separator, name = raw.partition("/")
    if not owner or separator != "/" or not name:
        raise ValueError("Expected OWNER/NAME")
    return Repository(owner=owner, name=name)

def clone(repo: Repository) -> str:
    """Clone a repository.

    Args:
        repo: Repository to clone.

    Returns:
        Clone result.
    """
    return f"{repo.owner}/{repo.name}"

app = Interfacy(print_result=True)
app.add_type_parser(Repository, parse_repository)
app.run(clone)
```

When a plain class has a registered parser, Interfacy treats it as one parsed value instead of expanding it into nested flags. That is useful for true scalar value objects; use dataclasses or Pydantic models when the user should pass separate fields.

If the project needs to replace the entire parser registry instead of adding one type, pass a `StrToTypeParser` with `type_parser=...` or `apply_setup(type_parser=...)`. Use full replacement only when the defaults are not appropriate.

## Help Text

Docstrings are CLI help. Write them for users:

```python
def deploy(environment: str, *, force: bool = False) -> None:
    """Deploy the current build.

    Args:
        environment: Deployment environment.
        force: Replace an existing deployment.

    Use force only when replacing an existing deployment.
    """
```

Do not put implementation details, stack traces, or internal architecture notes in command docstrings.

Do not add default value prose that repeats the signature:

```python
def retry(*, attempts: int = 3) -> None:
    """Retry the operation.

    Args:
        attempts: Number of attempts.
    """
```

Avoid: "Defaults to 3." Interfacy can derive that from the default values.

## Output

Choose one output style per command:

- Return a value and enable `print_result=True`.
- Print/log inside the command when streaming or side effects matter.
- Return `None` when success is represented by side effects.

Do not convert normal return values into exit codes unless the old CLI already did that.

Avoid `raise SystemExit(main())` wrappers around Interfacy commands. Let Interfacy manage parser exits, and use normal exceptions for failures.
