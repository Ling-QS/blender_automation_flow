import json

import bpy
from .overlay_drawing import _node_bounds
from ..node_system.editor_context import (
    _group_path_from_path_items,
    _path_item_node_tree,
    _resolve_group_path_node,
    _root_tree_from_path_items,
    _space_path_items,
)


def _load_serialized_group_path(raw_value):
    raw = str(raw_value or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    result = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "tree_name": str(item.get("tree_name", "") or ""),
                "node_name": str(item.get("node_name", "") or ""),
            }
        )
    return result


def _resolve_visible_path_target_node_name(node_tree, target_tree_name, target_node_name, group_path):
    if node_tree is None:
        return ""
    visible_tree_name = str(getattr(node_tree, "name", "") or "")
    actual_tree_name = str(target_tree_name or "")
    actual_node_name = str(target_node_name or "")
    if not actual_tree_name or not actual_node_name:
        return ""
    if visible_tree_name == actual_tree_name:
        return actual_node_name
    for step_ref in list(group_path or []):
        if str(step_ref.get("tree_name", "") or "") == visible_tree_name:
            return str(step_ref.get("node_name", "") or "")
    return ""

def _node_editor_group_path(context):
    space = getattr(context, "space_data", None)
    path_items = _space_path_items(space)
    if not path_items:
        root_tree = getattr(space, "node_tree", None) if space is not None else None
        edit_tree = getattr(space, "edit_tree", None) if space is not None else None
        if root_tree is None or edit_tree is None or root_tree == edit_tree:
            return []
        group_node = _resolve_group_path_node(root_tree, edit_tree)
        if group_node is None:
            return []
        node_tree = getattr(group_node, "id_data", None)
        return [{"tree_name": getattr(node_tree, "name", ""), "node_name": str(getattr(group_node, "name", "") or "")}]
    return _group_path_from_path_items(path_items)


def _node_editor_group_path_labels(context):
    space = getattr(context, "space_data", None)
    path_items = _space_path_items(space)
    labels = []
    if path_items:
        root_tree = _root_tree_from_path_items(path_items)
        root_label = str(getattr(root_tree, "name", "") or "").strip()
        if root_label:
            labels.append(root_label)
        previous_tree = _path_item_node_tree(path_items[0])
        for item in path_items[1:]:
            current_tree = _path_item_node_tree(item)
            if current_tree is None:
                continue
            label = str(getattr(current_tree, "name", "") or "").strip()
            if not label:
                group_node = _resolve_group_path_node(previous_tree, current_tree, getattr(item, "node", None))
                label = str(getattr(group_node, "name", "") or "").strip() if group_node is not None else ""
            if label:
                labels.append(label)
            previous_tree = current_tree
        return labels if len(labels) > 1 else []

    root_tree = getattr(space, "node_tree", None) if space is not None else None
    edit_tree = getattr(space, "edit_tree", None) if space is not None else None
    if root_tree is None or edit_tree is None or root_tree == edit_tree:
        return []
    root_label = str(getattr(root_tree, "name", "") or "").strip()
    if root_label:
        labels.append(root_label)
    group_node = _resolve_group_path_node(root_tree, edit_tree)
    label = str(getattr(edit_tree, "name", "") or "").strip()
    if not label:
        label = str(getattr(group_node, "name", "") or "").strip() if group_node is not None else ""
    if label:
        labels.append(label)
    return labels if len(labels) > 1 else []


def _node_editor_root_tree(context, fallback_tree):
    space = getattr(context, "space_data", None)
    path_items = _space_path_items(space)
    if path_items:
        root_tree = _root_tree_from_path_items(path_items)
        if root_tree is not None:
            return root_tree
    if space is not None:
        root_tree = getattr(space, "node_tree", None)
        if root_tree is not None:
            return root_tree
    return fallback_tree


def _ui_scale_factor():
    preferences = getattr(bpy.context, "preferences", None)
    system = getattr(preferences, "system", None) if preferences is not None else None
    if system is None:
        return 1.0
    return max(0.5, float(getattr(system, "ui_scale", 1.0)))


def _node_editor_zoom_factor(region=None, view2d=None):
    region = region if region is not None else getattr(bpy.context, "region", None)
    view2d = view2d if view2d is not None else (getattr(region, "view2d", None) if region is not None else None)
    if region is None or view2d is None:
        return 1.0
    try:
        origin = view2d.view_to_region(0.0, 0.0, clip=False)
        sample_x = view2d.view_to_region(100.0, 0.0, clip=False)
        sample_y = view2d.view_to_region(0.0, 100.0, clip=False)
    except Exception:
        return 1.0
    scales = []
    if origin is not None and sample_x is not None:
        scales.append(abs(float(sample_x[0]) - float(origin[0])) / 100.0)
    if origin is not None and sample_y is not None:
        scales.append(abs(float(sample_y[1]) - float(origin[1])) / 100.0)
    if not scales:
        return 1.0
    return max(0.35, min(3.0, sum(scales) / len(scales)))


def _node_visible_in_region(node, region=None, view2d=None, margin=96.0):
    region = region if region is not None else getattr(bpy.context, "region", None)
    view2d = view2d if view2d is not None else (getattr(region, "view2d", None) if region is not None else None)
    if region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
        return False
    if node is None:
        return False
    try:
        x1, y1, x2, y2 = _node_bounds(node, pad=0.0)
        top_left = view2d.view_to_region(float(x1), float(y1), clip=False)
        bottom_right = view2d.view_to_region(float(x2), float(y2), clip=False)
    except Exception:
        return False
    if top_left is None or bottom_right is None:
        return False
    left = min(float(top_left[0]), float(bottom_right[0]))
    right = max(float(top_left[0]), float(bottom_right[0]))
    bottom = min(float(top_left[1]), float(bottom_right[1]))
    top = max(float(top_left[1]), float(bottom_right[1]))
    margin = float(margin)
    return not (
        right < -margin
        or left > float(region.width) + margin
        or top < -margin
        or bottom > float(region.height) + margin
    )


def _iter_visible_nodes(node_tree, region=None, view2d=None, margin=96.0):
    if node_tree is None:
        return
    for node in getattr(node_tree, "nodes", []):
        if _node_visible_in_region(node, region=region, view2d=view2d, margin=margin):
            yield node
