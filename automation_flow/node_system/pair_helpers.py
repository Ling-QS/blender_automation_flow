import uuid

import bpy

from .config import (
    PAIR_KIND_END_INPUT_SOCKET,
    PAIR_KIND_END_TYPE,
    PAIR_KIND_START_OUTPUT_SOCKET,
    PAIR_KIND_START_TYPE,
    PAIR_NODE_FALLBACK_WIDTH,
    PAIR_NODE_HORIZONTAL_OFFSET,
    PAIR_NODE_PLACEMENT_GAP,
    PAIR_NODE_TYPE_MAP,
)
from .tree import AFNodeTree

_PAIR_NODE_SYNC_GUARD = set()
_START_NODE_ACTIVE_SYNC_GUARD = set()


def _iter_start_nodes(node_tree):
    return [node for node in getattr(node_tree, "nodes", []) if getattr(node, "bl_idname", "") == "AFNodeStart"]


def _pair_node_info(node_or_type):
    node_type = str(getattr(node_or_type, "bl_idname", node_or_type) or "")
    return PAIR_NODE_TYPE_MAP.get(node_type)


def _is_pair_managed_node(node):
    return _pair_node_info(node) is not None


def _pair_kind(node_or_type):
    info = _pair_node_info(node_or_type)
    return info[0] if info is not None else ""


def _pair_role(node_or_type):
    info = _pair_node_info(node_or_type)
    return info[1] if info is not None else ""


def _pair_counterpart_type(node_or_type):
    info = _pair_node_info(node_or_type)
    return info[2] if info is not None else ""


def _pair_end_input_socket_name(node_or_type):
    return PAIR_KIND_END_INPUT_SOCKET.get(_pair_kind(node_or_type), "Flow In")


def _pair_start_output_socket_name(node_or_type):
    return PAIR_KIND_START_OUTPUT_SOCKET.get(_pair_kind(node_or_type), "Flow Out")


def _pair_is_start(node_or_type):
    return _pair_role(node_or_type) == "START"


def _pair_is_end(node_or_type):
    return _pair_role(node_or_type) == "END"


def _node_pointer_key(node):
    return int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)


def _node_layout_width(node):
    width = float(getattr(node, "width", 0.0) or 0.0)
    if width > 1.0:
        return width
    return PAIR_NODE_FALLBACK_WIDTH


def _location_xy(location):
    if location is None:
        return (0.0, 0.0)
    try:
        return (float(location.x), float(location.y))
    except Exception:
        pass
    try:
        return (float(location[0]), float(location[1]))
    except Exception:
        return (0.0, 0.0)


def _pair_default_location_delta(source_node, pair_node):
    if source_node is None or pair_node is None:
        return (0.0, 0.0)
    source_width = _node_layout_width(source_node)
    pair_width = _node_layout_width(pair_node)
    direction = 1.0 if _pair_is_start(source_node) else -1.0
    gap = max(PAIR_NODE_PLACEMENT_GAP, 0.0)
    offset = max(PAIR_NODE_HORIZONTAL_OFFSET, source_width + gap, pair_width + gap)
    return (direction * offset, 0.0)


def _pair_duplicate_offset(source_node):
    try:
        values = getattr(source_node, "af_pair_duplicate_offset", None)
    except Exception:
        values = None
    if values is None:
        return None
    try:
        delta_x = float(values[0])
        delta_y = float(values[1])
    except Exception:
        return None
    if abs(delta_x) <= 1e-5 and abs(delta_y) <= 1e-5:
        return None
    return (delta_x, delta_y)


def _set_pair_duplicate_offset(node, delta):
    if node is None:
        return
    try:
        node.af_pair_duplicate_offset = (float(delta[0]), float(delta[1]))
    except Exception:
        pass


def _pair_reference_delta(reference_start, reference_end, source_node):
    if reference_start is None or reference_end is None or source_node is None:
        return None
    start_x, start_y = _location_xy(getattr(reference_start, "location", None))
    end_x, end_y = _location_xy(getattr(reference_end, "location", None))
    if _pair_is_start(source_node):
        return (end_x - start_x, end_y - start_y)
    if _pair_is_end(source_node):
        return (start_x - end_x, start_y - end_y)
    return None


def _candidate_pair_location(source_node, pair_node):
    if source_node is None or pair_node is None:
        return (0.0, 0.0)
    source_x, source_y = _location_xy(getattr(source_node, "location", None))
    delta = _pair_duplicate_offset(source_node)
    if delta is None:
        delta = _pair_default_location_delta(source_node, pair_node)
    return (source_x + float(delta[0]), source_y + float(delta[1]))


def _node_flow_output_target(node, socket_name="Flow Out"):
    output_socket = getattr(node, "outputs", {}).get(socket_name) if hasattr(getattr(node, "outputs", None), "get") else None
    if output_socket is None:
        return None
    valid_links = [link for link in getattr(output_socket, "links", []) if bool(getattr(link, "is_valid", True))]
    if not valid_links:
        return None
    return getattr(valid_links[0], "to_node", None)


def _node_flow_input_source(node, socket_name="Flow In"):
    input_socket = getattr(node, "inputs", {}).get(socket_name) if hasattr(getattr(node, "inputs", None), "get") else None
    if input_socket is None:
        return None
    valid_links = [link for link in getattr(input_socket, "links", []) if bool(getattr(link, "is_valid", True))]
    if not valid_links:
        return None
    return getattr(valid_links[0], "from_node", None)


def _pair_sequence_forward(start_node):
    counterpart_type = _pair_counterpart_type(start_node)
    if not counterpart_type or not _pair_is_start(start_node):
        return None

    sequence = []
    visited = set()
    current = start_node
    while current is not None:
        node_key = _node_pointer_key(current)
        if node_key in visited:
            return None
        visited.add(node_key)
        sequence.append(current)
        if getattr(current, "bl_idname", "") == counterpart_type:
            return tuple(sequence)
        socket_name = _pair_start_output_socket_name(current) if current == start_node else "Flow Out"
        current = _node_flow_output_target(current, socket_name)
    return None


def _pair_sequence_reverse(end_node):
    counterpart_type = _pair_counterpart_type(end_node)
    if not counterpart_type or not _pair_is_end(end_node):
        return None

    reverse_sequence = []
    visited = set()
    current = end_node
    current_input_name = _pair_end_input_socket_name(end_node)
    while current is not None:
        node_key = _node_pointer_key(current)
        if node_key in visited:
            return None
        visited.add(node_key)
        reverse_sequence.append(current)
        if getattr(current, "bl_idname", "") == counterpart_type:
            reverse_sequence.reverse()
            return tuple(reverse_sequence)
        current = _node_flow_input_source(current, current_input_name)
        current_input_name = "Flow In"
    return None


def _pair_sequence(node):
    if _pair_is_start(node):
        return _pair_sequence_forward(node)
    if _pair_is_end(node):
        return _pair_sequence_reverse(node)
    return None


def _pair_counterpart(node):
    sequence = _pair_sequence(node)
    if not sequence or len(sequence) < 2:
        return None
    return sequence[-1] if _pair_is_start(node) else sequence[0]


def _new_pair_id():
    return uuid.uuid4().hex


def _clear_pair_metadata(node):
    if node is None:
        return
    try:
        node.af_pair_id = ""
    except Exception:
        pass
    try:
        node.af_pair_auto_managed = False
    except Exception:
        pass
    try:
        node.af_pair_duplicate_pending = False
    except Exception:
        pass
    _set_pair_duplicate_offset(node, (0.0, 0.0))


def _assign_pair_metadata(start_node, end_node, pair_id=None):
    if start_node is None or end_node is None:
        return
    shared_pair_id = str(pair_id or _new_pair_id())
    start_node.af_pair_id = shared_pair_id
    start_node.af_pair_auto_managed = True
    start_node.af_pair_duplicate_pending = False
    _set_pair_duplicate_offset(start_node, (0.0, 0.0))
    end_node.af_pair_id = shared_pair_id
    end_node.af_pair_auto_managed = True
    end_node.af_pair_duplicate_pending = False
    _set_pair_duplicate_offset(end_node, (0.0, 0.0))


def _remove_node_safe(node_tree, node):
    if node_tree is None or node is None:
        return
    if getattr(node, "id_data", None) != node_tree:
        return
    try:
        node_tree.nodes.remove(node)
    except Exception:
        pass


def _create_missing_pair_node(node_tree, source_node):
    if node_tree is None or source_node is None or not _is_pair_managed_node(source_node):
        return None
    counterpart_type = str(_pair_counterpart_type(source_node) or "").strip()
    if not counterpart_type:
        return None

    tree_key = int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)
    manage_guard = tree_key not in _PAIR_NODE_SYNC_GUARD
    source_was_unpaired = not str(getattr(source_node, "af_pair_id", "") or "").strip()
    shared_pair_id = str(getattr(source_node, "af_pair_id", "") or "").strip() or _new_pair_id()
    created_node = None
    if manage_guard:
        _PAIR_NODE_SYNC_GUARD.add(tree_key)
    try:
        if source_was_unpaired:
            source_node.af_pair_id = shared_pair_id
            source_node.af_pair_auto_managed = True
            source_node.af_pair_duplicate_pending = False
            _set_pair_duplicate_offset(source_node, (0.0, 0.0))

        created_node = node_tree.nodes.new(counterpart_type)
        if created_node is None or not _is_pair_managed_node(created_node):
            _remove_node_safe(node_tree, created_node)
            if source_was_unpaired:
                _clear_pair_metadata(source_node)
            return None

        if _pair_is_start(source_node):
            start_node = source_node
            end_node = created_node
        else:
            end_node = source_node
            start_node = created_node

        try:
            start_node.parent = getattr(source_node, "parent", None)
            end_node.parent = getattr(source_node, "parent", None)
        except Exception:
            pass

        if _pair_is_start(source_node):
            end_node.location = _candidate_pair_location(start_node, end_node)
        else:
            start_node.location = _candidate_pair_location(end_node, start_node)

        _assign_pair_metadata(start_node, end_node, pair_id=shared_pair_id)
        source_output_name = _pair_start_output_socket_name(start_node)
        target_input_name = _pair_end_input_socket_name(end_node)
        try:
            node_tree.links.new(start_node.outputs[source_output_name], end_node.inputs[target_input_name])
        except Exception:
            pass
        return end_node if _pair_is_start(source_node) else start_node
    except Exception:
        _remove_node_safe(node_tree, created_node)
        if source_was_unpaired:
            _clear_pair_metadata(source_node)
        return None
    finally:
        if manage_guard:
            _PAIR_NODE_SYNC_GUARD.discard(tree_key)


def _normalize_duplicate_pair_ids(node_tree):
    pair_groups = {}
    for node in getattr(node_tree, "nodes", []):
        if not _is_pair_managed_node(node):
            continue
        pair_id = str(getattr(node, "af_pair_id", "") or "").strip()
        if not pair_id:
            continue
        pair_groups.setdefault((_pair_kind(node), pair_id), []).append(node)

    for (pair_kind, _pair_id), nodes in pair_groups.items():
        start_type = PAIR_KIND_START_TYPE.get(pair_kind)
        end_type = PAIR_KIND_END_TYPE.get(pair_kind)
        starts = [node for node in nodes if getattr(node, "bl_idname", "") == start_type]
        ends = [node for node in nodes if getattr(node, "bl_idname", "") == end_type]
        if len(starts) == 1 and len(ends) == 1:
            continue
        if not starts or not ends:
            continue

        matched_pairs = []
        used_starts = set()
        used_ends = set()
        for start_node in starts:
            counterpart = _pair_counterpart(start_node)
            if counterpart is None or counterpart not in ends:
                continue
            if counterpart in used_ends or start_node in used_starts:
                continue
            if _pair_counterpart(counterpart) != start_node:
                continue
            matched_pairs.append((start_node, counterpart))
            used_starts.add(start_node)
            used_ends.add(counterpart)

        keep_nodes = set()
        if matched_pairs:
            original_pair_id = str(getattr(matched_pairs[0][0], "af_pair_id", "") or "").strip() or _new_pair_id()
            for index, (start_node, end_node) in enumerate(matched_pairs):
                _assign_pair_metadata(start_node, end_node, pair_id=original_pair_id if index == 0 else None)
                keep_nodes.add(start_node)
                keep_nodes.add(end_node)
        else:
            keep_nodes.add(starts[0])
            keep_nodes.add(ends[0])

        for node in nodes:
            if node in keep_nodes:
                continue
            was_auto_managed = bool(getattr(node, "af_pair_auto_managed", False))
            reference_start = starts[0] if starts else None
            reference_end = ends[0] if ends else None
            if matched_pairs:
                reference_start, reference_end = matched_pairs[0]
            _clear_pair_metadata(node)
            _set_pair_duplicate_offset(node, _pair_reference_delta(reference_start, reference_end, node) or (0.0, 0.0))
            if was_auto_managed:
                try:
                    node.af_pair_duplicate_pending = True
                except Exception:
                    pass


def _remove_orphaned_pair_nodes(node_tree):
    pair_groups = {}
    for node in getattr(node_tree, "nodes", []):
        if not _is_pair_managed_node(node):
            continue
        pair_id = str(getattr(node, "af_pair_id", "") or "").strip()
        if not pair_id:
            continue
        pair_groups.setdefault((_pair_kind(node), pair_id), []).append(node)

    nodes_to_remove = []
    for (pair_kind, _pair_id), nodes in pair_groups.items():
        start_type = PAIR_KIND_START_TYPE.get(pair_kind)
        end_type = PAIR_KIND_END_TYPE.get(pair_kind)
        starts = [node for node in nodes if getattr(node, "bl_idname", "") == start_type]
        ends = [node for node in nodes if getattr(node, "bl_idname", "") == end_type]
        if len(starts) == 1 and len(ends) == 1:
            continue
        nodes_to_remove.extend(nodes)

    removed = False
    for node in nodes_to_remove:
        if getattr(node, "id_data", None) != node_tree:
            continue
        try:
            node_tree.nodes.remove(node)
            removed = True
        except Exception:
            pass
    return removed


def _assign_inferred_pair_ids(node_tree):
    assigned_any = False
    handled = set()
    for node in list(getattr(node_tree, "nodes", [])):
        if not _is_pair_managed_node(node) or str(getattr(node, "af_pair_id", "") or "").strip():
            continue
        node_key = _node_pointer_key(node)
        if node_key in handled:
            continue
        counterpart = _pair_counterpart(node)
        if counterpart is None or not _is_pair_managed_node(counterpart):
            continue
        counterpart_key = _node_pointer_key(counterpart)
        if str(getattr(counterpart, "af_pair_id", "") or "").strip():
            node.af_pair_id = str(getattr(counterpart, "af_pair_id", "") or "").strip()
            node.af_pair_auto_managed = bool(getattr(counterpart, "af_pair_auto_managed", False))
            node.af_pair_duplicate_pending = False
        else:
            if _pair_is_start(node):
                _assign_pair_metadata(node, counterpart)
            else:
                _assign_pair_metadata(counterpart, node)
        handled.add(node_key)
        handled.add(counterpart_key)
        assigned_any = True
    return assigned_any


def _pair_auto_create_allowed(node_tree):
    context = getattr(bpy, "context", None)
    if context is None:
        return False
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return False
    for window in getattr(window_manager, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in getattr(screen, "areas", []):
            if getattr(area, "type", "") != "NODE_EDITOR":
                continue
            for space in getattr(area, "spaces", []):
                if getattr(space, "type", "") != "NODE_EDITOR":
                    continue
                if getattr(space, "tree_type", "") != AFNodeTree.bl_idname:
                    continue
                if getattr(space, "edit_tree", None) == node_tree:
                    return True
    return False


def _has_selected_pending_pair_cohort(node_tree, node):
    if node_tree is None or node is None or not bool(getattr(node, "af_pair_duplicate_pending", False)):
        return False
    node_kind = _pair_kind(node)
    node_role = _pair_role(node)
    if not node_kind or not node_role or not bool(getattr(node, "select", False)):
        return False
    for other in getattr(node_tree, "nodes", []):
        if other == node or not _is_pair_managed_node(other):
            continue
        if not bool(getattr(other, "af_pair_duplicate_pending", False)):
            continue
        if not bool(getattr(other, "select", False)):
            continue
        if _pair_kind(other) != node_kind or _pair_role(other) == node_role:
            continue
        return True
    return False


def _selected_pending_pair_cohort(node_tree, node):
    if node_tree is None or node is None or not bool(getattr(node, "af_pair_duplicate_pending", False)):
        return None
    node_kind = _pair_kind(node)
    node_role = _pair_role(node)
    if not node_kind or not node_role or not bool(getattr(node, "select", False)):
        return None
    matches = []
    for other in getattr(node_tree, "nodes", []):
        if other == node or not _is_pair_managed_node(other):
            continue
        if not bool(getattr(other, "af_pair_duplicate_pending", False)):
            continue
        if not bool(getattr(other, "select", False)):
            continue
        if _pair_kind(other) != node_kind or _pair_role(other) == node_role:
            continue
        matches.append(other)
    if len(matches) != 1:
        return None
    return matches[0]


def _relink_pair_flow(node_tree, start_node, end_node):
    if node_tree is None or start_node is None or end_node is None:
        return
    start_socket = getattr(getattr(start_node, "outputs", None), "get", lambda _name: None)(_pair_start_output_socket_name(start_node))
    end_socket = getattr(getattr(end_node, "inputs", None), "get", lambda _name: None)(_pair_end_input_socket_name(end_node))
    if start_socket is None or end_socket is None:
        return
    existing = False
    for link in list(getattr(start_socket, "links", [])):
        if getattr(link, "to_node", None) == end_node and getattr(link, "to_socket", None) == end_socket:
            existing = True
            continue
        try:
            node_tree.links.remove(link)
        except Exception:
            pass
    for link in list(getattr(end_socket, "links", [])):
        if getattr(link, "from_node", None) == start_node and getattr(link, "from_socket", None) == start_socket:
            existing = True
            continue
        try:
            node_tree.links.remove(link)
        except Exception:
            pass
    if existing:
        return
    try:
        node_tree.links.new(start_socket, end_socket)
    except Exception:
        pass


def _materialize_selected_pending_pair(node_tree, node):
    counterpart = _selected_pending_pair_cohort(node_tree, node)
    if counterpart is None:
        return False
    if _pair_is_start(node):
        start_node = node
        end_node = counterpart
    else:
        start_node = counterpart
        end_node = node
    _assign_pair_metadata(start_node, end_node)
    _relink_pair_flow(node_tree, start_node, end_node)
    return True


def _sync_paired_flow_nodes(node_tree):
    if node_tree is None:
        return
    tree_key = int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)
    if tree_key in _PAIR_NODE_SYNC_GUARD:
        return
    _PAIR_NODE_SYNC_GUARD.add(tree_key)
    try:
        _normalize_duplicate_pair_ids(node_tree)
        _remove_orphaned_pair_nodes(node_tree)
        _assign_inferred_pair_ids(node_tree)
        if not _pair_auto_create_allowed(node_tree):
            return
        active_node = getattr(getattr(node_tree, "nodes", None), "active", None)
        for node in list(getattr(node_tree, "nodes", [])):
            if not _is_pair_managed_node(node):
                continue
            if str(getattr(node, "af_pair_id", "") or "").strip():
                continue
            if active_node is not None and node != active_node:
                continue
            if bool(getattr(node, "af_pair_duplicate_pending", False)):
                if _materialize_selected_pending_pair(node_tree, node):
                    continue
                if _has_selected_pending_pair_cohort(node_tree, node):
                    continue
                node.af_pair_duplicate_pending = False
                continue
            _create_missing_pair_node(node_tree, node)
    finally:
        _PAIR_NODE_SYNC_GUARD.discard(tree_key)


def _sync_active_start_nodes(node):
    node_tree = getattr(node, "id_data", None)
    if node_tree is None:
        return
    node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
    if node_key in _START_NODE_ACTIVE_SYNC_GUARD:
        return
    _START_NODE_ACTIVE_SYNC_GUARD.add(node_key)
    try:
        if bool(getattr(node, "is_active_start", False)):
            for other in _iter_start_nodes(node_tree):
                if other == node or not bool(getattr(other, "is_active_start", False)):
                    continue
                other.is_active_start = False
    finally:
        _START_NODE_ACTIVE_SYNC_GUARD.discard(node_key)


def _start_node_active_updated(self, context):
    del context
    _sync_active_start_nodes(self)


def _start_node_auto_follow_updated(self, context):
    del context
    if not bool(getattr(self, "auto_follow_enabled", False)):
        return
    if bool(getattr(self, "is_active_start", False)):
        self.is_active_start = False


def _initialize_start_node(node):
    node_tree = getattr(node, "id_data", None)
    if node_tree is None:
        return
    has_other_active_start = any(
        other != node and bool(getattr(other, "is_active_start", False))
        for other in _iter_start_nodes(node_tree)
    )
    node.is_active_start = not has_other_active_start


__all__ = [
    "_PAIR_NODE_SYNC_GUARD",
    "_START_NODE_ACTIVE_SYNC_GUARD",
    "_assign_inferred_pair_ids",
    "_assign_pair_metadata",
    "_candidate_pair_location",
    "_clear_pair_metadata",
    "_create_missing_pair_node",
    "_has_selected_pending_pair_cohort",
    "_initialize_start_node",
    "_is_pair_managed_node",
    "_iter_start_nodes",
    "_materialize_selected_pending_pair",
    "_normalize_duplicate_pair_ids",
    "_node_flow_input_source",
    "_node_flow_output_target",
    "_node_layout_width",
    "_node_pointer_key",
    "_pair_auto_create_allowed",
    "_pair_counterpart",
    "_pair_counterpart_type",
    "_pair_default_location_delta",
    "_pair_duplicate_offset",
    "_pair_end_input_socket_name",
    "_pair_is_end",
    "_pair_is_start",
    "_pair_kind",
    "_pair_node_info",
    "_pair_reference_delta",
    "_pair_role",
    "_pair_sequence",
    "_pair_sequence_forward",
    "_pair_sequence_reverse",
    "_pair_start_output_socket_name",
    "_relink_pair_flow",
    "_remove_orphaned_pair_nodes",
    "_selected_pending_pair_cohort",
    "_set_pair_duplicate_offset",
    "_start_node_active_updated",
    "_start_node_auto_follow_updated",
    "_sync_active_start_nodes",
    "_sync_paired_flow_nodes",
]
