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


def _read_geometry_bake_last_bake_state(
    node,
    *,
    gn_last_bake_state_prop,
    json_module,
):
    if node is None:
        return None
    raw_value = node.get(gn_last_bake_state_prop)
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


def _write_geometry_bake_last_bake_state(
    task_ref,
    frame_range=None,
    *,
    resolve_geometry_task_source_node,
    resolve_geometry_task_effective_bake_target,
    gn_last_bake_state_prop,
    json_module,
):
    node = resolve_geometry_task_source_node(task_ref)
    if node is None:
        return False
    if frame_range is None:
        frame_range = (int(task_ref.get("frame_start", 1)), int(task_ref.get("frame_end", 1)))
    raw_bake_target = str(task_ref.get("bake_target", "") or "")
    try:
        bake_target = str(resolve_geometry_task_effective_bake_target(task_ref) or "")
    except Exception:
        bake_target = raw_bake_target
    if bake_target == "INHERIT":
        bake_target = raw_bake_target
    use_custom_path = bool(task_ref.get("use_custom_path", False))
    directory = str(task_ref.get("directory", "") or "")
    use_custom_range = bool(task_ref.get("use_custom_simulation_frame_range", False))
    frame_start_local = None
    frame_end_local = None
    if use_custom_range:
        try:
            frame_start_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Frame Start")
            if frame_start_socket is not None and not bool(getattr(frame_start_socket, "is_linked", False)):
                frame_start_local = int(getattr(frame_start_socket, "default_value", frame_range[0]) or frame_range[0])
        except Exception:
            frame_start_local = None
        try:
            frame_end_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Frame End")
            if frame_end_socket is not None and not bool(getattr(frame_end_socket, "is_linked", False)):
                frame_end_local = int(getattr(frame_end_socket, "default_value", frame_range[1]) or frame_range[1])
        except Exception:
            frame_end_local = None
    node_settings_state = {
        "task_path": str(task_ref.get("task_path", "") or ""),
        "bake_mode": str(task_ref.get("bake_mode", "") or ""),
        "bake_target": str(raw_bake_target or ""),
        "use_custom_path": bool(use_custom_path),
        "directory": str(directory or "") if use_custom_path else "",
        "use_custom_simulation_frame_range": bool(use_custom_range),
        "frame_start_local": frame_start_local,
        "frame_end_local": frame_end_local,
    }
    state = {
        "version": 2,
        "has_cache": True,
        "task_path": str(task_ref.get("task_path", "") or ""),
        "object_name": str(task_ref.get("object_name", "") or ""),
        "modifier_name": str(task_ref.get("modifier_name", "") or ""),
        "bake_node_name": str(task_ref.get("bake_node_name", "") or ""),
        "bake_id": int(task_ref.get("bake_id", 0) or 0),
        "bake_mode": str(task_ref.get("bake_mode", "") or ""),
        "bake_target": str(bake_target or ""),
        "node_bake_target": str(raw_bake_target or ""),
        "use_custom_path": bool(use_custom_path),
        "directory": str(directory or ""),
        "use_custom_simulation_frame_range": bool(use_custom_range),
        "frame_start": int(frame_range[0]),
        "frame_end": int(frame_range[1]),
        "node_settings_state": node_settings_state,
    }
    node[gn_last_bake_state_prop] = json_module.dumps(state, ensure_ascii=True)
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


def _clear_geometry_bake_last_bake_state(
    task_ref,
    *,
    resolve_geometry_task_source_node,
    gn_last_bake_state_prop,
):
    node = resolve_geometry_task_source_node(task_ref)
    if node is None:
        return False
    try:
        if gn_last_bake_state_prop in node:
            del node[gn_last_bake_state_prop]
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


def _get_geometry_bake_last_bake_state(
    task_ref,
    *,
    resolve_geometry_task_source_node,
    read_geometry_bake_last_bake_state,
):
    node = resolve_geometry_task_source_node(task_ref)
    state = read_geometry_bake_last_bake_state(node)
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
    return dict(state)


def _build_geometry_bake_release_task_ref(
    task_ref,
    *,
    get_geometry_bake_last_bake_state,
    get_geometry_bake_tracked_packed_cache_status,
):
    release_task_ref = dict(task_ref or {})
    last_bake_state = None
    if get_geometry_bake_last_bake_state is not None:
        last_bake_state = get_geometry_bake_last_bake_state(task_ref)
    last_bake_target = str((last_bake_state or {}).get("bake_target", "") or "").upper()
    if last_bake_target in {"PACKED", "DISK"}:
        release_task_ref["bake_mode"] = str(last_bake_state.get("bake_mode", release_task_ref.get("bake_mode", "")) or release_task_ref.get("bake_mode", ""))
        release_task_ref["bake_target"] = last_bake_target
        if last_bake_target == "DISK":
            release_task_ref["use_custom_path"] = bool(last_bake_state.get("use_custom_path", False))
            release_task_ref["directory"] = str(last_bake_state.get("directory", "") or "")
        else:
            release_task_ref["use_custom_path"] = False
            release_task_ref["directory"] = ""
        release_task_ref["use_custom_simulation_frame_range"] = bool(
            last_bake_state.get(
                "use_custom_simulation_frame_range",
                release_task_ref.get("use_custom_simulation_frame_range", False),
            )
        )
        release_task_ref["frame_start"] = int(
            last_bake_state.get("frame_start", release_task_ref.get("frame_start", 1))
            or release_task_ref.get("frame_start", 1)
        )
        release_task_ref["frame_end"] = int(
            last_bake_state.get("frame_end", release_task_ref.get("frame_end", 1))
            or release_task_ref.get("frame_end", 1)
        )
        release_task_ref["apply_settings_on_run"] = True
        return release_task_ref, True

    tracked_packed_status = None
    if get_geometry_bake_tracked_packed_cache_status is not None:
        tracked_packed_status = get_geometry_bake_tracked_packed_cache_status(task_ref)
    if tracked_packed_status is not None:
        release_task_ref["bake_target"] = "PACKED"
        release_task_ref["use_custom_path"] = False
        release_task_ref["directory"] = ""
        release_task_ref["apply_settings_on_run"] = True
        return release_task_ref, True

    return dict(task_ref or {}), False


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


def _apply_geometry_bake_runtime_disk_directory(bake_entry, task_ref, *, resolve_default_directory):
    task_bake_target = str(task_ref.get("bake_target", "") or "")
    effective_bake_target = task_bake_target
    if effective_bake_target == "INHERIT":
        try:
            effective_bake_target = str(getattr(bake_entry, "bake_target", "") or "")
        except Exception:
            effective_bake_target = ""
    if effective_bake_target != "DISK":
        return False
    use_custom_path = bool(task_ref.get("use_custom_path", False))
    directory = str(task_ref.get("directory", "") or "").strip()
    if not use_custom_path:
        directory = str(resolve_default_directory(task_ref) or "").strip()
    if not directory:
        return False
    updated = False
    if hasattr(bake_entry, "bake_target") and str(getattr(bake_entry, "bake_target", "") or "") != "DISK":
        bake_entry.bake_target = "DISK"
        updated = True
    if hasattr(bake_entry, "use_custom_path") and not bool(getattr(bake_entry, "use_custom_path", False)):
        bake_entry.use_custom_path = True
        updated = True
    if hasattr(bake_entry, "directory") and str(getattr(bake_entry, "directory", "") or "") != directory:
        bake_entry.directory = directory
        updated = True
    return updated


def _restore_geometry_bake_entry_settings(bake_entry, state):
    for attr_name, value in state.items():
        setattr(bake_entry, attr_name, value)


def _apply_temporary_geometry_bake_settings(
    task_ref,
    *,
    apply_full_settings=True,
    find_geometry_bake_entry_for_task,
    capture_geometry_bake_entry_settings,
    apply_geometry_bake_entry_settings,
    apply_geometry_bake_runtime_disk_directory,
    resolve_default_directory,
):
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "applying temporary bake settings")
    original_state = capture_geometry_bake_entry_settings(bake_entry)
    if bool(apply_full_settings):
        apply_geometry_bake_entry_settings(bake_entry, task_ref)
    apply_geometry_bake_runtime_disk_directory(
        bake_entry,
        task_ref,
        resolve_default_directory=resolve_default_directory,
    )
    return bake_entry, original_state


def _apply_current_geometry_bake_temporary_override(
    task_ref,
    *,
    apply_temporary_geometry_bake_settings,
    apply_temporary_geometry_bake_runtime_directory,
):
    if bool(task_ref.get("apply_settings_on_run", False)):
        return apply_temporary_geometry_bake_settings(task_ref)
    return apply_temporary_geometry_bake_runtime_directory(task_ref)


def _apply_geometry_bake_settings_for_run(
    task_ref,
    *,
    find_geometry_bake_entry_for_task,
    apply_geometry_bake_entry_settings,
    apply_geometry_bake_runtime_disk_directory,
    resolve_default_directory,
):
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "applying geometry bake run settings")
    apply_geometry_bake_entry_settings(bake_entry, task_ref)
    apply_geometry_bake_runtime_disk_directory(
        bake_entry,
        task_ref,
        resolve_default_directory=resolve_default_directory,
    )
    return bake_entry


def _clear_geometry_bake_recorded_cache_state(
    task_ref,
    *,
    clear_geometry_bake_tracked_packed_cache_state,
    clear_geometry_bake_last_bake_state,
):
    clear_geometry_bake_tracked_packed_cache_state(task_ref)
    clear_geometry_bake_last_bake_state(task_ref)


def _geometry_bake_keep_overridden_settings_on_success(task_ref):
    task_bake_target = str(task_ref.get("bake_target", "") or "")
    should_keep_runtime_disk_binding = task_bake_target in {"DISK", "INHERIT"}
    return bool(task_ref.get("apply_settings_on_run", False) or should_keep_runtime_disk_binding)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
