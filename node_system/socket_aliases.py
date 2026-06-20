PROPERTY_PACKAGE_SOCKET_NAME = "Property Package"
PROPERTY_DEFINITION_SOCKET_NAME = "Property Definition"
PROPERTY_ASSIGNMENT_SOCKET_NAME = "Property Assignment"

PROPERTY_ASSIGNMENT_INPUT_PREFIX = f"{PROPERTY_ASSIGNMENT_SOCKET_NAME} "

BASE_PROPERTY_PACKAGE_SOCKET_NAME = f"Base {PROPERTY_PACKAGE_SOCKET_NAME}"
ADD_PROPERTY_PACKAGE_SOCKET_NAME = f"Add {PROPERTY_PACKAGE_SOCKET_NAME}"

BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME = f"Base {PROPERTY_ASSIGNMENT_SOCKET_NAME}"
ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME = f"Add {PROPERTY_ASSIGNMENT_SOCKET_NAME}"

_SOCKET_ALIAS_TABLE = {
    PROPERTY_PACKAGE_SOCKET_NAME: ("Prop Pack",),
    PROPERTY_DEFINITION_SOCKET_NAME: ("Prop Def",),
    PROPERTY_ASSIGNMENT_SOCKET_NAME: ("Prop Assign",),
    BASE_PROPERTY_PACKAGE_SOCKET_NAME: ("Base Prop Pack",),
    ADD_PROPERTY_PACKAGE_SOCKET_NAME: ("Add Prop Pack",),
    BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME: ("Base Prop Assign",),
    ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME: ("Add Prop Assign",),
}

_SOCKET_ALIAS_REVERSE_TABLE = {}
for _canonical_name, _aliases in _SOCKET_ALIAS_TABLE.items():
    alias_names = (_canonical_name, *tuple(_aliases))
    for _alias_name in alias_names:
        _SOCKET_ALIAS_REVERSE_TABLE[str(_alias_name)] = alias_names


def _indexed_alias_variants(raw_name):
    text = str(raw_name or "")
    if not text:
        return ()
    for canonical_name, aliases in _SOCKET_ALIAS_TABLE.items():
        prefix_variants = (canonical_name + " ", *tuple(alias + " " for alias in aliases))
        for prefix in prefix_variants:
            if not text.startswith(prefix):
                continue
            suffix = text[len(prefix) :]
            if not suffix:
                continue
            values = []
            for target_prefix in prefix_variants:
                values.append(f"{target_prefix}{suffix}")
            deduped = []
            seen = set()
            for value in values:
                if value in seen:
                    continue
                seen.add(value)
                deduped.append(value)
            return tuple(deduped)
    return ()


def canonical_socket_display_name(name):
    aliases = socket_name_aliases(name)
    return aliases[0] if aliases else str(name or "")


def socket_name_aliases(name):
    raw_name = str(name or "")
    if not raw_name:
        return ()
    direct = _SOCKET_ALIAS_REVERSE_TABLE.get(raw_name)
    if direct is not None:
        return direct
    indexed = _indexed_alias_variants(raw_name)
    if indexed:
        return indexed
    return (raw_name,)


def find_node_input_socket(node, *names):
    inputs = getattr(node, "inputs", None)
    getter = getattr(inputs, "get", None)
    if getter is None:
        return None
    for name in names:
        for alias_name in socket_name_aliases(name):
            socket = getter(str(alias_name or ""))
            if socket is not None:
                return socket
    return None


__all__ = [
    "ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "ADD_PROPERTY_PACKAGE_SOCKET_NAME",
    "BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "BASE_PROPERTY_PACKAGE_SOCKET_NAME",
    "PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "PROPERTY_ASSIGNMENT_SOCKET_NAME",
    "PROPERTY_DEFINITION_SOCKET_NAME",
    "PROPERTY_PACKAGE_SOCKET_NAME",
    "canonical_socket_display_name",
    "find_node_input_socket",
    "socket_name_aliases",
]
