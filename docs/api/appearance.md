# Appearance

The appearance package contains the layout, color, and help-formatting objects
used to control how Interfacy renders CLI help.

## Base Types

The base appearance classes are configuration-heavy. For these objects, the
constructor signature is the useful part of the API; the inherited rendering
methods are documented once on `HelpLayout` instead of repeated on every preset.

### `HelpLayout`

Base layout configuration object used by the appearance system. Its constructor
parameters define the available formatting knobs.

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.format_argument
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.format_description
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.format_parameter
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.format_usage_metavar
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_command_description
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_commands_ljust
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_help_for_class
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_help_for_multiple_commands
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_help_for_parameter
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_parser_command_usage_suffix
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_primary_boolean_flag_for_argument
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.get_subcommand_usage_token
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.is_argument_boolean
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.keep_help_default_slot_for_arguments
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.order_class_methods_for_help
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.order_commands_for_help
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.order_option_arguments_for_help
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.prepare_default_field_width_for_arguments
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.prepare_default_field_width_for_params
```

```{eval-rst}
.. automethod:: interfacy.appearance.layout.HelpLayout.should_render_description_before_usage
```

```{eval-rst}
.. list-table::
   :header-rows: 1

   * - Object
     - Purpose
   * - ``InterfacyColors``
     - Base color-theme container for help rendering styles.
   * - ``InterfacyLayout``
     - Interfacy-branded layout preset built on ``HelpLayout``.
```

## Layouts

These classes are layout presets built on top of `HelpLayout`.

```{eval-rst}
.. list-table::
   :header-rows: 1

   * - Object
     - Purpose
   * - ``StandardLayout``
     - Default layout that follows standard ``argparse``-style help output.
   * - ``SimpleLayout``
     - Alias of ``StandardLayout``.
   * - ``ArgparseLayout``
     - Layout tuned to closely mirror ``argparse`` help formatting.
   * - ``Aligned``
     - Compact aligned layout with a dedicated default-value column.
   * - ``AlignedTyped``
     - ``Aligned`` variant that gives more emphasis to type information.
   * - ``Modern``
     - More spacious modern layout with stronger visual separation.
   * - ``ClapLayout``
     - Layout inspired by Rust ``clap`` output.
```

## Color Themes

Color presets expose configuration through their constructor fields and do not
add a separate callable API.

```{eval-rst}
.. list-table::
   :header-rows: 1

   * - Object
     - Purpose
   * - ``NoColor``
     - Monochrome theme with no accent colors.
   * - ``Aurora``
     - Theme inspired by aurora palettes.
   * - ``ClapColors``
     - Theme that mimics ``clap`` default styled output.
```

## Help Sorting

```{eval-rst}
.. autodata:: interfacy.appearance.help_sort.HELP_OPTION_SORT_RULE_VALUES
```

```{eval-rst}
.. autodata:: interfacy.appearance.help_sort.DEFAULT_HELP_OPTION_SORT_RULES
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.normalize_sort_rule_name
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.resolve_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.resolve_help_option_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.default_help_option_sort_rules
```

```{eval-rst}
.. autodata:: interfacy.appearance.help_sort.HELP_SUBCOMMAND_SORT_RULE_VALUES
```

```{eval-rst}
.. autodata:: interfacy.appearance.help_sort.DEFAULT_HELP_SUBCOMMAND_SORT_RULES
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.resolve_help_subcommand_sort_rules
```

```{eval-rst}
.. autofunction:: interfacy.appearance.help_sort.default_help_subcommand_sort_rules
```

## Type Formatting

`TypeStyleTheme` is the protocol consumed by `TypeHelpFormatter` when styling
type tokens.

```{eval-rst}
.. autoclass:: interfacy.appearance.type_help.TypeHelpFormatter
   :members: format
   :exclude-members: __init__, __new__
   :show-inheritance:
```

```{eval-rst}
.. autofunction:: interfacy.appearance.type_help.format_type_for_help
```

## Rendering

### `SchemaHelpRenderer`

Turns schema objects into final help text using a selected layout.

```{eval-rst}
.. automethod:: interfacy.appearance.renderer.SchemaHelpRenderer.render_parser_help
```

```{eval-rst}
.. automethod:: interfacy.appearance.renderer.SchemaHelpRenderer.render_command_help
```

```{eval-rst}
.. autofunction:: interfacy.appearance.renderer.has_grouped_commands
```

```{eval-rst}
.. autofunction:: interfacy.appearance.renderer.command_has_grouped_subcommands
```
