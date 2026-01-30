from __future__ import annotations

from collections.abc import Iterable

from interfacy.exceptions import DuplicateCommandError
from interfacy.naming.name_mapping import NameMapping


class CommandNameRegistry:
    """Tracks canonical command names—the primary CLI labels—and their aliases."""

    def __init__(
        self,
        translator: NameMapping,
    ) -> None:
        self._translator: NameMapping = translator
        self._canonical: set[str] = set()
        self._alias_to_canonical: dict[str, str] = {}

    @property
    def translator(self) -> NameMapping:
        """
        Return the mapping used for CLI name translation.

        Returns:
            NameMapping: Translator that converts identifiers to CLI-safe names.
        """
        return self._translator

    def register(
        self,
        *,
        default_name: str,
        explicit_name: str | None = None,
        aliases: Iterable[str] | None = None,
    ) -> tuple[str, tuple[str, ...]]:
        """
        Store a command name and its aliases.

        Args:
            default_name: Python identifier derived from the callable.
            explicit_name: Optional override to use verbatim instead of translating the default name.
            aliases: Additional names that should resolve back to the same command.

        Returns:
            tuple[str, tuple[str, ...]]: Pair containing the canonical (authoritative) CLI name and the alias tuple.
        """
        if isinstance(aliases, str):
            alias_tuple: tuple[str, ...] = (aliases,)
        else:
            alias_tuple: tuple[str, ...] = tuple(aliases or ())

        canonical = explicit_name or self._translator.translate(default_name)
        self._ensure_unique(canonical, alias_tuple)
        self._canonical.add(canonical)
        for alias in alias_tuple:
            self._alias_to_canonical[alias] = canonical
        return canonical, alias_tuple

    def canonical_for(self, cli_name: str) -> str | None:
        """
        Look up the canonical name for a CLI entry.

        Args:
            cli_name: Name presented on the command line (canonical or alias).

        Returns:
            str | None: Canonical name if the CLI string is recognized, otherwise ``None``.
        """
        if cli_name in self._canonical:
            return cli_name
        return self._alias_to_canonical.get(cli_name)

    def _ensure_unique(self, canonical: str, aliases: tuple[str, ...]) -> None:
        if not canonical:
            raise DuplicateCommandError(canonical)
        if canonical in self._canonical or canonical in self._alias_to_canonical:
            raise DuplicateCommandError(canonical)

        seen_aliases: set[str] = set()
        for alias in aliases:
            if not alias:
                raise DuplicateCommandError(alias)
            if alias == canonical:
                raise DuplicateCommandError(alias)
            if alias in seen_aliases:
                raise DuplicateCommandError(alias)
            if alias in self._canonical or alias in self._alias_to_canonical:
                raise DuplicateCommandError(alias)
            seen_aliases.add(alias)


__all__ = ["CommandNameRegistry"]
