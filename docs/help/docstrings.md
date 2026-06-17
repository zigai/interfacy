# Docstrings

Docstrings are the main source of user-facing help. Their quality shows up directly in the generated CLI.

```python
def resize(path: str, width: int, height: int, crop: bool = False) -> None:
    """
    Resize an image.

    Args:
        path: Image file to resize.
        width: Target width in pixels.
        height: Target height in pixels.
        crop: Crop instead of preserving the full image.
    """
```

The first sentence describes the command. `Args:` entries describe parameters.

## CLI-facing docstrings

For functions and methods exposed through Interfacy, write docstrings as command help.

```python
def publish(package: str, dry_run: bool = False) -> None:
    """
    Publish a package to the configured registry.

    Args:
        package: Package name or path.
        dry_run: Show what would be published without uploading.
    """
```

The signature supplies parameter names, types, and defaults. The docstring supplies meaning: what the command does and what each parameter represents.

```python
Args:
    count: Number of retries before giving up.
```

## Classes

For class commands, the class docstring describes the namespace and method docstrings describe subcommands.

```python
class Database:
    """Database maintenance commands."""

    def vacuum(self, analyze: bool = False) -> None:
        """
        Reclaim storage from dead rows.

        Args:
            analyze: Update planner statistics after vacuuming.
        """
```

Initializer parameter help can come from the class or initializer docstring, depending on where the information lives.

## Markdown-ish inline code

Interfacy layouts can style or strip inline-code backticks in docstrings depending on layout settings. The raw docstring text is still the source for CLI help.
