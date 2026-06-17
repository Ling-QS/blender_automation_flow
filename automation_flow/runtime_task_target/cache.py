import os

import bpy


def _point_cache_has_existing_cache(point_cache, *, bpy_module, os_module, re_module):
    if point_cache is None:
        return False
    try:
        if bool(getattr(point_cache, "is_baked", False)):
            return True
    except Exception:
        pass
    info_text = str(getattr(point_cache, "info", "") or "").strip()
    if info_text:
        match = re_module.search(r"(\d+)\s+frames?\b", info_text, flags=re_module.IGNORECASE)
        if match is not None:
            try:
                if int(match.group(1)) > 0:
                    return True
            except Exception:
                pass
    file_path = str(getattr(point_cache, "filepath", "") or "").strip()
    if file_path:
        try:
            resolved_path = bpy_module.path.abspath(file_path)
        except Exception:
            resolved_path = file_path
        if resolved_path and os_module.path.exists(resolved_path):
            return True
    return False


def _point_cache_frame_range(point_cache, *, point_cache_has_existing_cache):
    if point_cache is None:
        return None
    if not point_cache_has_existing_cache(point_cache):
        return None
    try:
        frame_start = int(getattr(point_cache, "frame_start", 0) or 0)
        frame_end = int(getattr(point_cache, "frame_end", 0) or 0)
    except Exception:
        return None
    if frame_start == 0 and frame_end == 0:
        return None
    return (min(frame_start, frame_end), max(frame_start, frame_end))


def _physics_bake_cache_status_from_node(
    node,
    *,
    flow_execution_error_cls,
    resolve_physics_task_target,
    point_cache_frame_range,
):
    if node is None or getattr(node, "bl_idname", "") != "AFNodePhysicsBakeSettings":
        return None
    try:
        object_ref, modifier = resolve_physics_task_target(getattr(node, "physics_task_path", ""), getattr(node, "name", ""))
    except flow_execution_error_cls as exc:
        return {
            "has_cache": False,
            "frame_range": None,
            "source": "",
            "invalid": True,
            "error_code": str(exc.code or ""),
            "error_message": str(exc.message or ""),
        }
    except Exception as exc:
        return {
            "has_cache": False,
            "frame_range": None,
            "source": "",
            "invalid": True,
            "error_code": "AF_E004",
            "error_message": str(exc or ""),
        }

    physics_type = str(getattr(modifier, "type", "") or "")
    if physics_type in {"CLOTH", "SOFT_BODY"}:
        frame_range = point_cache_frame_range(getattr(modifier, "point_cache", None))
        if frame_range is not None:
            return {"has_cache": True, "frame_range": frame_range, "source": "POINT_CACHE"}
        return {"has_cache": False, "frame_range": None, "source": ""}

    if physics_type == "DYNAMIC_PAINT":
        canvas_settings = getattr(modifier, "canvas_settings", None)
        if canvas_settings is None:
            return {"has_cache": False, "frame_range": None, "source": ""}
        collected_ranges = []
        for surface in getattr(canvas_settings, "canvas_surfaces", []):
            frame_range = point_cache_frame_range(getattr(surface, "point_cache", None))
            if frame_range is not None:
                collected_ranges.append(frame_range)
        if collected_ranges:
            return {
                "has_cache": True,
                "frame_range": (
                    min(int(item[0]) for item in collected_ranges),
                    max(int(item[1]) for item in collected_ranges),
                ),
                "source": "POINT_CACHE",
            }
        return {"has_cache": False, "frame_range": None, "source": ""}

    return {"has_cache": False, "frame_range": None, "source": ""}


def _physics_task_has_existing_cache(task_ref, *, point_cache_has_existing_cache):
    object_ref = task_ref.get("object_ref")
    modifier_name = str(task_ref.get("modifier_name", "") or "")
    physics_type = str(task_ref.get("physics_type", "") or "")
    if object_ref is None or not modifier_name:
        return False
    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        return False
    if physics_type in {"CLOTH", "SOFT_BODY"}:
        return point_cache_has_existing_cache(getattr(modifier, "point_cache", None))
    if physics_type == "DYNAMIC_PAINT":
        canvas_settings = getattr(modifier, "canvas_settings", None)
        if canvas_settings is None:
            return False
        for surface in getattr(canvas_settings, "canvas_surfaces", []):
            if point_cache_has_existing_cache(getattr(surface, "point_cache", None)):
                return True
        return False
    return False


def _physics_bake_all_has_pending_work(task_ref, *, physics_task_has_existing_cache):
    for item in list(task_ref.get("tasks", []) or []):
        if bool(item.get("free_before_bake", False)):
            return True
        if not physics_task_has_existing_cache(item):
            return True
    return False


def _geometry_bake_entry_has_cached_data(bake_entry):
    data_blocks = getattr(bake_entry, "data_blocks", None)
    if data_blocks is None:
        return False
    try:
        return len(data_blocks) > 0
    except Exception:
        return False


def _geometry_bake_disk_cache_root_dir(task_ref, bake_entry=None, *, bpy_module=bpy, require_payload_object_ref=None):
    if require_payload_object_ref is not None:
        object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    else:
        object_ref = task_ref.get("object_ref")
    if object_ref is None:
        return ""
    modifier = object_ref.modifiers.get(task_ref["modifier_name"])
    if modifier is None:
        return ""
    prefer_task_settings = bool(task_ref.get("_prefer_task_settings", False))
    if prefer_task_settings:
        effective_bake_target = str(task_ref.get("bake_target", "") or "")
        if effective_bake_target and effective_bake_target != "DISK":
            return ""
        use_custom_path = bool(task_ref.get("use_custom_path", False))
        directory = str(task_ref.get("directory", "") or "").strip()
        if use_custom_path and directory:
            try:
                return bpy_module.path.abspath(directory)
            except Exception:
                return directory
        return bpy_module.path.abspath(getattr(modifier, "bake_directory", "") or "")
    if bake_entry is not None:
        try:
            effective_bake_target = str(getattr(bake_entry, "bake_target", "") or "")
        except Exception:
            effective_bake_target = ""
        if effective_bake_target and effective_bake_target != "DISK":
            return ""
        try:
            use_custom_path = bool(getattr(bake_entry, "use_custom_path", False))
        except Exception:
            use_custom_path = False
        directory = str(getattr(bake_entry, "directory", "") or "").strip()
    else:
        use_custom_path = bool(task_ref.get("use_custom_path", False))
        directory = str(task_ref.get("directory", "") or "").strip()
    if use_custom_path and directory:
        try:
            return bpy_module.path.abspath(directory)
        except Exception:
            return directory
    return bpy_module.path.abspath(getattr(modifier, "bake_directory", "") or "")


def _iter_geometry_bake_disk_cache_candidate_roots(task_ref, bake_entry=None, *, geometry_bake_disk_cache_root_dir=_geometry_bake_disk_cache_root_dir):
    root_dir = geometry_bake_disk_cache_root_dir(task_ref, bake_entry=bake_entry)
    if not root_dir or not os.path.isdir(root_dir):
        return []

    bake_id = str(int(task_ref["bake_id"]))
    ordered_roots = []
    seen_paths = set()

    def _append_candidate(path):
        if not path:
            return
        normalized = os.path.normcase(os.path.normpath(path))
        if normalized in seen_paths:
            return
        seen_paths.add(normalized)
        ordered_roots.append(path)

    _append_candidate(root_dir)
    if os.path.basename(os.path.normpath(root_dir)) != bake_id:
        _append_candidate(os.path.join(root_dir, bake_id))
    return ordered_roots


def _geometry_bake_cached_frame_from_filename(filename):
    stem, _ext = os.path.splitext(str(filename or ""))
    if not stem:
        return None
    frame_token = stem.split("_", 1)[0].strip()
    if not frame_token:
        return None
    try:
        return int(frame_token)
    except Exception:
        return None


def _geometry_bake_cached_frame_range_from_candidate_root(candidate_root):
    if not candidate_root or not os.path.isdir(candidate_root):
        return None

    frame_numbers = set()
    for subdir_name in ("meta", "blobs"):
        subdir_path = os.path.join(candidate_root, subdir_name)
        if not os.path.isdir(subdir_path):
            continue
        try:
            with os.scandir(subdir_path) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    frame_number = _geometry_bake_cached_frame_from_filename(entry.name)
                    if frame_number is None:
                        continue
                    frame_numbers.add(int(frame_number))
        except Exception:
            continue

    if not frame_numbers:
        return None
    return min(frame_numbers), max(frame_numbers)


def _geometry_bake_disk_cache_frame_range(task_ref, bake_entry=None):
    for candidate_root in _iter_geometry_bake_disk_cache_candidate_roots(task_ref, bake_entry=bake_entry):
        frame_range = _geometry_bake_cached_frame_range_from_candidate_root(candidate_root)
        if frame_range is not None:
            return frame_range
    return None


def _geometry_bake_entry_cached_frame_range(bake_entry):
    data_blocks = getattr(bake_entry, "data_blocks", None)
    if data_blocks is None:
        return None

    frame_numbers = set()
    try:
        iterable_blocks = list(data_blocks)
    except Exception:
        iterable_blocks = []

    for data_block in iterable_blocks:
        for attr_name in ("frame", "frame_number", "simulation_frame"):
            if not hasattr(data_block, attr_name):
                continue
            try:
                frame_numbers.add(int(getattr(data_block, attr_name)))
                break
            except Exception:
                continue
        else:
            frame_number = _geometry_bake_cached_frame_from_filename(getattr(data_block, "name", ""))
            if frame_number is not None:
                frame_numbers.add(int(frame_number))

    if frame_numbers:
        return min(frame_numbers), max(frame_numbers)

    try:
        if len(iterable_blocks) > 0 and hasattr(bake_entry, "frame_start") and hasattr(bake_entry, "frame_end"):
            frame_start = int(getattr(bake_entry, "frame_start"))
            frame_end = int(getattr(bake_entry, "frame_end"))
            return min(frame_start, frame_end), max(frame_start, frame_end)
    except Exception:
        pass
    return None


def _geometry_bake_cache_status_from_node(
    node,
    *,
    bpy_module,
    flow_execution_error_cls,
    resolve_bake_target,
    build_geometry_task_ref,
    geometry_bake_disk_cache_frame_range,
    geometry_bake_entry_has_cached_data,
    geometry_bake_entry_cached_frame_range,
    get_geometry_bake_tracked_packed_cache_status,
    geometry_bake_disk_cache_exists,
):
    if node is None or getattr(node, "bl_idname", "") != "AFNodeBakeTask":
        return None
    try:
        object_ref, modifier, bake_node, bake_entry = resolve_bake_target(getattr(node, "bake_task_path", ""), getattr(node, "name", ""))
    except flow_execution_error_cls as exc:
        return {
            "has_cache": False,
            "frame_range": None,
            "source": "",
            "invalid": True,
            "error_code": str(exc.code or ""),
            "error_message": str(exc.message or ""),
        }
    except Exception as exc:
        return {
            "has_cache": False,
            "frame_range": None,
            "source": "",
            "invalid": True,
            "error_code": "AF_E004",
            "error_message": str(exc or ""),
        }

    scene = getattr(bpy_module.context, "scene", None)
    try:
        runner_tree = getattr(node, "id_data", None)
        if scene is not None and runner_tree is not None:
            task_ref = build_geometry_task_ref(runner_tree, scene, node)
        else:
            task_ref = {
                "source_node": str(getattr(node, "name", "") or ""),
                "source_tree_name": str(getattr(getattr(node, "id_data", None), "name", "") or ""),
                "object_ref": object_ref,
                "object_name": object_ref.name,
                "modifier_name": modifier.name,
                "bake_node_name": getattr(bake_node, "name", ""),
                "bake_id": int(getattr(bake_entry, "bake_id", 0)),
                "bake_target": str(getattr(node, "bake_target", "") or ""),
                "bake_mode": str(getattr(node, "bake_mode", "") or ""),
                "task_path": str(getattr(node, "bake_task_path", "") or ""),
                "use_custom_path": bool(getattr(node, "use_custom_path", False)),
                "directory": str(getattr(node, "directory", "") or ""),
                "use_custom_simulation_frame_range": bool(getattr(node, "use_custom_simulation_frame_range", False)),
                "frame_start": int(getattr(node.inputs.get("Frame Start"), "default_value", 1) or 1),
                "frame_end": int(getattr(node.inputs.get("Frame End"), "default_value", 250) or 250),
                "apply_settings_on_run": bool(getattr(node, "apply_settings_on_run", False)),
            }
    except Exception:
        task_ref = {
            "source_node": str(getattr(node, "name", "") or ""),
            "source_tree_name": str(getattr(getattr(node, "id_data", None), "name", "") or ""),
            "object_ref": object_ref,
            "object_name": object_ref.name,
            "modifier_name": modifier.name,
            "bake_node_name": getattr(bake_node, "name", ""),
            "bake_id": int(getattr(bake_entry, "bake_id", 0)),
            "bake_target": str(getattr(node, "bake_target", "") or ""),
            "bake_mode": str(getattr(node, "bake_mode", "") or ""),
            "task_path": str(getattr(node, "bake_task_path", "") or ""),
            "use_custom_path": bool(getattr(node, "use_custom_path", False)),
            "directory": str(getattr(node, "directory", "") or ""),
            "use_custom_simulation_frame_range": bool(getattr(node, "use_custom_simulation_frame_range", False)),
            "frame_start": int(getattr(node.inputs.get("Frame Start"), "default_value", 1) or 1),
            "frame_end": int(getattr(node.inputs.get("Frame End"), "default_value", 250) or 250),
            "apply_settings_on_run": bool(getattr(node, "apply_settings_on_run", False)),
        }

    task_ref = dict(task_ref or {})
    task_settings_ref = dict(task_ref)
    actual_entry_ref = dict(task_ref)
    actual_entry_ref.pop("_prefer_task_settings", None)
    if bool(task_ref.get("apply_settings_on_run", False)):
        task_settings_ref["_prefer_task_settings"] = True

    disk_frame_range = geometry_bake_disk_cache_frame_range(task_settings_ref, bake_entry=bake_entry)
    if disk_frame_range is not None:
        return {
            "has_cache": True,
            "frame_range": (int(disk_frame_range[0]), int(disk_frame_range[1])),
            "source": "DISK",
        }

    if geometry_bake_entry_has_cached_data(bake_entry):
        memory_frame_range = geometry_bake_entry_cached_frame_range(bake_entry)
        return {
            "has_cache": True,
            "frame_range": (
                (int(memory_frame_range[0]), int(memory_frame_range[1]))
                if memory_frame_range is not None
                else None
            ),
            "source": "MEMORY",
        }

    tracked_packed_status = get_geometry_bake_tracked_packed_cache_status(task_settings_ref)
    if tracked_packed_status is not None:
        return tracked_packed_status

    actual_disk_frame_range = geometry_bake_disk_cache_frame_range(actual_entry_ref, bake_entry=bake_entry)
    if actual_disk_frame_range is not None:
        return {
            "has_cache": True,
            "frame_range": (int(actual_disk_frame_range[0]), int(actual_disk_frame_range[1])),
            "source": "DISK",
        }

    if geometry_bake_disk_cache_exists(task_settings_ref, bake_entry=bake_entry):
        return {
            "has_cache": True,
            "frame_range": None,
            "source": "DISK",
        }

    if geometry_bake_disk_cache_exists(actual_entry_ref, bake_entry=bake_entry):
        return {
            "has_cache": True,
            "frame_range": None,
            "source": "DISK",
        }

    return {
        "has_cache": False,
        "frame_range": None,
        "source": "",
    }


def _geometry_bake_disk_cache_exists(task_ref, bake_entry=None, *, geometry_bake_disk_cache_candidate_roots=_iter_geometry_bake_disk_cache_candidate_roots):
    def _dir_has_files(path):
        if not path or not os.path.isdir(path):
            return False
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file():
                        return True
        except Exception:
            return False
        return False

    def _candidate_has_cache(candidate_root):
        if not candidate_root or not os.path.isdir(candidate_root):
            return False
        blobs_dir = os.path.join(candidate_root, "blobs")
        meta_dir = os.path.join(candidate_root, "meta")
        return _dir_has_files(blobs_dir) or _dir_has_files(meta_dir)

    for candidate_root in geometry_bake_disk_cache_candidate_roots(task_ref, bake_entry=bake_entry):
        if _candidate_has_cache(candidate_root):
            return True
    return False


def _geometry_bake_has_existing_cache(task_ref, scene, bake_entry, *, geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data, get_geometry_bake_tracked_packed_cache_status=None, geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists):
    del scene
    if geometry_bake_entry_has_cached_data(bake_entry):
        return True
    if get_geometry_bake_tracked_packed_cache_status is not None and get_geometry_bake_tracked_packed_cache_status(task_ref) is not None:
        return True
    if geometry_bake_disk_cache_exists(task_ref, bake_entry=bake_entry):
        return True
    return False


def _geometry_bake_has_existing_cache_for_current_entry(task_ref, scene, bake_entry, *, geometry_bake_entry_has_cached_data=_geometry_bake_entry_has_cached_data, geometry_bake_disk_cache_exists=_geometry_bake_disk_cache_exists):
    del scene
    current_entry_ref = dict(task_ref or {})
    current_entry_ref.pop("_prefer_task_settings", None)
    if geometry_bake_entry_has_cached_data(bake_entry):
        return True
    if geometry_bake_disk_cache_exists(current_entry_ref, bake_entry=bake_entry):
        return True
    return False


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
