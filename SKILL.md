---
name: interfacy
description: Build and review CLIs that use the Interfacy library (user-facing usage, not core maintenance). Use when deciding Argparser vs ClickParser, registering function/class/group commands, configuring help layouts and sort rules, modeling typed arguments and model expansion, wiring stdin piping, and handling CLI entrypoint targets.
---

# Interfacy Operating Guide

Use this guide when building CLIs with Interfacy as a library user. Prefer source and test behavior over assumptions from examples.

## Treat results and exit codes as separate concepts

- Treat command return values, including `int`, strictly as command results, never as process exit codes.
- Let Interfacy control process exit status through its own exit path.
- Use `sys_exit_enabled=False` for embedding/tests where returned `SystemExit` objects are needed instead of process termination.
- Avoid wrappers that map command return values to process exits via `raise SystemExit(main())`.

## Pick backend deliberately

- Use `Argparser` as the default backend.
- Use `ClickParser` only when Click backend behavior is explicitly desired.
- Treat Click as optional and handle missing-install import errors.
- Do not call `ClickParser.parser_from_function`, `ClickParser.parser_from_class`, or `ClickParser.parser_from_multiple_commands`; they are intentionally unsupported.
- Do not assume Click backend supports argparse tab-completion installation semantics.

## Model commands intentionally

- Use typed functions for leaf commands.
- Use classes when initializer options plus method subcommands are desired.
- Use class instances when state is preconfigured and initializer CLI options must remain hidden.
- Use `CommandGroup` for explicitly shaped nested command trees.
- Use `@parser.command(...)` or `add_command(...)` consistently; both are valid.
- Keep canonical names and aliases globally unique.
- Avoid re-registering the same commands by repeatedly passing them to `run(*commands)` on an already configured parser.
- Avoid duplicate command/subgroup names inside `CommandGroup`; later entries overwrite earlier entries.

## Use type shapes that parse predictably

- Add concrete type annotations for all user-facing CLI params.
- Use `list[T]` or `list[T] | None` when list nargs behavior is required.
- Avoid unions like `list[T] | X | None` when expecting list nargs behavior.
- Remember that bool params are handled as flag options.
- Expect short-only bool flags to have no generated negative counterpart.
- For heterogeneous fixed tuples, expect per-element parsing behavior.
- Use dataclass, Pydantic, or plain-class models for expansion when nested flags are desired.
- Use optional model types (`Model | None`) when absence of nested flags should resolve to `None`.
- Use model defaults intentionally; provided nested flags merge onto default model values.

## Configure stdin piping explicitly

- Configure piping with `pipe_targets` or `pipe_to(...)`.
- Use Python parameter names in pipe targets, not rendered CLI flag strings.
- Set `priority` explicitly: `cli` keeps CLI-provided values, `pipe` overrides them.
- Set `allow_partial=True` only when fewer chunks than targets is acceptable.
- Expect required targets with missing values to raise a pipe input error.

## Configure help layout and sorting explicitly

- Choose layout family intentionally: template-style vs argparse-style.
- Set `help_option_sort` and `help_subcommand_sort` when deterministic ordering matters.
- Pass sort rules as `list[str]` tokens, not single strings.
- Treat empty sort lists as unset/default behavior, not hard disable.
- If replacing `parser.help_layout` after parser creation, rewire parser-owned layout dependencies.
- Expect missing required subcommand cases to print full help and exit with code `0`.

## Use CLI entrypoint targets correctly

- Pass entrypoint targets as `module_or_file:symbol`.
- Use functions, classes, class instances, or bound methods as targets.
- Do not pass `Argparser` or `CommandGroup` objects as entrypoint targets.
- Expect passthrough `--` separators to be stripped before forwarding target args.
- Use config defaults intentionally; they apply only when corresponding overrides are `None`.

## Avoid these bad practices

- Avoid import-time CLI execution (`cli()` at module top level).
- Avoid broad `except SystemExit` handlers that hide parser/runtime failures.
- Avoid assuming `return 0` or `return 1` from commands controls process exit status.
- Avoid using stress/demo examples as production templates.
- Avoid mutable default lists in command signatures.
- Avoid depending on alias names appearing in usage-choice braces.
- Avoid relying on undocumented backend parity; verify behavior per backend when needed.

## Treat known quirks as unstable behavior

- Treat “missing required subcommand prints full help and exits `0`” as current behavior, not a stability guarantee.
- Treat `CommandGroup` duplicate-key overwrite behavior as an implementation quirk; do not build workflows that rely on overwrite order.
- Treat Click parser in-place argument list mutation as backend-internal behavior; do not rely on post-parse `args` identity/content.
- Treat stateful internals (for example list-positional flag generation counters) as non-contract behavior.

## Verify with focused tests

- Runtime and exit behavior: `tests/common/test_system_exit_handling.py`, `tests/common/test_interrupt.py`, `tests/common/test_runner.py`, `tests/common/test_runner_varargs.py`.
- Schema and typing behavior: `tests/schema/`, `tests/specs/test_parser_spec_builder.py`, `tests/common/test_naming.py`.
- Help/layout behavior: `tests/argparse/layout/`, `tests/common/test_help_option_sort.py`, `tests/common/test_help_subcommand_sort.py`, `tests/common/test_help_missing_subcommand.py`.
- Click backend behavior: `tests/click/` and shared command/group/decorator tests in `tests/common/`.
- Entrypoint/config behavior: `tests/cli/test_main.py`, `tests/common/test_config.py`.
