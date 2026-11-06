# Help

The help package contains the layout, color, and formatting objects used to
control how Interfacy renders CLI help.

## Base Types

The base help classes are configuration-heavy. For these objects, the constructor
signature is the useful part of the API; inherited rendering methods are
documented once on `HelpLayout` instead of repeated on every preset.

### `HelpLayout`

Base layout configuration object used by the help system. Its constructor
parameters define the available formatting knobs.

Grouped command listings can be tuned with ``command_indent`` for the global
command-row indentation and ``command_group_spacing`` for the number of blank
lines inserted between help-group sections.

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.format_argument
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.format_description
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.format_usage_metavar
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_command_description
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_commands_ljust
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_help_for_multiple_commands
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_parser_command_usage_suffix
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_primary_boolean_flag_for_argument
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.get_subcommand_usage_token
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.is_argument_boolean
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.keep_help_default_slot_for_arguments
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.order_commands_for_help
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.order_option_arguments_for_help
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.prepare_default_field_width_for_arguments
```

```text {eval-rst}
.. automethod:: interfacy.help.layouts.base.HelpLayout.should_render_description_before_usage
```

- `InterfacyColors`
- `InterfacyLayout`

## Layouts

- `StandardLayout`
- `ArgparseLayout`
- `Aligned`
- `AlignedTyped`
- `Modern`
- `ClapLayout`

## Color Themes

- `NoColor`
- `Aurora`
- `ClapColors`

## Help Sorting

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.HelpOptionSortRule
```

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.HELP_OPTION_SORT_RULE_VALUES
```

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.DEFAULT_HELP_OPTION_SORT_RULES
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.normalize_sort_rule_name
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.normalize_sort_rules
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.normalize_help_option_sort_rules
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.default_help_option_sort_rules
```

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.HelpSubcommandSortRule
```

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.HELP_SUBCOMMAND_SORT_RULE_VALUES
```

```text {eval-rst}
.. autodata:: interfacy.declarations.sorting.DEFAULT_HELP_SUBCOMMAND_SORT_RULES
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.normalize_help_subcommand_sort_rules
```

```text {eval-rst}
.. autofunction:: interfacy.declarations.sorting.default_help_subcommand_sort_rules
```

## Type Formatting

```text {eval-rst}
.. autoclass:: interfacy.help.formatting.TypeHelpFormatter
   :members: format
   :exclude-members: __init__, __new__
   :show-inheritance:
```

```text {eval-rst}
.. autofunction:: interfacy.help.formatting.format_type_for_help
```

## Rendering

### `SchemaHelpRenderer`

Turns schema objects into final help text using a selected layout.

```text {eval-rst}
.. automethod:: interfacy.help.renderer.SchemaHelpRenderer.render_parser_help
```

```text {eval-rst}
.. automethod:: interfacy.help.renderer.SchemaHelpRenderer.render_command_help
```

```text {eval-rst}
.. autofunction:: interfacy.help.renderer.has_grouped_commands
```

```text {eval-rst}
.. autofunction:: interfacy.help.renderer.command_has_grouped_subcommands
```
