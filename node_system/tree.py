import bpy
from bpy.app.handlers import persistent

from ..runtime_core.registration import safe_register_class, safe_unregister_class

_SYNC_RETRY_COUNTS = {}
_SYNC_TIMER_ACTIVE = False
_GROUP_TREE_SYNC_RETRY_COUNTS = {}
_GROUP_TREE_SYNC_TIMER_ACTIVE = False
_GROUP_NODE_CONSISTENCY_TIMER_ACTIVE = False
_SYNC_SUSPENDED = False
_TREE_RUNTIME_REVISIONS = {}
_AUTO_CAST_LINK_DEPTH = 0
_REROUTE_DEFAULT_SOCKET = "NodeSocketColor"
_INVALID_SOCKET_IDNAMES = {"", "NodeSocketVirtual", "NodeSocketUndefined"}
_NUMERIC_SOCKET_FAMILY_BY_IDNAME = {
    "NodeSocketBool": "NodeSocketBool",
    "NodeSocketInt": "NodeSocketInt",
    "NodeSocketFloat": "NodeSocketFloat",
    "NodeSocketVector": "NodeSocketVector",
    "AFSocketBooleanValue": "NodeSocketBool",
    "AFSocketIntegerValue": "NodeSocketInt",
    "AFSocketFloatValue": "NodeSocketFloat",
    "AFSocketVectorValue": "NodeSocketVector",
}
_NUMERIC_SOCKET_IDNAMES = set(_NUMERIC_SOCKET_FAMILY_BY_IDNAME.keys())
_STRING_SOCKET_FAMILY_BY_IDNAME = {
    "NodeSocketString": "NodeSocketString",
    "AFSocketString": "NodeSocketString",
}
_CONVERSION_MODE_BY_SOCKET_TYPES = {
    ("NodeSocketBool", "NodeSocketInt"): "BOOL_TO_INT",
    ("NodeSocketBool", "NodeSocketFloat"): "BOOL_TO_FLOAT",
    ("NodeSocketBool", "NodeSocketVector"): "BOOL_TO_VECTOR",
    ("NodeSocketInt", "NodeSocketBool"): "INT_TO_BOOL",
    ("NodeSocketInt", "NodeSocketFloat"): "INT_TO_FLOAT",
    ("NodeSocketInt", "NodeSocketVector"): "INT_TO_VECTOR",
    ("NodeSocketFloat", "NodeSocketBool"): "FLOAT_TO_BOOL",
    ("NodeSocketFloat", "NodeSocketInt"): "FLOAT_TO_INT",
    ("NodeSocketFloat", "NodeSocketVector"): "FLOAT_TO_VECTOR",
    ("NodeSocketVector", "NodeSocketBool"): "VECTOR_TO_BOOL",
    ("NodeSocketVector", "NodeSocketInt"): "VECTOR_TO_INT",
    ("NodeSocketVector", "NodeSocketFloat"): "VECTOR_TO_FLOAT",
}
_PREVIEW_DYNAMIC_SOCKET_IDNAME = "AFSocketPreviewData"
_PREVIEW_DYNAMIC_MODE_TO_SOCKET = {
    "OBJECT": "AFSocketObjectList",
    "OBJECT_LIST": "AFSocketObjectList",
    "STRING": "NodeSocketString",
    "BOOLEAN": "NodeSocketBool",
    "INTEGER": "NodeSocketInt",
    "FLOAT": "NodeSocketFloat",
    "VECTOR": "NodeSocketVector",
    "ROTATION": "NodeSocketRotation",
    "MATRIX": "NodeSocketMatrix",
    "DISPLAY_TYPE": "AFSocketDisplayType",
    "ROTATION_MODE": "AFSocketRotationMode",
    "PROPERTY_DEFINITION": "AFSocketPropertyDefinition",
    "PROPERTY_ASSIGNMENT": "AFSocketPropertyAssignment",
    "PROPERTY_PACKAGE": "AFSocketPropertyPackage",
    "TASK_REF": "AFSocketTaskRef",
    "TASK_PLAN": "AFSocketTaskPlan",
    "TASK_HANDLE": "AFSocketTaskHandle",
    "REPORT": "AFSocketReport",
}
_PREVIEW_DYNAMIC_SUPPORTED_SOCKET_TYPES = set(_PREVIEW_DYNAMIC_MODE_TO_SOCKET.values())


def suspend_runtime_sync():
    global _SYNC_SUSPENDED
    _SYNC_SUSPENDED = True


def resume_runtime_sync():
    global _SYNC_SUSPENDED
    _SYNC_SUSPENDED = False


def _runtime_sync_enabled():
    return not _SYNC_SUSPENDED


def _tree_runtime_revision_key(node_tree):
    if node_tree is None:
        return None
    return int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)


def _touch_tree_runtime_revision(node_tree):
    cache_key = _tree_runtime_revision_key(node_tree)
    if cache_key is None:
        return
    _TREE_RUNTIME_REVISIONS[cache_key] = int(_TREE_RUNTIME_REVISIONS.get(cache_key, 0)) + 1
    if len(_TREE_RUNTIME_REVISIONS) > 256:
        stale_keys = [key for key in _TREE_RUNTIME_REVISIONS.keys() if key != cache_key]
        for stale_key in stale_keys[:-128]:
            _TREE_RUNTIME_REVISIONS.pop(stale_key, None)


def node_tree_runtime_revision(node_tree):
    cache_key = _tree_runtime_revision_key(node_tree)
    if cache_key is None:
        return 0
    return int(_TREE_RUNTIME_REVISIONS.get(cache_key, 0) or 0)


def _link_is_valid(link):
    return bool(getattr(link, "is_valid", True))


def _socket_links(socket):
    return [link for link in getattr(socket, "links", []) if _link_is_valid(link)]


def _socket_idname(socket):
    return str(getattr(socket, "bl_idname", "") or "")


def _normalize_numeric_socket_type(socket_type):
    return _NUMERIC_SOCKET_FAMILY_BY_IDNAME.get(str(socket_type or ""), str(socket_type or ""))


def _normalize_string_socket_type(socket_type):
    return _STRING_SOCKET_FAMILY_BY_IDNAME.get(str(socket_type or ""), str(socket_type or ""))


def _effective_socket_type(node, socket):
    socket_idname = _socket_idname(socket)
    if getattr(node, "bl_idname", "") == "NodeReroute":
        reroute_socket_type = str(getattr(node, "socket_idname", "") or "")
        if reroute_socket_type and reroute_socket_type not in _INVALID_SOCKET_IDNAMES and reroute_socket_type != _REROUTE_DEFAULT_SOCKET:
            return reroute_socket_type
        return ""
    if getattr(node, "bl_idname", "") == "AFNodePreviewData" and socket_idname == _PREVIEW_DYNAMIC_SOCKET_IDNAME:
        if bool(getattr(socket, "af_is_virtual", False)):
            return ""
        preview_mode = str(getattr(node, "preview_mode", "OBJECT_LIST") or "OBJECT_LIST")
        return _PREVIEW_DYNAMIC_MODE_TO_SOCKET.get(preview_mode, "")
    if socket_idname == "AFSocketRotationValue":
        return "NodeSocketRotation"
    normalized_string = _normalize_string_socket_type(socket_idname)
    if normalized_string == "NodeSocketString":
        return normalized_string
    return socket_idname


def is_resolved_flow_socket(node, socket):
    socket_type = _effective_socket_type(node, socket)
    if not socket_type:
        return False
    try:
        from .sockets import is_flow_socket_idname

        return bool(is_flow_socket_idname(socket_type))
    except Exception:
        return str(socket_type or "") == "AFSocketFlow"


def _link_conversion_mode(from_socket_type, to_socket_type):
    normalized_from = _normalize_numeric_socket_type(from_socket_type)
    normalized_to = _normalize_numeric_socket_type(to_socket_type)
    return _CONVERSION_MODE_BY_SOCKET_TYPES.get((str(normalized_from), str(normalized_to)))


def _link_types_are_compatible(from_socket_type, to_socket_type):
    from_socket_type = str(from_socket_type or "")
    to_socket_type = str(to_socket_type or "")
    if not from_socket_type or not to_socket_type:
        return False
    if from_socket_type == to_socket_type:
        return True
    if from_socket_type == _PREVIEW_DYNAMIC_SOCKET_IDNAME and to_socket_type in _PREVIEW_DYNAMIC_SUPPORTED_SOCKET_TYPES:
        return True
    if to_socket_type == _PREVIEW_DYNAMIC_SOCKET_IDNAME and from_socket_type in _PREVIEW_DYNAMIC_SUPPORTED_SOCKET_TYPES:
        return True
    if from_socket_type in _NUMERIC_SOCKET_IDNAMES and to_socket_type in _NUMERIC_SOCKET_IDNAMES:
        return True
    if _normalize_string_socket_type(from_socket_type) == "NodeSocketString" and _normalize_string_socket_type(to_socket_type) == "NodeSocketString":
        return True
    property_socket_pair = {from_socket_type, to_socket_type}
    if property_socket_pair == {"AFSocketPropertyDefinition", "AFSocketPropertyAssignment"}:
        return True
    return False


def _link_should_auto_convert(link):
    if link is None:
        return None
    if getattr(link.to_node, "bl_idname", "") == "NodeReroute":
        return None
    from_socket_type = _effective_socket_type(getattr(link, "from_node", None), getattr(link, "from_socket", None))
    to_socket_type = _effective_socket_type(getattr(link, "to_node", None), getattr(link, "to_socket", None))
    return _link_conversion_mode(from_socket_type, to_socket_type)


def _mark_link_validity(link, is_valid):
    try:
        link.is_valid = bool(is_valid)
    except Exception:
        pass


def _refresh_link_validity(node_tree):
    if node_tree is None:
        return
    changed = False
    invalid_links = []
    for link in getattr(node_tree, "links", []):
        from_node = getattr(link, "from_node", None)
        to_node = getattr(link, "to_node", None)
        from_socket_type = _effective_socket_type(from_node, getattr(link, "from_socket", None))
        to_socket_type = _effective_socket_type(to_node, getattr(link, "to_socket", None))

        preview_virtual_link = bool(
            getattr(to_node, "bl_idname", "") == "AFNodePreviewData"
            and _socket_idname(getattr(link, "to_socket", None)) == _PREVIEW_DYNAMIC_SOCKET_IDNAME
            and bool(getattr(getattr(link, "to_socket", None), "af_is_virtual", False))
            and from_socket_type in _PREVIEW_DYNAMIC_SUPPORTED_SOCKET_TYPES
        )
        if not from_socket_type or not to_socket_type:
            # Keep unresolved reroute staging links editable until the chain type settles.
            is_supported = bool(
                getattr(from_node, "bl_idname", "") == "NodeReroute"
                or getattr(to_node, "bl_idname", "") == "NodeReroute"
                or preview_virtual_link
            )
        else:
            is_supported = _link_types_are_compatible(from_socket_type, to_socket_type)
        previous_valid = bool(getattr(link, "is_valid", True))
        _mark_link_validity(link, is_supported)
        if previous_valid != bool(is_supported):
            changed = True
        if not is_supported:
            invalid_links.append(link)
    for link in invalid_links:
        try:
            node_tree.links.remove(link)
            changed = True
        except Exception:
            pass
    if changed:
        _tag_node_editor_redraw(node_tree.name)


def _insert_auto_cast_node(node_tree, link, conversion_mode):
    global _AUTO_CAST_LINK_DEPTH
    if node_tree is None or link is None or not conversion_mode:
        return False

    from_socket = getattr(link, "from_socket", None)
    to_socket = getattr(link, "to_socket", None)
    from_node = getattr(link, "from_node", None)
    to_node = getattr(link, "to_node", None)
    if from_socket is None or to_socket is None or from_node is None or to_node is None:
        return False

    try:
        from_location = getattr(from_node, "location", None)
        to_location = getattr(to_node, "location", None)
        mid_x = ((float(from_location.x) if from_location is not None else 0.0) + (float(to_location.x) if to_location is not None else 0.0)) * 0.5
        mid_y = ((float(from_location.y) if from_location is not None else 0.0) + (float(to_location.y) if to_location is not None else 0.0)) * 0.5
    except Exception:
        mid_x = 0.0
        mid_y = 0.0

    try:
        node_tree.links.remove(link)
    except Exception:
        pass

    cast_node = node_tree.nodes.new("AFNodeConvertValue")
    cast_node.conversion_mode = conversion_mode
    cast_node.location = (mid_x, mid_y)
    cast_node.select = False
    if getattr(from_node, "parent", None) == getattr(to_node, "parent", None):
        cast_node.parent = getattr(from_node, "parent", None)

    _AUTO_CAST_LINK_DEPTH += 1
    try:
        node_tree.links.new(from_socket, cast_node.inputs[0])
        node_tree.links.new(cast_node.outputs[0], to_socket)
    finally:
        _AUTO_CAST_LINK_DEPTH = max(0, _AUTO_CAST_LINK_DEPTH - 1)
    return True


def _sync_dynamic_node_inputs(node_tree):
    if not _runtime_sync_enabled():
        return
    try:
        from .. import nodes as nodes_module
    except Exception:
        return
    pair_guard = getattr(nodes_module, "_PAIR_NODE_SYNC_GUARD", None)
    tree_key = int(node_tree.as_pointer()) if hasattr(node_tree, "as_pointer") else id(node_tree)
    if pair_guard is not None and tree_key in pair_guard:
        return
    pair_node_sync_fn = getattr(nodes_module, "_sync_paired_flow_nodes", None)
    if pair_node_sync_fn is not None:
        try:
            pair_node_sync_fn(node_tree)
        except Exception:
            pass
    sync_fn = getattr(nodes_module, "_sync_physics_bake_task_inputs", None)
    task_step_sync_fn = getattr(nodes_module, "_sync_task_step_sockets", None)
    bake_target_sync_fn = getattr(nodes_module, "_sync_bake_target_sockets", None)
    physics_bake_target_sync_fn = getattr(nodes_module, "_sync_physics_bake_target_sockets", None)
    evaluate_dependencies_sync_fn = getattr(nodes_module, "_sync_evaluate_task_dependencies_sockets", None)
    render_target_sync_fn = getattr(nodes_module, "_sync_render_target_sockets", None)
    run_task_plan_sync_fn = getattr(nodes_module, "_sync_run_task_plan_sockets", None)
    task_output_sync_fn = getattr(nodes_module, "_sync_task_output_sockets", None)
    branch_end_sync_fn = getattr(nodes_module, "_sync_branch_end_sockets", None)
    run_background_task_plan_sync_fn = getattr(nodes_module, "_sync_run_background_task_plan_sockets", None)
    index_switch_sync_fn = getattr(nodes_module, "_sync_index_switch_sockets", None)
    preview_data_sync_fn = getattr(nodes_module, "_sync_preview_data_sockets", None)
    parse_property_package_sync_fn = getattr(nodes_module, "_sync_parse_property_package_sockets", None)
    hide_report_outputs_fn = getattr(nodes_module, "_hide_report_outputs", None)
    if (
        sync_fn is None
        and task_step_sync_fn is None
        and bake_target_sync_fn is None
        and physics_bake_target_sync_fn is None
        and evaluate_dependencies_sync_fn is None
        and render_target_sync_fn is None
        and run_task_plan_sync_fn is None
        and task_output_sync_fn is None
        and branch_end_sync_fn is None
        and run_background_task_plan_sync_fn is None
        and index_switch_sync_fn is None
        and preview_data_sync_fn is None
        and parse_property_package_sync_fn is None
        and hide_report_outputs_fn is None
    ):
        return
    for node in node_tree.nodes:
        if getattr(node, "bl_idname", "") == "AFNodeBakeTask" and bake_target_sync_fn is not None:
            try:
                bake_target_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodePhysicsBakeTask":
            try:
                if physics_bake_target_sync_fn is not None:
                    physics_bake_target_sync_fn(node)
                else:
                    sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeTaskStep" and task_step_sync_fn is not None:
            try:
                task_step_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeEvaluateTaskDependencies" and evaluate_dependencies_sync_fn is not None:
            try:
                evaluate_dependencies_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeRunTaskPlan" and run_task_plan_sync_fn is not None:
            try:
                run_task_plan_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeTaskOutput" and task_output_sync_fn is not None:
            try:
                task_output_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeBranchEnd" and branch_end_sync_fn is not None:
            try:
                branch_end_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeRunBackgroundTaskPlan" and run_background_task_plan_sync_fn is not None:
            try:
                run_background_task_plan_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeIndexSwitch" and index_switch_sync_fn is not None:
            try:
                index_switch_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodePreviewData" and preview_data_sync_fn is not None:
            try:
                preview_data_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") == "AFNodeParsePropertyPackage" and parse_property_package_sync_fn is not None:
            try:
                parse_property_package_sync_fn(node)
            except Exception:
                pass
        if getattr(node, "bl_idname", "") in {"AFNodeRenderTarget", "AFNodeRenderTask"} and render_target_sync_fn is not None:
            try:
                render_target_sync_fn(node)
            except Exception:
                pass
        if hide_report_outputs_fn is not None:
            try:
                hide_report_outputs_fn(node)
            except Exception:
                pass


def _get_group_sync_functions():
    try:
        from .. import nodes as nodes_module
    except Exception:
        return None, None, None
    return (
        getattr(nodes_module, "_group_node_socket_signatures_match", None),
        getattr(nodes_module, "_hard_sync_group_node", None),
        getattr(nodes_module, "_sync_group_nodes_referencing_tree", None),
    )


def _iter_af_group_nodes(snapshot_nodes=False):
    node_groups = getattr(bpy.data, "node_groups", None)
    if node_groups is None:
        return
    for node_tree in node_groups:
        if getattr(node_tree, "bl_idname", "") != AFNodeTree.bl_idname:
            continue
        nodes = list(node_tree.nodes) if snapshot_nodes else node_tree.nodes
        for node in nodes:
            if getattr(node, "bl_idname", "") != "AFNodeGroup":
                continue
            yield node_tree, node


def _sync_all_group_nodes():
    if not _runtime_sync_enabled():
        return
    match_fn, hard_sync_fn, _ = _get_group_sync_functions()
    if match_fn is None or hard_sync_fn is None:
        return
    changed_tree_names = set()
    for node_tree, node in _iter_af_group_nodes():
        try:
            if match_fn(node):
                continue
            hard_sync_fn(node)
            changed_tree_names.add(node_tree.name)
        except Exception:
            pass
    for tree_name in changed_tree_names:
        _tag_node_editor_redraw(tree_name)


def queue_sync_all_group_nodes():
    def _timer():
        _sync_all_group_nodes()
        return None

    bpy.app.timers.register(_timer, first_interval=0.0)


def _iter_af_node_trees():
    node_groups = getattr(bpy.data, "node_groups", None)
    if node_groups is None:
        return
    for node_tree in node_groups:
        if getattr(node_tree, "bl_idname", "") == AFNodeTree.bl_idname:
            yield node_tree


def queue_post_register_sync():
    def _timer():
        if not _runtime_sync_enabled():
            return 0.05
        for node_tree in list(_iter_af_node_trees() or []):
            try:
                _sync_dynamic_node_inputs(node_tree)
            except Exception:
                pass
            try:
                _queue_group_tree_sync(node_tree)
            except Exception:
                pass
        _sync_all_group_nodes()
        return None

    bpy.app.timers.register(_timer, first_interval=0.0)


def _start_group_node_consistency_timer():
    global _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE
    if _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE:
        return

    def _timer():
        if not _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE:
            return None
        if not _runtime_sync_enabled():
            return 0.2

        match_fn, hard_sync_fn, _ = _get_group_sync_functions()
        if match_fn is None or hard_sync_fn is None:
            return 0.2

        changed_tree_names = set()
        for node_tree, node in _iter_af_group_nodes(snapshot_nodes=True):
            try:
                if match_fn(node):
                    continue
                hard_sync_fn(node)
                changed_tree_names.add(node_tree.name)
            except Exception:
                continue
        for tree_name in changed_tree_names:
            _tag_node_editor_redraw(tree_name)
        return 0.2

    _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE = True
    bpy.app.timers.register(_timer, first_interval=0.2, persistent=True)


@persistent
def _sync_all_group_nodes_after_load(_dummy):
    _sync_all_group_nodes()


def _queue_group_tree_sync(node_tree):
    global _GROUP_TREE_SYNC_TIMER_ACTIVE
    if node_tree is None or getattr(node_tree, "bl_idname", "") != AFNodeTree.bl_idname:
        return

    _GROUP_TREE_SYNC_RETRY_COUNTS[node_tree.name] = max(_GROUP_TREE_SYNC_RETRY_COUNTS.get(node_tree.name, 0), 6)
    if _GROUP_TREE_SYNC_TIMER_ACTIVE:
        return

    def _timer():
        global _GROUP_TREE_SYNC_TIMER_ACTIVE
        if not _GROUP_TREE_SYNC_RETRY_COUNTS:
            _GROUP_TREE_SYNC_TIMER_ACTIVE = False
            return None

        _, _, tree_sync_fn = _get_group_sync_functions()
        names = list(_GROUP_TREE_SYNC_RETRY_COUNTS.keys())
        for tree_name in names:
            tree = bpy.data.node_groups.get(tree_name)
            retries = _GROUP_TREE_SYNC_RETRY_COUNTS.get(tree_name, 0)
            if (
                tree is not None
                and getattr(tree, "bl_idname", "") == AFNodeTree.bl_idname
                and tree_sync_fn is not None
            ):
                try:
                    tree_sync_fn(tree)
                except Exception:
                    pass
            retries -= 1
            if retries <= 0:
                _GROUP_TREE_SYNC_RETRY_COUNTS.pop(tree_name, None)
            else:
                _GROUP_TREE_SYNC_RETRY_COUNTS[tree_name] = retries

        if _GROUP_TREE_SYNC_RETRY_COUNTS:
            return 0.02
        _GROUP_TREE_SYNC_TIMER_ACTIVE = False
        return None

    _GROUP_TREE_SYNC_TIMER_ACTIVE = True
    bpy.app.timers.register(_timer, first_interval=0.0)


def _node_key(node):
    try:
        return int(node.as_pointer())
    except Exception:
        return id(node)


def _socket_type_from_socket(socket):
    socket_idname = getattr(socket, "bl_idname", "")
    if socket_idname in _INVALID_SOCKET_IDNAMES:
        return None
    return socket_idname


def _socket_type_from_reroute_neighbor(reroute_node):
    socket_idname = getattr(reroute_node, "socket_idname", "")
    if socket_idname in _INVALID_SOCKET_IDNAMES:
        return None
    # Do not use default yellow as evidence when resolving through reroute chains.
    if socket_idname == _REROUTE_DEFAULT_SOCKET:
        return None
    return socket_idname


def _resolve_upstream_socket_type(node, visited):
    node_id = _node_key(node)
    if node_id in visited:
        return None
    visited.add(node_id)
    try:
        if not node.inputs:
            return None
        input_socket = node.inputs[0]
        links = _socket_links(input_socket)
        if not links:
            return None

        for link in links:
            from_node = getattr(link, "from_node", None)
            from_socket = getattr(link, "from_socket", None)
            if from_node is None or from_socket is None:
                continue
            if from_node.bl_idname == "NodeReroute":
                resolved = _resolve_upstream_socket_type(from_node, visited)
                if resolved:
                    return resolved
                resolved = _resolve_downstream_socket_type(from_node, visited)
                if resolved:
                    return resolved
                resolved = _socket_type_from_reroute_neighbor(from_node)
                if resolved:
                    return resolved
                continue
            resolved = _socket_type_from_socket(from_socket)
            if resolved:
                return resolved
        return None
    finally:
        visited.discard(node_id)


def _resolve_downstream_socket_type(node, visited):
    node_id = _node_key(node)
    if node_id in visited:
        return None
    visited.add(node_id)
    try:
        if not node.outputs:
            return None
        output_socket = node.outputs[0]
        links = _socket_links(output_socket)
        if not links:
            return None

        for link in links:
            to_node = getattr(link, "to_node", None)
            to_socket = getattr(link, "to_socket", None)
            if to_node is None or to_socket is None:
                continue
            if to_node.bl_idname == "NodeReroute":
                resolved = _resolve_downstream_socket_type(to_node, visited)
                if resolved:
                    return resolved
                resolved = _resolve_upstream_socket_type(to_node, visited)
                if resolved:
                    return resolved
                resolved = _socket_type_from_reroute_neighbor(to_node)
                if resolved:
                    return resolved
                continue
            resolved = _socket_type_from_socket(to_socket)
            if resolved:
                return resolved
        return None
    finally:
        visited.discard(node_id)


def _reroute_has_any_link(node):
    if node is None:
        return False
    if node.inputs and _socket_links(node.inputs[0]):
        return True
    if node.outputs and _socket_links(node.outputs[0]):
        return True
    return False


def _desired_reroute_socket_idname(node):
    if not _reroute_has_any_link(node):
        return _REROUTE_DEFAULT_SOCKET
    resolved = _resolve_upstream_socket_type(node, set())
    if resolved:
        return resolved
    resolved = _resolve_downstream_socket_type(node, set())
    if resolved:
        return resolved
    current = getattr(node, "socket_idname", "")
    # Preserve non-default state only while still linked during transient updates.
    if current and current not in _INVALID_SOCKET_IDNAMES and current != _REROUTE_DEFAULT_SOCKET:
        return current
    return _REROUTE_DEFAULT_SOCKET


def _tag_node_editor_redraw(tree_name=None):
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "NODE_EDITOR":
                continue
            if tree_name is None:
                area.tag_redraw()
                continue
            for space in area.spaces:
                if space.type != "NODE_EDITOR":
                    continue
                node_tree = getattr(space, "edit_tree", None)
                if node_tree is not None and node_tree.name == tree_name:
                    area.tag_redraw()
                    break


def _sync_reroute_socket_idnames(node_tree):
    total_changed = 0
    # Converge reroute chains in one sync call to avoid "next action updates previous" behavior.
    for _ in range(8):
        pass_changed = 0
        desired_map = []
        for node in node_tree.nodes:
            if node.bl_idname != "NodeReroute":
                continue
            desired_map.append((node, _desired_reroute_socket_idname(node)))
        for node, desired in desired_map:
            if node.socket_idname != desired:
                try:
                    node.socket_idname = desired
                    pass_changed += 1
                except Exception:
                    pass
        total_changed += pass_changed
        if pass_changed == 0:
            break
    if total_changed > 0:
        _tag_node_editor_redraw(node_tree.name)
    return total_changed


def _queue_tree_reroute_sync(node_tree):
    global _SYNC_TIMER_ACTIVE
    if node_tree is None:
        return
    _SYNC_RETRY_COUNTS[node_tree.name] = max(_SYNC_RETRY_COUNTS.get(node_tree.name, 0), 4)
    if _SYNC_TIMER_ACTIVE:
        return

    def _timer():
        global _SYNC_TIMER_ACTIVE
        if not _SYNC_RETRY_COUNTS:
            _SYNC_TIMER_ACTIVE = False
            return None

        names = list(_SYNC_RETRY_COUNTS.keys())
        for tree_name in names:
            tree = bpy.data.node_groups.get(tree_name)
            retries = _SYNC_RETRY_COUNTS.get(tree_name, 0)
            if tree is not None and getattr(tree, "bl_idname", "") == AFNodeTree.bl_idname:
                _sync_reroute_socket_idnames(tree)
                _refresh_link_validity(tree)
            retries -= 1
            if retries <= 0:
                _SYNC_RETRY_COUNTS.pop(tree_name, None)
            else:
                _SYNC_RETRY_COUNTS[tree_name] = retries

        if _SYNC_RETRY_COUNTS:
            return 0.03
        _SYNC_TIMER_ACTIVE = False
        return None

    _SYNC_TIMER_ACTIVE = True
    bpy.app.timers.register(_timer, first_interval=0.01)


class AFNodeTree(bpy.types.NodeTree):
    bl_idname = "AFNodeTreeType"
    bl_label = "Flow Node Editor"
    bl_icon = "NODETREE"
    bl_use_group_interface = True

    @classmethod
    def valid_socket_type(cls, socket_type):
        valid_custom = {
            "AFSocketFlow",
            "AFSocketCollectionList",
            "AFSocketObjectList",
            "AFSocketPropertyPackage",
            "AFSocketPropertyDefinition",
            "AFSocketPropertyAssignment",
            "AFSocketTaskRef",
            "AFSocketTaskPlan",
            "AFSocketTaskHandle",
            "AFSocketReport",
            "AFSocketDisplayType",
            "AFSocketRotationMode",
        }
        valid_builtin = {
            "NodeSocketString",
            "NodeSocketInt",
            "NodeSocketFloat",
            "NodeSocketBool",
            "NodeSocketVector",
            "NodeSocketRotation",
            "NodeSocketMatrix",
        }
        return str(socket_type) in valid_custom or str(socket_type) in valid_builtin

    def update(self):
        _touch_tree_runtime_revision(self)
        if not _runtime_sync_enabled():
            return
        try:
            from .. import nodes as nodes_module
            pair_guard = getattr(nodes_module, "_PAIR_NODE_SYNC_GUARD", None)
            tree_key = int(self.as_pointer()) if hasattr(self, "as_pointer") else id(self)
            if pair_guard is not None and tree_key in pair_guard:
                return

            pair_sync_fn = getattr(nodes_module, "_sync_paired_flow_nodes", None)
            if pair_sync_fn is not None:
                pair_sync_fn(self)
        except Exception:
            pass
        _sync_dynamic_node_inputs(self)
        _sync_reroute_socket_idnames(self)
        _refresh_link_validity(self)
        _queue_tree_reroute_sync(self)
        _queue_group_tree_sync(self)

    def interface_update(self, context):
        del context
        _touch_tree_runtime_revision(self)
        if not _runtime_sync_enabled():
            return
        try:
            from .. import nodes as nodes_module
            pair_guard = getattr(nodes_module, "_PAIR_NODE_SYNC_GUARD", None)
            tree_key = int(self.as_pointer()) if hasattr(self, "as_pointer") else id(self)
            if pair_guard is not None and tree_key in pair_guard:
                return

            pair_sync_fn = getattr(nodes_module, "_sync_paired_flow_nodes", None)
            if pair_sync_fn is not None:
                pair_sync_fn(self)
        except Exception:
            pass
        _sync_dynamic_node_inputs(self)
        _sync_reroute_socket_idnames(self)
        _refresh_link_validity(self)
        _queue_tree_reroute_sync(self)
        _queue_group_tree_sync(self)

    def insert_link(self, link):
        _touch_tree_runtime_revision(self)
        if not _runtime_sync_enabled():
            return
        if link is None:
            return

        from_socket = getattr(link, "from_socket", None)
        to_socket = getattr(link, "to_socket", None)
        from_node = getattr(link, "from_node", None)
        to_node = getattr(link, "to_node", None)
        from_socket_type = _effective_socket_type(from_node, from_socket)
        to_socket_type = _effective_socket_type(to_node, to_socket)
        from_unresolved_reroute = getattr(from_node, "bl_idname", "") == "NodeReroute" and not from_socket_type
        to_unresolved_reroute = getattr(to_node, "bl_idname", "") == "NodeReroute" and not to_socket_type
        to_virtual_preview = bool(
            getattr(to_node, "bl_idname", "") == "AFNodePreviewData"
            and _socket_idname(to_socket) == _PREVIEW_DYNAMIC_SOCKET_IDNAME
            and bool(getattr(to_socket, "af_is_virtual", False))
        )

        if _AUTO_CAST_LINK_DEPTH <= 0:
            conversion_mode = _link_should_auto_convert(link)
            if conversion_mode:
                if _insert_auto_cast_node(self, link, conversion_mode):
                    _sync_dynamic_node_inputs(self)
                    _sync_reroute_socket_idnames(self)
                    _refresh_link_validity(self)
                    _queue_tree_reroute_sync(self)
                    _queue_group_tree_sync(self)
                return

        if to_virtual_preview and from_socket_type in _PREVIEW_DYNAMIC_SUPPORTED_SOCKET_TYPES:
            is_supported = True
        elif to_unresolved_reroute and from_socket_type:
            is_supported = True
        elif from_unresolved_reroute and to_socket_type:
            is_supported = True
        else:
            is_supported = _link_types_are_compatible(from_socket_type, to_socket_type)
        if not is_supported:
            try:
                self.links.remove(link)
            except Exception:
                pass
            _tag_node_editor_redraw(self.name)
            _sync_dynamic_node_inputs(self)
            _sync_reroute_socket_idnames(self)
            _queue_tree_reroute_sync(self)
            _queue_group_tree_sync(self)
            return
        _mark_link_validity(link, is_supported)
        _tag_node_editor_redraw(self.name)

        # Keep immediate behavior for fan-out / branch reroute creation.
        if is_supported and to_node and to_node.bl_idname == "NodeReroute":
            try:
                if from_socket_type:
                    to_node.socket_idname = from_socket_type
            except Exception:
                pass
        if is_supported and from_node and from_node.bl_idname == "NodeReroute":
            try:
                if to_socket_type:
                    from_node.socket_idname = to_socket_type
            except Exception:
                pass
        try:
            from .. import nodes as nodes_module

            pair_sync_fn = getattr(nodes_module, "_sync_paired_flow_nodes", None)
            if pair_sync_fn is not None:
                pair_sync_fn(self)
        except Exception:
            pass
        _sync_dynamic_node_inputs(self)
        _sync_reroute_socket_idnames(self)
        _refresh_link_validity(self)
        # A few delayed retries handle single-line insertion timing.
        _queue_tree_reroute_sync(self)


CLASSES = (
    AFNodeTree,
)


def register():
    for cls in CLASSES:
        safe_register_class(cls)
    if _sync_all_group_nodes_after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_sync_all_group_nodes_after_load)
    _start_group_node_consistency_timer()


def unregister():
    global _SYNC_TIMER_ACTIVE, _GROUP_TREE_SYNC_TIMER_ACTIVE, _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE
    _SYNC_RETRY_COUNTS.clear()
    _GROUP_TREE_SYNC_RETRY_COUNTS.clear()
    _SYNC_TIMER_ACTIVE = False
    _GROUP_TREE_SYNC_TIMER_ACTIVE = False
    _GROUP_NODE_CONSISTENCY_TIMER_ACTIVE = False
    if _sync_all_group_nodes_after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_sync_all_group_nodes_after_load)
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
