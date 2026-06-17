PROPERTY_PACKAGE_SOCKET_NAME = "Prop Pack"
LEGACY_PROPERTY_PACKAGE_SOCKET_NAME = "Package"
OLDER_PROPERTY_PACKAGE_SOCKET_NAME = "Property Package"

PROPERTY_DEFINITION_SOCKET_NAME = "Prop Def"
LEGACY_PROPERTY_DEFINITION_SOCKET_NAME = "Definition"
OLDER_PROPERTY_DEFINITION_SOCKET_NAME = "Property Definition"

PROPERTY_ASSIGNMENT_SOCKET_NAME = "Prop Assign"
LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME = "Assignment"
OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME = "Property Assignment"

PROPERTY_ASSIGNMENT_INPUT_PREFIX = f"{PROPERTY_ASSIGNMENT_SOCKET_NAME} "
LEGACY_PROPERTY_ASSIGNMENT_INPUT_PREFIX = f"{LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME} "
OLDER_PROPERTY_ASSIGNMENT_INPUT_PREFIX = f"{OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME} "


def _unique_names(names):
    resolved = []
    seen = set()
    for name in names:
        text = str(name or "")
        if not text or text in seen:
            continue
        seen.add(text)
        resolved.append(text)
    return tuple(resolved)


_EXACT_SOCKET_NAME_ALIASES = {
    PROPERTY_PACKAGE_SOCKET_NAME: _unique_names(
        (PROPERTY_PACKAGE_SOCKET_NAME, LEGACY_PROPERTY_PACKAGE_SOCKET_NAME, OLDER_PROPERTY_PACKAGE_SOCKET_NAME)
    ),
    LEGACY_PROPERTY_PACKAGE_SOCKET_NAME: _unique_names(
        (PROPERTY_PACKAGE_SOCKET_NAME, LEGACY_PROPERTY_PACKAGE_SOCKET_NAME, OLDER_PROPERTY_PACKAGE_SOCKET_NAME)
    ),
    OLDER_PROPERTY_PACKAGE_SOCKET_NAME: _unique_names(
        (PROPERTY_PACKAGE_SOCKET_NAME, LEGACY_PROPERTY_PACKAGE_SOCKET_NAME, OLDER_PROPERTY_PACKAGE_SOCKET_NAME)
    ),
    PROPERTY_DEFINITION_SOCKET_NAME: _unique_names(
        (PROPERTY_DEFINITION_SOCKET_NAME, LEGACY_PROPERTY_DEFINITION_SOCKET_NAME, OLDER_PROPERTY_DEFINITION_SOCKET_NAME)
    ),
    LEGACY_PROPERTY_DEFINITION_SOCKET_NAME: _unique_names(
        (PROPERTY_DEFINITION_SOCKET_NAME, LEGACY_PROPERTY_DEFINITION_SOCKET_NAME, OLDER_PROPERTY_DEFINITION_SOCKET_NAME)
    ),
    OLDER_PROPERTY_DEFINITION_SOCKET_NAME: _unique_names(
        (PROPERTY_DEFINITION_SOCKET_NAME, LEGACY_PROPERTY_DEFINITION_SOCKET_NAME, OLDER_PROPERTY_DEFINITION_SOCKET_NAME)
    ),
    PROPERTY_ASSIGNMENT_SOCKET_NAME: _unique_names(
        (PROPERTY_ASSIGNMENT_SOCKET_NAME, LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME, OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME)
    ),
    LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME: _unique_names(
        (PROPERTY_ASSIGNMENT_SOCKET_NAME, LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME, OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME)
    ),
    OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME: _unique_names(
        (PROPERTY_ASSIGNMENT_SOCKET_NAME, LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME, OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME)
    ),
}

_PREFIX_SOCKET_NAME_ALIASES = (
    (
        PROPERTY_ASSIGNMENT_INPUT_PREFIX,
        LEGACY_PROPERTY_ASSIGNMENT_INPUT_PREFIX,
        OLDER_PROPERTY_ASSIGNMENT_INPUT_PREFIX,
    ),
)


def canonical_socket_display_name(name):
    raw_name = str(name or "")
    if not raw_name:
        return raw_name
    exact_aliases = _EXACT_SOCKET_NAME_ALIASES.get(raw_name)
    if exact_aliases:
        return exact_aliases[0]
    for primary_prefix, legacy_prefix, older_prefix in _PREFIX_SOCKET_NAME_ALIASES:
        if raw_name.startswith(primary_prefix):
            return f"{primary_prefix}{raw_name[len(primary_prefix):]}"
        if raw_name.startswith(legacy_prefix):
            return f"{primary_prefix}{raw_name[len(legacy_prefix):]}"
        if raw_name.startswith(older_prefix):
            return f"{primary_prefix}{raw_name[len(older_prefix):]}"
    return raw_name


def socket_name_aliases(name):
    raw_name = str(name or "")
    if not raw_name:
        return ()
    exact_aliases = _EXACT_SOCKET_NAME_ALIASES.get(raw_name)
    if exact_aliases:
        return exact_aliases
    for primary_prefix, legacy_prefix, older_prefix in _PREFIX_SOCKET_NAME_ALIASES:
        if raw_name.startswith(primary_prefix):
            suffix = raw_name[len(primary_prefix):]
            return _unique_names((f"{primary_prefix}{suffix}", f"{legacy_prefix}{suffix}", f"{older_prefix}{suffix}"))
        if raw_name.startswith(legacy_prefix):
            suffix = raw_name[len(legacy_prefix):]
            return _unique_names((f"{primary_prefix}{suffix}", f"{legacy_prefix}{suffix}", f"{older_prefix}{suffix}"))
        if raw_name.startswith(older_prefix):
            suffix = raw_name[len(older_prefix):]
            return _unique_names((f"{primary_prefix}{suffix}", f"{legacy_prefix}{suffix}", f"{older_prefix}{suffix}"))
    return (raw_name,)


def find_node_input_socket(node, *names):
    inputs = getattr(node, "inputs", None)
    getter = getattr(inputs, "get", None)
    if getter is None:
        return None
    for name in names:
        for alias_name in socket_name_aliases(name):
            socket = getter(alias_name)
            if socket is not None:
                return socket
    return None


__all__ = [
    "PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "PROPERTY_DEFINITION_SOCKET_NAME",
    "PROPERTY_PACKAGE_SOCKET_NAME",
    "LEGACY_PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "LEGACY_PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "LEGACY_PROPERTY_DEFINITION_SOCKET_NAME",
    "LEGACY_PROPERTY_PACKAGE_SOCKET_NAME",
    "OLDER_PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "OLDER_PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "OLDER_PROPERTY_DEFINITION_SOCKET_NAME",
    "OLDER_PROPERTY_PACKAGE_SOCKET_NAME",
    "canonical_socket_display_name",
    "find_node_input_socket",
    "socket_name_aliases",
]
