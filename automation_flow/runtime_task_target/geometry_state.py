import bpy


def _resolve_geometry_task_source_node(task_ref):
    if not isinstance(task_ref, dict):
        return None
    tree_name = str(task_ref.get("source_tree_name", "") or "").strip()
    node_name = str(task_ref.get("source_node", "") or "").strip()
    if not tree_name or not node_name:
        return None
    node_tree = bpy.data.node_groups.get(tree_name)
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None
    node = node_tree.nodes.get(node_name)
    if node is None or getattr(node, "bl_idname", "") != "AFNodeBakeTask":
        return None
    return node


def _read_geometry_bake_tracked_packed_cache_state(
    node,
    *,
    gn_packed_cache_state_prop,
    json_module,
):
    if node is None:
        return None
    raw_value = node.get(gn_packed_cache_state_prop)
    if not raw_value:
        return None
    try:
        state = json_module.loads(str(raw_value))
    except Exception:
        return None
    if not isinstance(state, dict):
        return None
    if not bool(state.get("has_cache", False)):
        return None
    return state


def _write_geometry_bake_tracked_packed_cache_state(
    task_ref,
    frame_range=None,
    *,
    resolve_geometry_task_source_node,
    gn_packed_cache_state_prop,
    json_module,
):
    node = resolve_geometry_task_source_node(task_ref)
    if node is None:
        return False
    if frame_range is None:
        frame_range = (int(task_ref.get("frame_start", 1)), int(task_ref.get("frame_end", 1)))
    state = {
        "version": 1,
        "has_cache": True,
        "task_path": str(task_ref.get("task_path", "") or ""),
        "object_name": str(task_ref.get("object_name", "") or ""),
        "modifier_name": str(task_ref.get("modifier_name", "") or ""),
        "bake_node_name": str(task_ref.get("bake_node_name", "") or ""),
        "bake_id": int(task_ref.get("bake_id", 0) or 0),
        "bake_mode": str(task_ref.get("bake_mode", "") or ""),
        "use_custom_simulation_frame_range": bool(task_ref.get("use_custom_simulation_frame_range", False)),
        "frame_start": int(frame_range[0]),
        "frame_end": int(frame_range[1]),
    }
    node[gn_packed_cache_state_prop] = json_module.dumps(state, ensure_ascii=True)
    return True


def _clear_geometry_bake_tracked_packed_cache_state(
    task_ref,
    *,
    resolve_geometry_task_source_node,
    gn_packed_cache_state_prop,
):
    node = resolve_geometry_task_source_node(task_ref)
    if node is None:
        return False
    try:
        if gn_packed_cache_state_prop in node:
            del node[gn_packed_cache_state_prop]
            return True
    except Exception:
        return False
    return False


def _get_geometry_bake_tracked_packed_cache_status(
    task_ref,
    *,
    resolve_geometry_task_source_node,
    read_geometry_bake_tracked_packed_cache_state,
):
    node = resolve_geometry_task_source_node(task_ref)
    state = read_geometry_bake_tracked_packed_cache_state(node)
    if state is None:
        return None
    if str(state.get("task_path", "") or "") != str(task_ref.get("task_path", "") or ""):
        return None
    if str(state.get("object_name", "") or "") != str(task_ref.get("object_name", "") or ""):
        return None
    if str(state.get("modifier_name", "") or "") != str(task_ref.get("modifier_name", "") or ""):
        return None
    if str(state.get("bake_node_name", "") or "") != str(task_ref.get("bake_node_name", "") or ""):
        return None
    if int(state.get("bake_id", 0) or 0) != int(task_ref.get("bake_id", 0) or 0):
        return None
    if str(state.get("bake_mode", "") or "") != str(task_ref.get("bake_mode", "") or ""):
        return None
    return {
        "has_cache": True,
        "frame_range": (int(state["frame_start"]), int(state["frame_end"])),
        "source": "PACKED_TRACKED",
    }


def _capture_geometry_bake_entry_settings(bake_entry):
    state = {}
    for attr_name in (
        "bake_mode",
        "bake_target",
        "use_custom_path",
        "directory",
        "use_custom_simulation_frame_range",
        "frame_start",
        "frame_end",
    ):
        if hasattr(bake_entry, attr_name):
            state[attr_name] = getattr(bake_entry, attr_name)
    return state


def _apply_geometry_bake_entry_settings(bake_entry, task_ref):
    bake_target = str(task_ref.get("bake_target", "") or "")
    use_custom_path = bool(task_ref.get("use_custom_path", False)) if bake_target == "DISK" else False
    directory = str(task_ref.get("directory", "") or "") if bake_target == "DISK" else ""
    if hasattr(bake_entry, "bake_mode"):
        bake_entry.bake_mode = task_ref["bake_mode"]
    if hasattr(bake_entry, "bake_target"):
        bake_entry.bake_target = bake_target
    if hasattr(bake_entry, "use_custom_path"):
        bake_entry.use_custom_path = use_custom_path
    if hasattr(bake_entry, "directory"):
        bake_entry.directory = directory
    if hasattr(bake_entry, "use_custom_simulation_frame_range"):
        bake_entry.use_custom_simulation_frame_range = bool(task_ref["use_custom_simulation_frame_range"])
    if hasattr(bake_entry, "frame_start"):
        bake_entry.frame_start = int(task_ref["frame_start"])
    if hasattr(bake_entry, "frame_end"):
        bake_entry.frame_end = int(task_ref["frame_end"])


def _restore_geometry_bake_entry_settings(bake_entry, state):
    for attr_name, value in state.items():
        setattr(bake_entry, attr_name, value)


def _apply_temporary_geometry_bake_settings(
    task_ref,
    *,
    find_geometry_bake_entry_for_task,
    capture_geometry_bake_entry_settings,
    apply_geometry_bake_entry_settings,
):
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "applying temporary bake settings")
    original_state = capture_geometry_bake_entry_settings(bake_entry)
    apply_geometry_bake_entry_settings(bake_entry, task_ref)
    return bake_entry, original_state


def _apply_geometry_bake_settings_for_run(
    task_ref,
    *,
    find_geometry_bake_entry_for_task,
    apply_geometry_bake_entry_settings,
):
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "applying geometry bake run settings")
    apply_geometry_bake_entry_settings(bake_entry, task_ref)
    return bake_entry


def _geometry_bake_keep_overridden_settings_on_success(task_ref):
    return bool(task_ref.get("apply_settings_on_run", False))


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
