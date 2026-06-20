import bpy

from .editor_utils import _get_active_flow_tree, _tag_flow_node_editor_redraw

GROUP_FORBIDDEN_NODE_TYPES = {
    "AFNodeStart",
    "AFNodeEnd",
    "NodeGroupInput",
    "NodeGroupOutput",
}


def _is_group_editing_context(context):
    space = getattr(context, "space_data", None)
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return False
    return len(getattr(space, "path", [])) > 1


def _get_active_group_node(context):
    tree = _get_active_flow_tree(context)
    node = getattr(context, "active_node", None)
    if tree is None or node is None:
        return None
    if getattr(node, "bl_idname", "") != "AFNodeGroup":
        return None
    if getattr(node, "group_tree", None) is None:
        return None
    return node


def _node_bounds_contains_point(node, view_x, view_y, pad=18.0):
    bounds = _node_bounds_for_point_test(node, pad=pad)
    if bounds is None:
        return False
    left, right, top, bottom = bounds
    return left <= view_x <= right and bottom <= view_y <= top


def _node_bounds_for_point_test(node, pad=18.0):
    node_loc = getattr(node, "location_absolute", None)
    if node_loc is None:
        node_loc = getattr(node, "location", None)
    if node_loc is None:
        return None

    dimensions = getattr(node, "dimensions", None)
    width = float(getattr(node, "width", 140.0))
    height = 100.0
    if dimensions is not None:
        try:
            if float(dimensions.x) > 1.0:
                width = float(dimensions.x)
            if float(dimensions.y) > 1.0:
                height = float(dimensions.y)
        except Exception:
            pass
    if bool(getattr(node, "hide", False)):
        height = max(height, 32.0)
    else:
        try:
            visible_input_count = len([socket for socket in getattr(node, "inputs", []) if not bool(getattr(socket, "hide", False))])
            visible_output_count = len([socket for socket in getattr(node, "outputs", []) if not bool(getattr(socket, "hide", False))])
            visible_socket_count = max(visible_input_count, visible_output_count)
            estimated_height = 44.0 + (visible_socket_count * 22.0)
            height = max(height, estimated_height)
        except Exception:
            pass

    left = float(node_loc.x) - pad
    right = left + max(width, 1.0) + (pad * 2.0)
    top = float(node_loc.y) + pad
    bottom = top - max(height, 1.0) - (pad * 2.0)
    return (left, right, top, bottom)


def _distance_sq_to_rect(view_x, view_y, left, right, top, bottom):
    dx = 0.0
    if view_x < left:
        dx = left - view_x
    elif view_x > right:
        dx = view_x - right

    dy = 0.0
    if view_y < bottom:
        dy = bottom - view_y
    elif view_y > top:
        dy = view_y - top

    return (dx * dx) + (dy * dy)


def _node_hit_score(node, view_x, view_y, z_index):
    bounds = _node_bounds_for_point_test(node)
    if bounds is None:
        return None
    left, right, top, bottom = bounds
    exact_bounds = _node_bounds_for_point_test(node, pad=0.0)
    if exact_bounds is None:
        return None
    exact_left, exact_right, exact_top, exact_bottom = exact_bounds
    distance_sq = _distance_sq_to_rect(view_x, view_y, exact_left, exact_right, exact_top, exact_bottom)
    area = max(right - left, 1.0) * max(top - bottom, 1.0)
    is_group = (
        getattr(node, "bl_idname", "") == "AFNodeGroup"
        and getattr(node, "group_tree", None) is not None
    )
    is_exact_hit = exact_left <= view_x <= exact_right and exact_bottom <= view_y <= exact_top
    return (
        0 if is_exact_hit else 1,
        0 if is_group else 1,
        distance_sq,
        area,
        int(z_index),
    )


def _find_node_under_cursor(context, event, groups_only=False):
    tree = _get_active_flow_tree(context)
    region = getattr(context, "region", None)
    if tree is None or region is None or getattr(region, "type", "") != "WINDOW":
        return None

    view2d = getattr(region, "view2d", None)
    if view2d is None:
        return None

    try:
        view_x, view_y = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
    except Exception:
        return None

    candidates = []
    ordered_nodes = list(reversed(list(tree.nodes)))
    for z_index, node in enumerate(ordered_nodes):
        if groups_only and (
            getattr(node, "bl_idname", "") != "AFNodeGroup"
            or getattr(node, "group_tree", None) is None
        ):
            continue
        if not _node_bounds_contains_point(node, view_x, view_y):
            continue
        score = _node_hit_score(node, view_x, view_y, z_index)
        if score is None:
            continue
        candidates.append((score, node))
    if not candidates:
        return None
    if groups_only:
        active_group = getattr(context, "active_node", None)
        if (
            active_group is not None
            and getattr(active_group, "bl_idname", "") == "AFNodeGroup"
            and getattr(active_group, "group_tree", None) is not None
            and _node_bounds_contains_point(active_group, view_x, view_y, pad=0.0)
        ):
            return active_group
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _select_node_under_cursor(context, event):
    space = getattr(context, "space_data", None)
    tree = getattr(space, "edit_tree", None) if space is not None else None
    region = getattr(context, "region", None)
    if tree is None or region is None or getattr(region, "type", "") != "WINDOW":
        return None

    previous_active = getattr(tree.nodes, "active", None)
    previous_selected = [node for node in getattr(tree, "nodes", []) if bool(getattr(node, "select", False))]
    try:
        bpy.ops.node.select(
            extend=False,
            deselect=False,
            toggle=False,
            deselect_all=True,
            select_passthrough=False,
            socket_select=False,
            clear_viewer=False,
            location=(int(event.mouse_region_x), int(event.mouse_region_y)),
        )
    except Exception:
        return None

    selected_nodes = [node for node in getattr(tree, "nodes", []) if bool(getattr(node, "select", False))]
    active_node = getattr(tree.nodes, "active", None)
    hit_node = active_node if active_node in selected_nodes else (selected_nodes[0] if selected_nodes else None)

    for node in getattr(tree, "nodes", []):
        try:
            node.select = False
        except Exception:
            continue
    for node in previous_selected:
        try:
            node.select = True
        except Exception:
            continue
    try:
        tree.nodes.active = previous_active
    except Exception:
        pass
    return hit_node


def _make_group_nav_target(context, hit_node):
    space = getattr(context, "space_data", None)
    path_depth = len(getattr(space, "path", [])) if space is not None else 0
    if getattr(hit_node, "bl_idname", "") == "AFNodeGroup" and getattr(hit_node, "group_tree", None) is not None:
        return "GROUP"
    if hit_node is None and path_depth > 1:
        return "BLANK"
    return None


def _enter_group_node(context, group_node, reporter=None):
    if group_node is None or getattr(group_node, "bl_idname", "") != "AFNodeGroup":
        if reporter is not None:
            reporter.report({"ERROR"}, "Active node is not a valid group")
        return {"CANCELLED"}

    try:
        from ..nodes import _group_node_socket_signatures_match, _sync_group_node_sockets

        if not _group_node_socket_signatures_match(group_node):
            _sync_group_node_sockets(group_node)
    except Exception:
        pass

    space = context.space_data
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        if reporter is not None:
            reporter.report({"ERROR"}, "Open a Node Editor first")
        return {"CANCELLED"}

    group_tree = getattr(group_node, "group_tree", None)
    if group_tree is None:
        if reporter is not None:
            reporter.report({"ERROR"}, "Group tree is missing")
        return {"CANCELLED"}

    if len(space.path) == 0:
        root_tree = _get_active_flow_tree(context)
        if root_tree is None:
            if reporter is not None:
                reporter.report({"ERROR"}, "Open an Automation Flow node tree first")
            return {"CANCELLED"}
        space.path.start(root_tree)
    space.path.append(group_tree)
    _tag_flow_node_editor_redraw(group_tree.name)
    return {"FINISHED"}


def _exit_current_group(context, reporter=None):
    space = context.space_data
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        if reporter is not None:
            reporter.report({"ERROR"}, "Open a Node Editor first")
        return {"CANCELLED"}
    if len(getattr(space, "path", [])) <= 1:
        if reporter is not None:
            reporter.report({"ERROR"}, "Not currently editing a group")
        return {"CANCELLED"}

    source_group_tree = getattr(space, "edit_tree", None)
    try:
        space.path.pop()
    except Exception as exc:
        if reporter is not None:
            reporter.report({"ERROR"}, f"Failed to exit group: {exc}")
        return {"CANCELLED"}

    if source_group_tree is not None and getattr(source_group_tree, "bl_idname", "") == "AFNodeTreeType":
        try:
            from ..nodes import _sync_group_nodes_referencing_tree

            _sync_group_nodes_referencing_tree(source_group_tree)
        except Exception:
            pass
        try:
            from ..node_system.tree import _queue_group_tree_sync

            _queue_group_tree_sync(source_group_tree)
        except Exception:
            pass

    edit_tree = getattr(space, "edit_tree", None)
    if edit_tree is not None:
        _tag_flow_node_editor_redraw(edit_tree.name)
    return {"FINISHED"}


def _find_interface_socket_by_identifier(node, identifier, direction):
    sockets = node.outputs if direction == "INPUT" else node.inputs
    for socket in sockets:
        if str(getattr(socket, "identifier", "")) == str(identifier):
            return socket
    return None


def _find_group_node_socket_by_identifier(node, identifier, direction):
    try:
        from ..nodes import _build_group_node_socket_specs
    except Exception:
        return None

    group_tree = getattr(node, "group_tree", None)
    if group_tree is None:
        return None

    sockets = node.inputs if direction == "INPUT" else node.outputs
    socket_specs = _build_group_node_socket_specs(group_tree, direction)
    for socket, spec in zip(sockets, socket_specs):
        if str(spec.get("identifier", "")) == str(identifier):
            return socket
    return None


def _copy_socket_defaults(source_node, target_node):
    for source_socket, target_socket in zip(source_node.inputs, target_node.inputs):
        if getattr(source_socket, "bl_idname", "") != getattr(target_socket, "bl_idname", ""):
            continue
        if not hasattr(source_socket, "default_value") or not hasattr(target_socket, "default_value"):
            continue
        try:
            target_socket.default_value = source_socket.default_value
        except Exception:
            pass


def _clone_node_to_tree(source_node, target_tree):
    target_node = target_tree.nodes.new(source_node.bl_idname)
    skip_props = {
        "rna_type",
        "type",
        "dimensions",
        "width_hidden",
        "select",
        "inputs",
        "outputs",
        "internal_links",
        "parent",
        "location_absolute",
        "color",
        "interface",
    }
    for prop in source_node.bl_rna.properties:
        identifier = prop.identifier
        if identifier in skip_props or getattr(prop, "is_readonly", False):
            continue
        if getattr(prop, "type", "") == "COLLECTION":
            continue
        try:
            value = getattr(source_node, identifier)
        except Exception:
            continue
        try:
            setattr(target_node, identifier, value)
        except Exception:
            pass
    try:
        target_node.location = source_node.location.copy()
    except Exception:
        pass
    try:
        target_node.width = float(source_node.width)
    except Exception:
        pass
    try:
        target_node.height = float(source_node.height)
    except Exception:
        pass
    _copy_socket_defaults(source_node, target_node)
    return target_node


def _unique_interface_name(base_name, used_names):
    candidate = str(base_name or "Socket").strip() or "Socket"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate
    index = 1
    while True:
        trial = f"{candidate}.{index:03d}"
        if trial not in used_names:
            used_names.add(trial)
            return trial
        index += 1


def _group_interface_context(context):
    space = getattr(context, "space_data", None)
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return None, None
    tree = getattr(space, "edit_tree", None)
    interface = getattr(tree, "interface", None) if tree is not None else None
    if tree is None or interface is None or getattr(tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    return tree, interface
