import bpy


def _space_path_items(space):
    return list(getattr(space, "path", [])) if space is not None else []


def _space_matches_node_tree(space, node_tree):
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return False
    if getattr(space, "tree_type", "") != "AFNodeTreeType":
        return False
    if getattr(space, "edit_tree", None) == node_tree:
        return True
    return any(getattr(item, "node_tree", None) == node_tree for item in _space_path_items(space))


def _context_node_editor_space(node, context):
    node_tree = getattr(node, "id_data", None)
    for candidate_context in (context, bpy.context):
        space = getattr(candidate_context, "space_data", None)
        if _space_matches_node_tree(space, node_tree):
            return space

    window_manager = getattr(bpy.context, "window_manager", None)
    if window_manager is None:
        return None
    for window in getattr(window_manager, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in getattr(screen, "areas", []):
            if getattr(area, "type", "") != "NODE_EDITOR":
                continue
            for space in getattr(area, "spaces", []):
                if _space_matches_node_tree(space, node_tree):
                    return space
    return None


def _path_item_node_tree(item):
    return getattr(item, "node_tree", None)


def _resolve_group_path_node(previous_tree, current_tree, explicit_node=None):
    if (
        explicit_node is not None
        and getattr(explicit_node, "bl_idname", "") == "AFNodeGroup"
        and getattr(explicit_node, "group_tree", None) == current_tree
    ):
        return explicit_node
    if previous_tree is None or current_tree is None:
        return None

    candidates = [
        node
        for node in getattr(previous_tree, "nodes", [])
        if getattr(node, "bl_idname", "") == "AFNodeGroup" and getattr(node, "group_tree", None) == current_tree
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    active_node = getattr(getattr(previous_tree, "nodes", None), "active", None)
    if (
        active_node is not None
        and getattr(active_node, "bl_idname", "") == "AFNodeGroup"
        and getattr(active_node, "group_tree", None) == current_tree
    ):
        return active_node

    selected_candidates = [node for node in candidates if bool(getattr(node, "select", False))]
    if len(selected_candidates) == 1:
        return selected_candidates[0]
    return None


def _group_path_from_path_items(path_items):
    group_path = []
    if not path_items:
        return group_path

    previous_tree = _path_item_node_tree(path_items[0])
    for item in path_items[1:]:
        current_tree = _path_item_node_tree(item)
        if current_tree is None:
            continue
        group_node = _resolve_group_path_node(previous_tree, current_tree, getattr(item, "node", None))
        if group_node is not None:
            node_tree = getattr(group_node, "id_data", None)
            group_path.append(
                {
                    "tree_name": getattr(node_tree, "name", ""),
                    "node_name": str(getattr(group_node, "name", "") or ""),
                }
            )
        previous_tree = current_tree
    return group_path


def _root_tree_from_path_items(path_items):
    if not path_items:
        return None
    return _path_item_node_tree(path_items[0])


def _context_node_editor_path_items(node, context):
    return _space_path_items(_context_node_editor_space(node, context))


def _ui_group_path(node, context):
    space = _context_node_editor_space(node, context)
    path_items = _space_path_items(space)
    if path_items:
        return _group_path_from_path_items(path_items)

    root_tree = getattr(space, "node_tree", None) if space is not None else None
    edit_tree = getattr(space, "edit_tree", None) if space is not None else None
    if root_tree is not None and edit_tree is not None and root_tree != edit_tree:
        group_node = _resolve_group_path_node(root_tree, edit_tree)
        if group_node is not None:
            node_tree = getattr(group_node, "id_data", None)
            return [{"tree_name": getattr(node_tree, "name", ""), "node_name": str(getattr(group_node, "name", "") or "")}]
    return []


def _ui_root_tree(node, context):
    space = _context_node_editor_space(node, context)
    path_items = _space_path_items(space)
    if path_items:
        root_tree = _root_tree_from_path_items(path_items)
        if root_tree is not None:
            return root_tree
    if space is not None:
        root_tree = getattr(space, "node_tree", None)
        if root_tree is not None:
            return root_tree
    return getattr(node, "id_data", None)


def _ui_runner_for_node(node, context):
    try:
        from ..runtime_runner.core import FlowRunner
    except Exception:
        return None

    scene = getattr(context, "scene", None) or getattr(bpy.context, "scene", None)
    root_tree = _ui_root_tree(node, context)
    if scene is None or root_tree is None:
        return None
    try:
        runner = FlowRunner(root_tree, scene)
        runner.current_group_path = _ui_group_path(node, context)
        return runner
    except Exception:
        return None


__all__ = [
    "_space_path_items",
    "_space_matches_node_tree",
    "_context_node_editor_space",
    "_path_item_node_tree",
    "_resolve_group_path_node",
    "_group_path_from_path_items",
    "_root_tree_from_path_items",
    "_context_node_editor_path_items",
    "_ui_group_path",
    "_ui_root_tree",
    "_ui_runner_for_node",
]
