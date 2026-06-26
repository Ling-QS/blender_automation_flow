import re

from ..runtime_core.constants import (
    BRANCH_END_NODE_TYPES,
    BRANCH_START_NODE_TYPES,
    FLOW_SIDE_HOOK_NODE_TYPES,
    REPEAT_END_NODE_TYPES,
    REPEAT_START_NODE_TYPES,
    numeric_socket_family_by_idname,
    string_socket_family_by_idname,
)

_NODE_TREE_RUNTIME_REVISION_FN = None
_SOCKET_LINK_CACHE = {}
_INPUT_SOURCE_CACHE = {}
_OUTPUT_TARGET_CACHE = {}
_LINK_CACHE_BUCKET_LIMIT = 256


def reset_runtime_flow_caches():
    global _NODE_TREE_RUNTIME_REVISION_FN
    _NODE_TREE_RUNTIME_REVISION_FN = None
    _SOCKET_LINK_CACHE.clear()
    _INPUT_SOURCE_CACHE.clear()
    _OUTPUT_TARGET_CACHE.clear()


def _safe_attr(owner, attr_name, default=None):
    if owner is None:
        return default
    try:
        return getattr(owner, attr_name)
    except Exception:
        return default


def _node_bl_idname(node_or_type):
    if isinstance(node_or_type, str):
        return node_or_type
    return str(_safe_attr(node_or_type, "bl_idname", "") or "")


def _node_name(node, fallback=""):
    return str(_safe_attr(node, "name", fallback) or fallback or "")


def _node_tree_name(node_or_tree, fallback=""):
    tree = _safe_attr(node_or_tree, "id_data", None)
    if tree is None:
        tree = node_or_tree
    name_full = _safe_attr(tree, "name_full", "")
    if name_full:
        return str(name_full)
    return str(_safe_attr(tree, "name", fallback) or fallback or "")


def _socket_collection_get(collection, socket_name):
    if collection is None:
        return None
    getter = _safe_attr(collection, "get", None)
    if callable(getter):
        try:
            return getter(socket_name)
        except Exception:
            return None
    try:
        if socket_name not in collection:
            return None
    except Exception:
        return None
    try:
        return collection[socket_name]
    except Exception:
        return None


def _safe_collection_len(collection):
    if collection is None:
        return 0
    try:
        return len(collection)
    except Exception:
        return 0


def _is_run_task_plan_socket(socket):
    return _node_bl_idname(socket) == "AFSocketTaskPlan" and not bool(_safe_attr(socket, "af_is_virtual", False))


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
    return numeric_socket_family_by_idname(_node_bl_idname(socket))


def _string_socket_family(socket):
    return string_socket_family_by_idname(_node_bl_idname(socket))


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


def _node_tree_cache_token(node_tree):
    global _NODE_TREE_RUNTIME_REVISION_FN
    if node_tree is None:
        return None
    try:
        tree_key = int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)
    except Exception:
        return None
    if _NODE_TREE_RUNTIME_REVISION_FN is None:
        try:
            from ..node_system.tree import node_tree_runtime_revision
        except Exception:
            node_tree_runtime_revision = None
        if node_tree_runtime_revision is not None:
            _NODE_TREE_RUNTIME_REVISION_FN = node_tree_runtime_revision
    revision = 0
    if callable(_NODE_TREE_RUNTIME_REVISION_FN):
        try:
            revision = int(_NODE_TREE_RUNTIME_REVISION_FN(node_tree) or 0)
        except Exception:
            revision = 0
    return (tree_key, revision)


def _cache_bucket(cache_store, node_tree):
    cache_token = _node_tree_cache_token(node_tree)
    if cache_token is None:
        return None
    bucket = cache_store.get(cache_token)
    if bucket is None:
        bucket = {}
        cache_store[cache_token] = bucket
        if len(cache_store) > _LINK_CACHE_BUCKET_LIMIT:
            stale_keys = [key for key in cache_store.keys() if key != cache_token]
            for stale_key in stale_keys[:-max(0, _LINK_CACHE_BUCKET_LIMIT // 2)]:
                cache_store.pop(stale_key, None)
    return bucket


def _is_repeat_start_node(node):
    return _node_bl_idname(node) in REPEAT_START_NODE_TYPES


def _is_repeat_end_node(node):
    return _node_bl_idname(node) in REPEAT_END_NODE_TYPES


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
                    "node_name": _node_name(node),
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
                "node_name": _node_name(node),
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
            "node_name": _node_name(node),
            "pair_map": {},
            "pairs": (),
        }

    return {
        "ok": True,
        "pair_map": pair_map,
        "pairs": tuple(ordered_pairs),
    }


def _is_subflow_start_node(node):
    return _node_bl_idname(node) == "AFNodeSubflowStart"


def _is_subflow_join_node(node):
    return _node_bl_idname(node) == "AFNodeSubflowJoin"


def _is_branch_start_node(node):
    return _node_bl_idname(node) in BRANCH_START_NODE_TYPES


def _is_branch_end_node(node):
    return _node_bl_idname(node) in BRANCH_END_NODE_TYPES


def _is_flow_side_hook_node(node_or_type):
    return _node_bl_idname(node_or_type) in FLOW_SIDE_HOOK_NODE_TYPES


def _link_is_valid(link):
    return bool(getattr(link, "is_valid", True))


def _socket_identity(socket):
    if socket is None:
        return None
    try:
        node = _safe_attr(socket, "node", None)
    except Exception:
        node = None
    if node is None:
        return None
    try:
        node_key = int(node.as_pointer())
    except Exception:
        node_key = _node_name(node)
    return (
        node_key,
        bool(_safe_attr(socket, "is_output", False)),
        str(_safe_attr(socket, "identifier", "") or _safe_attr(socket, "name", "") or ""),
    )


def _link_matches_socket(link, socket, socket_identity=None):
    if link is None or socket is None:
        return False
    endpoint_name = "from_socket" if bool(_safe_attr(socket, "is_output", False)) else "to_socket"
    try:
        endpoint_socket = _safe_attr(link, endpoint_name, None)
    except Exception:
        return False
    return _socket_identity(endpoint_socket) == (socket_identity or _socket_identity(socket))


def _valid_socket_links(socket):
    if socket is None:
        return []
    try:
        if not bool(_safe_attr(socket, "is_linked", False)):
            return []
    except Exception:
        return []
    node_tree = _safe_attr(socket, "id_data", None)
    if node_tree is None:
        return []
    socket_identity = _socket_identity(socket)
    if socket_identity is None:
        return []
    cache_bucket = _cache_bucket(_SOCKET_LINK_CACHE, node_tree)
    if cache_bucket is not None:
        cached_links = cache_bucket.get(socket_identity)
        if cached_links is not None:
            return cached_links
    links = []
    # Avoid NodeSocket.links here: Blender implements it by scanning the whole
    # tree and comparing sockets, which is fragile when auto-follow is triggered
    # from redraw/depsgraph-adjacent callbacks.
    for link in _safe_attr(node_tree, "links", []):
        try:
            if not _link_is_valid(link):
                continue
            if not _link_matches_socket(link, socket, socket_identity=socket_identity):
                continue
            links.append(link)
        except Exception:
            continue
    if not bool(_safe_attr(socket, "is_output", False)):
        try:
            links.sort(
                key=lambda link: int(getattr(link, "multi_input_sort_id", 0) or 0),
                reverse=True,
            )
        except Exception:
            pass
    cached_links = tuple(links)
    if cache_bucket is not None:
        cache_bucket[socket_identity] = cached_links
    return cached_links


def _find_single_from_input_socket(input_socket):
    if input_socket is None:
        return None, None
    node_tree = _safe_attr(input_socket, "id_data", None)
    socket_identity = _socket_identity(input_socket)
    cache_bucket = _cache_bucket(_INPUT_SOURCE_CACHE, node_tree) if socket_identity is not None else None
    if cache_bucket is not None:
        cached_source = cache_bucket.get(socket_identity)
        if cached_source is not None:
            return cached_source
    links = _valid_socket_links(input_socket)
    if not links:
        result = (None, None)
        if cache_bucket is not None:
            cache_bucket[socket_identity] = result
        return result
    link = links[0]
    from_node = _safe_attr(link, "from_node", None)
    from_socket = _safe_attr(link, "from_socket", None)
    # Resolve reroute chains so data resolution works when users insert relay points.
    while from_node is not None and _node_bl_idname(from_node) == "NodeReroute":
        inputs = _safe_attr(from_node, "inputs", None)
        if _safe_collection_len(inputs) == 0:
            result = (None, None)
            if cache_bucket is not None:
                cache_bucket[socket_identity] = result
            return result
        try:
            reroute_input = inputs[0]
        except Exception:
            reroute_input = None
        upstream_links = _valid_socket_links(reroute_input)
        if not upstream_links:
            result = (None, None)
            if cache_bucket is not None:
                cache_bucket[socket_identity] = result
            return result
        upstream_link = upstream_links[0]
        from_node = _safe_attr(upstream_link, "from_node", None)
        from_socket = _safe_attr(upstream_link, "from_socket", None)
    result = (from_node, from_socket)
    if cache_bucket is not None:
        cache_bucket[socket_identity] = result
    return result


def _find_single_to_output_socket(output_socket):
    targets = _resolved_output_targets(output_socket)
    if not targets:
        return None, None
    return targets[0]


def _resolved_output_targets(output_socket, _visited_reroutes=None):
    cache_bucket = None
    socket_identity = None
    if not _visited_reroutes and output_socket is not None:
        node_tree = _safe_attr(output_socket, "id_data", None)
        socket_identity = _socket_identity(output_socket)
        if socket_identity is not None:
            cache_bucket = _cache_bucket(_OUTPUT_TARGET_CACHE, node_tree)
            if cache_bucket is not None:
                cached_targets = cache_bucket.get(socket_identity)
                if cached_targets is not None:
                    return cached_targets
    links = _valid_socket_links(output_socket) if output_socket is not None else []
    if not links:
        return []

    visited_reroutes = set(_visited_reroutes or ())
    targets = []
    seen = set()
    for link in links:
        to_node = _safe_attr(link, "to_node", None)
        to_socket = _safe_attr(link, "to_socket", None)
        if to_node is None:
            continue
        if _node_bl_idname(to_node) == "NodeReroute":
            reroute_key = int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node)
            reroute_outputs = _safe_attr(to_node, "outputs", None)
            if reroute_key in visited_reroutes or _safe_collection_len(reroute_outputs) == 0:
                continue
            try:
                reroute_output = reroute_outputs[0]
            except Exception:
                reroute_output = None
            downstream_targets = _resolved_output_targets(
                reroute_output,
                visited_reroutes | {reroute_key},
            )
            for downstream_node, downstream_socket in downstream_targets:
                target_key = (
                    int(downstream_node.as_pointer()) if hasattr(downstream_node, "as_pointer") else id(downstream_node),
                    str(_safe_attr(downstream_socket, "identifier", "") or _safe_attr(downstream_socket, "name", "") or ""),
                )
                if target_key in seen:
                    continue
                seen.add(target_key)
                targets.append((downstream_node, downstream_socket))
            continue

        target_key = (
            int(to_node.as_pointer()) if hasattr(to_node, "as_pointer") else id(to_node),
            str(_safe_attr(to_socket, "identifier", "") or _safe_attr(to_socket, "name", "") or ""),
        )
        if target_key in seen:
            continue
        seen.add(target_key)
        targets.append((to_node, to_socket))
    cached_targets = tuple(targets)
    if cache_bucket is not None and socket_identity is not None:
        cache_bucket[socket_identity] = cached_targets
    return cached_targets


def _output_nodes(node, output_name):
    if node is None:
        return []
    output_socket = _socket_collection_get(_safe_attr(node, "outputs", None), output_name)
    if output_socket is None:
        return []
    return [to_node for to_node, _to_socket in _resolved_output_targets(output_socket)]


def _flow_trigger_output_nodes(node, output_name):
    return [
        output_node
        for output_node in _output_nodes(node, output_name)
        if _is_flow_side_hook_node(output_node)
    ]


def _first_output_node(node, output_name):
    for output_node in _output_nodes(node, output_name):
        if _is_flow_side_hook_node(output_node):
            continue
        return output_node
    return None

