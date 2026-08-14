def inverted_bool_flag_name(name: str, prefix: str = "no-") -> str:
    """
    Return the inverted boolean flag name with a prefix toggle.

    Args:
        name (str): Base flag name.
        prefix (str): Prefix for the inverted form.
    """
    if name.startswith(prefix):
        return name[len(prefix) :]

    return prefix + name
