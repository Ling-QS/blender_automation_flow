import re

from ..runtime_core.constants import (
    BRANCH_END_NODE_TYPES,
    BRANCH_START_NODE_TYPES,
    NUMERIC_SOCKET_FAMILY_BY_IDNAME,
    REPEAT_END_NODE_TYPES,
    REPEAT_START_NODE_TYPES,
)


def _is_run_task_plan_socket(socket):
    return getattr(socket, "bl_idname", "") == "AFSocketTaskPlan" and not bool(getattr(socket, "af_is_virtual", False))


def _task_plan_socket_title(socket, fallback_index):
    title = str(getattr(socket, "af_display_title", "") or "").strip()
    if title:
        return title
    fallback_name = str(getattr(socket, "name", "") or "").strip()
    if fallback_name:
        return fallback_name
    return f"Task Plan {fallback_index}"


def _make_issue(code, message, node_name, level="ERROR"):
    return {
        "code": code,
        "message": message,
        "node_name": node_name,
        "level": level,
    }


def _numeric_socket_family(socket):
    return NUMERIC_SOCKET_FAMILY_BY_IDNAME.get(str(getattr(socket, "bl_idname", "") or ""), "")


def _socket_specific_output_key(socket):
    family = _numeric_socket_family(socket)
    if not family:
        return ""
    raw_identifier = str(getattr(socket, "identifier", "") or getattr(socket, "name", "") or "").strip()
    if not raw_identifier:
        return ""
    normalized_identifier = re.sub(r"[^0-9A-Za-z_]+", "_", raw_identifier).strip("_").lower()
    if not normalized_identifier:
        return ""
    family_key = {
        "NodeSocketBool": "bool",
        "NodeSocketInt": "int",
        "NodeSocketFloat": "float",
        "NodeSocketVector": "vector",
    }.get(family, "")
    if not family_key:
        return ""
    return f"{family_key}_socket::{normalized_identifier}"


def _numeric_output_key_family(key):
    key = str(key or "")
    if key.startswith("bool_socket::") or key == "bool_value":
        return "NodeSocketBool"
    if key.startswith("int_socket::") or key in {"int_value", "frame", "frame_start", "frame_end", "count"}:
        return "NodeSocketInt"
    if key.startswith("float_socket::") or key in {"float_value", "float_x", "float_y", "float_z"}:
        return "NodeSocketFloat"
    if key.startswith("vector_socket::") or key == "vector_value":
        return "NodeSocketVector"
    return ""


def _is_repeat_start_node(node):
    return getattr(node, "bl_idname", "") in REPEAT_START_NODE_TYPES


def _is_repeat_end_node(node):
    return getattr(node, "bl_idname", "") in REPEAT_END_NODE_TYPES


def _scan_repeat_pairs(entries, get_entry_node=None):
    entry_node_fn = get_entry_node or (lambda entry: entry["node"])
    pair_map = {}
    ordered_pairs = []
    open_start_index = None

    for index, entry in enumerate(entries):
        node = entry_node_fn(entry)
        if _is_repeat_start_node(node):
            if open_start_index is not None:
                return {
                    "ok": False,
                    "code": "AF_E009",
                    "message": "Nested Repeat blocks are not supported",
                    "node_name": node.name,
                    "pair_map": {},
                    "pairs": (),
                }
            open_start_index = index
            continue
        if not _is_repeat_end_node(node):
            continue
        if open_start_index is None:
            return {
                "ok": False,
                "code": "AF_E009",
                "message": "Repeat End has no matching Repeat Start",
                "node_name": node.name,
                "pair_map": {},
                "pairs": (),
            }

        pair = {
            "start_index": int(open_start_index),
            "end_index": int(index),
        }
        pair_map[open_start_index] = dict(pair)
        pair_map[index] = dict(pair)
        ordered_pairs.append(dict(pair))
        open_start_index = None

    if open_start_index is not None:
        node = entry_node_fn(entries[open_start_index])
        return {
            "ok": False,
            "code": "AF_E009",
            "message": "Repeat Start has no matching Repeat End",
            "node_name": node.name,
            "pair_map": {},
            "pairs": (),
        }

    return {
        "ok": True,
        "pair_map": pair_map,
        "pairs": tuple(ordered_pairs),
    }


def _is_subflow_start_node(node):
    return getattr(node, "bl_idname", "") == "AFNodeSubflowStart"


def _is_subflow_join_node(node):
    return getattr(node, "bl_idname", "") == "AFNodeSubflowJoin"


def _is_branch_start_node(node):
    return getattr(node, "bl_idname", "") in BRANCH_START_NODE_TYPES


def _is_branch_end_node(node):
    return getattr(node, "bl_idname", "") in BRANCH_END_NODE_TYPES


def _link_is_valid(link):
    return bool(getattr(link, "is_valid", True))


def _socket_identity(socket):
    if socket is None:
        return None
    try:
        node = getattr(socket, "node", None)
    except Exception:
        node = None
    if node is None:
        return None
    try:
        node_key = int(node.as_pointer())
    except Exception:
        node_key = str(getattr(node, "name", "") or "")
    return (
        node_key,
        bool(getattr(socket, "is_output", False)),
        str(getattr(socket, "identifier", "") or getattr(socket, "name", "") or ""),
    )


def _link_matches_socket(link, socket, socket_identity=None):
    if link is None or socket is None:
        return False
    endpoint_name = "from_socket" if bool(getattr(socket, "is_output", False)) else "to_socket"
    try:
        endpoint_socket = getattr(link, endpoint_name, None)
    except Exception:
        return False
    return _socket_identity(endpoint_socket) == (socket_identity or _socket_identity(socket))


def _valid_socket_links(socket):
    if socket is None:
        return []
    try:
        if not bool(getattr(socket, "is_linked", False)):
            return []
    except Exception:
        return []
    node_tree = getattr(socket, "id_data", None)
    if node_tree is None:
        return []
    socket_identity = _socket_identity(socket)
    if socket_identity is None:
        return []
    links = []
    # Avoid NodeSocket.links here: Blender implements it by scanning the whole
    # tree and comparing sockets, which is fragile when auto-follow is triggered
    # from redraw/depsgraph-adjacent callbacks.
    for link in getattr(node_tree, "links", []):
        try:
            if not _link_is_valid(link):
                continue
            if not _link_matches_socket(link, socket, socket_identity=socket_identity):
                continue
            links.append(link)
        except Exception:
            continue
    if not bool(getattr(socket, "is_output", False)):
        try:
            links.sort(
                key=lambda link: int(getattr(link, "multi_input_sort_id", 0) or 0),
                reverse=True,
            )
        except Exception:
            pass
    return links


def _find_single_from_input_socket(input_socket):
    links = _valid_socket_links(input_socket)
    if not links:
        return None, None
    link = links[0]
    from_node = link.from_node
    from_socket = link.from_socket
    # Resolve reroute chains so data resolution works when users insert relay points.
    while from_node is not None and from_node.bl_idname == "NodeReroute":
        if len(from_node.inputs) == 0:
            return None, None
        upstream_links = _valid_socket_links(from_node.inputs[0])
        if not upstream_links:
            return None, None
        upstream_link = upstream_links[0]
        from_node = upstream_link.from_node
        from_socket = upstream_link.from_socket
    return from_node, from_socket


def _find_single_to_output_socket(output_socket):
    targets = _resolved_output_targets(output_socket)
    if not targets:
        return None, None
    return targets[0]


def _resolved_output_targets(output_socket, _visited_reroutes=None):
    links = _valid_socket_links(output_socket) if output_socket is not None else []
    if not links:
        return []

    visited_reroutes = set(_visited_reroutes or ())
    targets = []
    seen = set()
    for link in links:
        to_node = getattr(link, "to_node", None)
        to_socket = getattr(link, "to_socket", None)
        if to_node is None:
            continue
        if getattr(to_node, "bl_idname", "") == "NodeReroute":
            reroute_key = int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node)
            if reroute_key in visited_reroutes or len(getattr(to_node, "outputs", [])) == 0:
                continue
            downstream_targets = _resolved_output_targets(
                to_node.outputs[0],
                visited_reroutes | {reroute_key},
            )
            for downstream_node, downstream_socket in downstream_targets:
                target_key = (
                    int(downstream_node.as_pointer()) if hasattr(downstream_node, "as_pointer") else id(downstream_node),
                    str(getattr(downstream_socket, "identifier", "") or getattr(downstream_socket, "name", "") or ""),
                )
                if target_key in seen:
                    continue
                seen.add(target_key)
                targets.append((downstream_node, downstream_socket))
            continue

        target_key = (
            int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node),
            str(getattr(to_socket, "identifier", "") or getattr(to_socket, "name", "") or ""),
        )
        if target_key in seen:
            continue
        seen.add(target_key)
        targets.append((to_node, to_socket))
    return targets


def _output_nodes(node, output_name):
    if node is None or output_name not in getattr(node, "outputs", {}):
        return []
    return [to_node for to_node, _to_socket in _resolved_output_targets(node.outputs[output_name])]


def _flow_trigger_output_nodes(node, output_name):
    return [
        output_node
        for output_node in _output_nodes(node, output_name)
        if getattr(output_node, "bl_idname", "") == "AFNodeFlowToggle"
    ]


def _first_output_node(node, output_name):
    for output_node in _output_nodes(node, output_name):
        if getattr(output_node, "bl_idname", "") == "AFNodeFlowToggle":
            continue
        return output_node
    return None

