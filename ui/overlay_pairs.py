import math
import time

from ..runtime_flow.helpers import _find_single_from_input_socket, _first_output_node, _is_flow_side_hook_node, _scan_repeat_pairs
from .overlay_drawing import _convex_hull, _inflate_polygon, _node_bounds, _paired_zone_node_bounds


_EXECUTION_OVERLAY_FILL_COLOR = (0.18, 0.30, 0.48, 0.10)
_EXECUTION_OVERLAY_OUTLINE_COLOR = (0.35, 0.62, 0.95, 0.42)
_TASK_OVERLAY_FILL_COLOR = (0.12, 0.36, 0.25, 0.10)
_TASK_OVERLAY_OUTLINE_COLOR = (0.22, 0.76, 0.54, 0.42)
_REPEAT_OVERLAY_FILL_COLOR = (0.44, 0.29, 0.12, 0.18)
_REPEAT_OVERLAY_OUTLINE_COLOR = (0.72, 0.46, 0.18, 0.56)
_SUBFLOW_BRANCH_OVERLAY_FILL_COLOR = (0.20, 0.18, 0.42, 0.14)
_SUBFLOW_BRANCH_OVERLAY_OUTLINE_COLOR = (0.46, 0.40, 0.86, 0.50)
_OVERLAY_PAIR_PAD = 26.0
_OVERLAY_NESTED_GAP = 12.0


def _overlay_node_key(node):
    return int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)


def _collect_forward_flow_nodes(start_node):
    ordered = []
    visited = set()
    current = start_node
    while current is not None:
        node_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if node_key in visited:
            return None
        visited.add(node_key)
        ordered.append(current)
        if getattr(current, "bl_idname", "") == "AFNodeEnd":
            return ordered
        current = _first_output_node(current, "Flow Out")
    return None


def _collect_reverse_flow_nodes(sink_node, flow_input_name, start_node_types, allowed_node_types):
    if flow_input_name not in getattr(sink_node, "inputs", {}):
        return None, None
    reverse_nodes = []
    visited = {int(sink_node.as_pointer()) if hasattr(sink_node, "as_pointer") else id(sink_node)}
    current, _current_socket = _find_single_from_input_socket(sink_node.inputs[flow_input_name])

    while current is not None:
        node_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if node_key in visited:
            return None, None
        visited.add(node_key)

        current_type = getattr(current, "bl_idname", "")
        if current_type in start_node_types:
            reverse_nodes.reverse()
            return current, reverse_nodes

        if getattr(current, "mute", False):
            if "Flow In" not in current.inputs:
                return None, None
            current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])
            continue

        if current_type not in allowed_node_types:
            return None, None

        reverse_nodes.append(current)
        if "Flow In" not in current.inputs:
            return None, None
        current, _current_socket = _find_single_from_input_socket(current.inputs["Flow In"])

    return None, None


def _collect_linear_flow_context(node):
    if node is None:
        return ()

    reverse_nodes = []
    visited = set()
    current = node
    while current is not None:
        node_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if node_key in visited:
            return ()
        visited.add(node_key)
        reverse_nodes.append(current)
        input_name = "Trigger" if _is_flow_side_hook_node(current) else "Flow In"
        if input_name not in getattr(current, "inputs", {}):
            break
        current, _current_socket = _find_single_from_input_socket(current.inputs[input_name])

    if not reverse_nodes:
        return ()

    root = reverse_nodes[-1]
    ordered = []
    visited.clear()
    current = root
    while current is not None:
        node_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if node_key in visited:
            return ()
        visited.add(node_key)
        ordered.append(current)
        current = _first_output_node(current, "Flow Out")
    return tuple(ordered)


def _collect_pair_groups_by_id(node_tree, start_type, end_type):
    grouped = {}
    for node in getattr(node_tree, "nodes", []):
        node_type = getattr(node, "bl_idname", "")
        if node_type not in {start_type, end_type}:
            continue
        pair_id = str(getattr(node, "af_pair_id", "") or "").strip()
        if not pair_id:
            continue
        grouped.setdefault(pair_id, []).append(node)
    return grouped


def _overlay_pair_anchor_node(pair):
    pair_kind = str(pair.get("kind", "") or "")
    if pair_kind == "SUBFLOW":
        return pair.get("end_node")
    if pair_kind == "BRANCH":
        return pair.get("start_node")
    return None


def _overlay_pair_path_nodes(pair):
    return tuple(pair.get("path_nodes", pair.get("nodes", ())) or ())


def _overlay_pair_path_node_keys(pair):
    return {_overlay_node_key(node) for node in _overlay_pair_path_nodes(pair)}


def _paired_flow_context_nodes(start_node, end_node, nodes_module):
    if start_node is None or end_node is None:
        return ()
    ordered = []
    visited = set()
    current = start_node
    first_output_name = nodes_module._pair_start_output_socket_name(start_node)
    if getattr(getattr(start_node, "outputs", None), "get", lambda _name: None)(first_output_name) is None:
        first_output_name = "Flow Out"
    while current is not None:
        node_key = int(current.as_pointer()) if hasattr(current, "as_pointer") else id(current)
        if node_key in visited:
            break
        visited.add(node_key)
        ordered.append(current)
        if current == end_node:
            return tuple(ordered)
        output_name = first_output_name if current == start_node else "Flow Out"
        current = _first_output_node(current, output_name)
    return tuple(dict.fromkeys((start_node, end_node)))


def _augment_parent_pair_nodes(parent_pair, child_pairs):
    parent_nodes = list(parent_pair.get("nodes", ()))
    parent_keys = {_overlay_node_key(node) for node in parent_nodes}
    parent_path_keys = _overlay_pair_path_node_keys(parent_pair)
    for child in child_pairs:
        anchor_node = _overlay_pair_anchor_node(child)
        if anchor_node is None:
            continue
        anchor_key = _overlay_node_key(anchor_node)
        if anchor_key not in parent_path_keys:
            continue
        for node in child.get("nodes", ()):
            node_key = _overlay_node_key(node)
            if node_key in parent_keys:
                continue
            parent_nodes.append(node)
            parent_keys.add(node_key)
    parent_pair["nodes"] = tuple(parent_nodes)
    return parent_pair


def _collect_raw_managed_overlay_pairs(node_tree, kind, start_type, end_type):
    from .. import nodes as nodes_module

    pairs = []
    for grouped_nodes in _collect_pair_groups_by_id(node_tree, start_type, end_type).values():
        start_node = next((node for node in grouped_nodes if getattr(node, "bl_idname", "") == start_type), None)
        end_node = next((node for node in grouped_nodes if getattr(node, "bl_idname", "") == end_type), None)
        if start_node is None or end_node is None:
            continue
        pairs.append(
            {
                "kind": kind,
                "start_node": start_node,
                "end_node": end_node,
                "path_nodes": _paired_flow_context_nodes(start_node, end_node, nodes_module),
                "nodes": _paired_flow_context_nodes(start_node, end_node, nodes_module),
            }
        )
    return pairs


def _complete_control_overlay_pair_nodes(pair, control_pairs, cache=None, visiting=None):
    if cache is None:
        cache = {}
    if visiting is None:
        visiting = set()
    pair_key = _overlay_pair_key(pair)
    cached_pair = cache.get(pair_key)
    if cached_pair is not None:
        return cached_pair
    if pair_key in visiting:
        return dict(pair)

    visiting.add(pair_key)
    completed_pair = dict(pair)
    # Control pairs nest by anchors on the parent's own body path, not by the
    # already-expanded node set that later hull and depth calculation consume.
    completed_nodes = list(_overlay_pair_path_nodes(pair))
    completed_node_keys = {_overlay_node_key(node) for node in completed_nodes}
    pair_path_keys = _overlay_pair_path_node_keys(pair)
    for candidate in control_pairs:
        if candidate is pair:
            continue
        anchor_node = _overlay_pair_anchor_node(candidate)
        if anchor_node is None:
            continue
        if _overlay_node_key(anchor_node) not in pair_path_keys:
            continue
        completed_child = _complete_control_overlay_pair_nodes(
            candidate,
            control_pairs,
            cache=cache,
            visiting=visiting,
        )
        for node in completed_child.get("nodes", ()):
            node_key = _overlay_node_key(node)
            if node_key in completed_node_keys:
                continue
            completed_nodes.append(node)
            completed_node_keys.add(node_key)
    completed_pair["nodes"] = tuple(completed_nodes)
    cache[pair_key] = completed_pair
    visiting.discard(pair_key)
    return completed_pair


def _collect_control_overlay_pairs(node_tree):
    raw_pairs = []
    raw_pairs.extend(_collect_raw_managed_overlay_pairs(node_tree, "SUBFLOW", "AFNodeSubflowStart", "AFNodeSubflowJoin"))
    raw_pairs.extend(_collect_raw_managed_overlay_pairs(node_tree, "BRANCH", "AFNodeBranchStart", "AFNodeBranchEnd"))
    cache = {}
    return [
        _complete_control_overlay_pair_nodes(pair, raw_pairs, cache=cache, visiting=set())
        for pair in raw_pairs
    ]


def _collect_managed_overlay_pairs(node_tree, kind, start_type, end_type, child_pairs=None):
    pairs = [dict(pair) for pair in _collect_raw_managed_overlay_pairs(node_tree, kind, start_type, end_type)]
    if kind in {"EXECUTION", "TASK"} and child_pairs:
        pairs = [_augment_parent_pair_nodes(pair, child_pairs) for pair in pairs]
    return pairs


def _collect_repeat_overlay_pairs(node_tree):
    pairs = _collect_managed_overlay_pairs(node_tree, "REPEAT", "AFNodeRepeatStart", "AFNodeRepeatEnd")
    if not pairs:
        return pairs

    context_validity = {}
    valid_pairs = []
    for pair in pairs:
        context_nodes = _collect_linear_flow_context(pair.get("start_node"))
        context_key = tuple(_overlay_node_key(node) for node in context_nodes)
        if not context_key:
            context_nodes = tuple(pair.get("path_nodes", ()) or ())
            context_key = tuple(_overlay_node_key(node) for node in context_nodes)
        if not context_key:
            continue
        is_valid = context_validity.get(context_key)
        if is_valid is None:
            is_valid = bool(_scan_repeat_pairs(context_nodes, lambda entry: entry).get("ok", False))
            context_validity[context_key] = is_valid
        if is_valid:
            valid_pairs.append(pair)
    return valid_pairs


def _collect_execution_overlay_pairs(node_tree, control_pairs=None):
    if control_pairs is None:
        control_pairs = _collect_control_overlay_pairs(node_tree)
    return _collect_managed_overlay_pairs(node_tree, "EXECUTION", "AFNodeStart", "AFNodeEnd", child_pairs=control_pairs)


def _collect_task_overlay_pairs(node_tree, control_pairs=None):
    if control_pairs is None:
        control_pairs = _collect_control_overlay_pairs(node_tree)
    return _collect_managed_overlay_pairs(node_tree, "TASK", "AFNodeTaskStart", "AFNodeTaskOutput", child_pairs=control_pairs)


def _collect_subflow_overlay_pairs(node_tree, control_pairs=None):
    if control_pairs is None:
        control_pairs = _collect_control_overlay_pairs(node_tree)
    return [dict(pair) for pair in control_pairs if str(pair.get("kind", "")) == "SUBFLOW"]


def _collect_branch_overlay_pairs(node_tree, control_pairs=None):
    if control_pairs is None:
        control_pairs = _collect_control_overlay_pairs(node_tree)
    return [dict(pair) for pair in control_pairs if str(pair.get("kind", "")) == "BRANCH"]


def _overlay_pair_key(pair):
    start_node = pair["start_node"]
    end_node = pair["end_node"]
    return (
        _overlay_node_key(start_node),
        _overlay_node_key(end_node),
        str(pair.get("kind", "")),
    )


def _overlay_pair_node_keys(pair):
    return {_overlay_node_key(node) for node in pair.get("nodes", ())}


def _pair_hull(pair_nodes, pad=_OVERLAY_PAIR_PAD):
    if not pair_nodes:
        return ()
    points = []
    for node in pair_nodes:
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type in {"AFNodeStart", "AFNodeEnd", "AFNodeTaskStart", "AFNodeTaskOutput", "AFNodeRepeatStart", "AFNodeRepeatEnd", "AFNodeSubflowStart", "AFNodeSubflowJoin", "AFNodeBranchStart", "AFNodeBranchEnd"}:
            x1, y1, x2, y2 = _paired_zone_node_bounds(node, pad=pad)
        else:
            x1, y1, x2, y2 = _node_bounds(node, pad=pad)
        points.extend(((x1, y1), (x2, y1), (x2, y2), (x1, y2)))
    hull = _convex_hull(points)
    return tuple(hull)


def _repeat_pair_hull(pair_nodes, pad=_OVERLAY_PAIR_PAD):
    return _pair_hull(pair_nodes, pad=pad)


def _annotate_overlay_pair_nesting(pairs):
    annotated_pairs = []
    pair_node_sets = {}
    for pair in pairs:
        annotated = dict(pair)
        annotated["children"] = []
        annotated["depth"] = 0
        annotated_pairs.append(annotated)
        pair_node_sets[_overlay_pair_key(annotated)] = _overlay_pair_node_keys(annotated)

    for parent in annotated_pairs:
        parent_key = _overlay_pair_key(parent)
        parent_nodes = pair_node_sets[parent_key]
        direct_children = []
        for child in annotated_pairs:
            if child is parent:
                continue
            child_key = _overlay_pair_key(child)
            child_nodes = pair_node_sets[child_key]
            if not child_nodes or not child_nodes < parent_nodes:
                continue
            is_direct_child = True
            for candidate in annotated_pairs:
                if candidate is parent or candidate is child:
                    continue
                candidate_nodes = pair_node_sets[_overlay_pair_key(candidate)]
                if child_nodes < candidate_nodes and candidate_nodes < parent_nodes:
                    is_direct_child = False
                    break
            if is_direct_child:
                direct_children.append(child)
        parent["children"] = direct_children

    def assign_depth(pair):
        if not pair["children"]:
            pair["depth"] = 0
            return 0
        pair["depth"] = max(assign_depth(child) for child in pair["children"]) + 1
        return pair["depth"]

    for pair in annotated_pairs:
        assign_depth(pair)
    return annotated_pairs


def _overlay_pair_hull(pair, cache=None, pad=_OVERLAY_PAIR_PAD, nested_gap=_OVERLAY_NESTED_GAP):
    if cache is None:
        cache = {}
    pair_key = _overlay_pair_key(pair)
    if pair_key in cache:
        return cache[pair_key]

    points = list(_pair_hull(pair.get("nodes", ()), pad=pad))
    for child in pair.get("children", ()):
        child_hull = _overlay_pair_hull(child, cache=cache, pad=pad, nested_gap=nested_gap)
        points.extend(_inflate_polygon(child_hull, nested_gap))

    hull = tuple(_convex_hull(points))
    cache[pair_key] = hull
    return hull


def _overlay_pair_palette(kind):
    if kind == "EXECUTION":
        return _EXECUTION_OVERLAY_FILL_COLOR, _EXECUTION_OVERLAY_OUTLINE_COLOR
    if kind == "TASK":
        return _TASK_OVERLAY_FILL_COLOR, _TASK_OVERLAY_OUTLINE_COLOR
    if kind == "SUBFLOW":
        return _SUBFLOW_BRANCH_OVERLAY_FILL_COLOR, _SUBFLOW_BRANCH_OVERLAY_OUTLINE_COLOR
    if kind == "BRANCH":
        return _SUBFLOW_BRANCH_OVERLAY_FILL_COLOR, _SUBFLOW_BRANCH_OVERLAY_OUTLINE_COLOR
    return _REPEAT_OVERLAY_FILL_COLOR, _REPEAT_OVERLAY_OUTLINE_COLOR


def _append_overlay_entry(entries, slots, node, color, line_width):
    return _append_overlay_entry_with_style(entries, slots, node, color, line_width, "STATIC")


def _overlay_style_priority(style):
    style_name = str(style or "STATIC")
    if style_name == "ERROR":
        return 300
    if style_name == "RUNNING":
        return 200
    if style_name == "AUTO_TICK":
        return 140
    if style_name == "BACKGROUND_STEP_PULSE":
        return 120
    if style_name == "BACKGROUND_PULSE":
        return 100
    return 0


def _append_overlay_entry_with_style(entries, slots, node, color, line_width, style):
    if node is None:
        return
    node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
    style_name = str(style or "STATIC")
    priority = _overlay_style_priority(style_name)
    existing = slots.get(node_key)
    if existing is not None and int(existing["priority"]) > priority:
        return
    payload = (node, color, line_width, style_name)
    if existing is None:
        slots[node_key] = {"index": len(entries), "priority": priority}
        entries.append(payload)
        return
    entries[int(existing["index"])] = payload
    slots[node_key] = {"index": int(existing["index"]), "priority": priority}


def _overlay_pulse_state(style):
    pulse_style = str(style or "STATIC")
    if pulse_style == "AUTO_TICK":
        phase = time.monotonic() * 1.15
        wave = 0.5 + (0.5 * math.sin(phase))
        return {
            "alpha_scale": 0.72 + (wave * 0.20),
            "pad_scale": 0.96,
            "line_scale": 0.92,
        }
    if pulse_style == "BACKGROUND_PULSE":
        phase = time.monotonic() * 1.75
        wave = 0.5 + (0.5 * math.sin(phase))
        return {
            "alpha_scale": 0.55 + (wave * 0.85),
            "pad_scale": 1.0,
            "line_scale": 1.0,
        }
    if pulse_style == "BACKGROUND_STEP_PULSE":
        phase = time.monotonic() * 2.10
        wave = 0.5 + (0.5 * math.sin(phase))
        return {
            "alpha_scale": 0.45 + (wave * 1.10),
            "pad_scale": 1.0,
            "line_scale": 1.0,
        }
    return {
        "alpha_scale": 1.0,
        "pad_scale": 1.0,
        "line_scale": 1.0,
    }
