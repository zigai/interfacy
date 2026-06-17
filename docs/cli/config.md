# Config

The `interfacy` entrypoint can load defaults from a TOML configuration file.

Config is searched in this order:

1. the path in `INTERFACY_CONFIG`, if set
2. `~/.config/interfacy/config.toml`

Print the active search paths with:

```console
$ interfacy --config-paths
```

## Example

```toml
[behavior]
backend = "argparse"
print_result = true
full_error_traceback = false
tab_completion = true
allow_args_from_file = true
expand_model_params = true
model_expansion_max_depth = 3
parse_recovery_max_attempts = 3

[appearance]
layout = "clap"
colors = "clap"

[flags]
strategy = "default"
style = "required_positional"
translation_mode = "kebab"
help_flags = ["--help", "-h"]
bool_negative_prefix = "no-"
negative_bool_name_mode = "flag_only"
negative_bool_name_prefixes = ["no-", "disable-", "without-"]
help_option_sort = ["required_first", "short_first", "alphabetical"]
help_subcommand_sort = ["insert_order"]

[abbreviations]
generator = "default"
max_generated_len = 1
scope = "top_level_options"

[plugins]
enabled = ["my_package.cli_plugins:DefaultsPlugin"]
```

## Named components

`layout`, `colors`, `strategy`, and `generator` can use built-in names.

Examples:

```toml
[appearance]
layout = "modern"
colors = "aurora"

[abbreviations]
generator = "none"
```

They can also use import paths:

```toml
[appearance]
layout = "my_package.theme:DocsLayout"

[plugins]
enabled = ["my_package.plugins:EnvDefaults"]
```

Imported classes are instantiated. Imported instances are used directly.

## Config and code

Configuration sets entrypoint defaults. A module-level setup hook can still customize the parser after config loads and before the target is registered. See {doc}`setup-hooks`.

Configuration applies to the `interfacy` entrypoint, team-wide defaults, and local developer preferences. Standalone scripts can configure `Interfacy` directly in code.
