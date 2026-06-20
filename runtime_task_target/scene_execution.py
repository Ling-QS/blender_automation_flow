import os
import shutil
import tempfile


def _physics_disk_cache_enabled(task_ref):
    return bool(task_ref.get("disk_cache", False) or task_ref.get("_force_disk_cache", False))


def _capture_point_cache_disk_cache_state(point_cache):
    if point_cache is None or not hasattr(point_cache, "use_disk_cache"):
        return None
    try:
        return bool(point_cache.use_disk_cache)
    except Exception:
        return None


def _apply_point_cache_disk_cache(point_cache, enabled):
    if point_cache is None or not hasattr(point_cache, "use_disk_cache"):
        return
    try:
        point_cache.use_disk_cache = bool(enabled)
    except Exception:
        pass


def _copy_directory_contents(source_path, destination_path, *, shutil_module, os_module):
    if not source_path or not destination_path:
        return 0
    if not os_module.path.isdir(source_path):
        return 0
    os_module.makedirs(destination_path, exist_ok=True)
    copied = 0
    try:
        entries = list(os_module.scandir(source_path))
    except Exception:
        entries = []
    for entry in entries:
        child_source = entry.path
        child_destination = os_module.path.join(destination_path, entry.name)
        try:
            if entry.is_dir():
                copied += _copy_directory_contents(
                    child_source,
                    child_destination,
                    shutil_module=shutil_module,
                    os_module=os_module,
                )
            else:
                parent = os_module.path.dirname(child_destination)
                if parent:
                    os_module.makedirs(parent, exist_ok=True)
                shutil_module.copy2(child_source, child_destination)
                copied += 1
        except Exception:
            continue
    return copied


def _directory_file_signature(path, *, os_module):
    if not path or not os_module.path.isdir(path):
        return ()
    rows = []
    try:
        for root, _dirs, files in os_module.walk(path):
            for name in sorted(files):
                full_path = os_module.path.join(root, name)
                rel_path = os_module.path.relpath(full_path, path)
                try:
                    size = int(os_module.path.getsize(full_path))
                except Exception:
                    size = -1
                rows.append((str(rel_path).replace("\\", "/"), size))
    except Exception:
        return ()
    rows.sort()
    return tuple(rows)


def _clear_directory_contents(path, *, shutil_module, os_module):
    if not path or not os_module.path.isdir(path):
        return
    try:
        entries = list(os_module.scandir(path))
    except Exception:
        entries = []
    for entry in entries:
        try:
            if entry.is_dir():
                shutil_module.rmtree(entry.path, ignore_errors=True)
            else:
                os_module.remove(entry.path)
        except Exception:
            continue


def _physics_disk_cache_root_dir_for_current_blend(*, bpy_module, os_module):
    blend_filepath = str(getattr(getattr(bpy_module, "data", None), "filepath", "") or "").strip()
    if not blend_filepath:
        return ""
    blend_directory = os_module.path.dirname(blend_filepath)
    blend_stem = os_module.path.splitext(os_module.path.basename(blend_filepath))[0].strip()
    if not blend_directory or not blend_stem:
        return ""
    return os_module.path.join(blend_directory, f"blendcache_{blend_stem}")


def _physics_operator_result_is_finished(result):
    if isinstance(result, str):
        return str(result).strip().upper() == "FINISHED"
    if isinstance(result, (set, tuple, list)):
        return any(str(item).strip().upper() == "FINISHED" for item in result)
    return False


def _register_point_cache_from_disk(
    point_cache,
    base_override,
    ui_context=None,
    *,
    bpy_module,
    compose_bake_override,
):
    if point_cache is None:
        return False
    override = compose_bake_override({**base_override, "point_cache": point_cache}, ui_context)
    try:
        with bpy_module.context.temp_override(**override):
            if not bpy_module.ops.ptcache.bake_from_cache.poll():
                return False
            result = bpy_module.ops.ptcache.bake_from_cache()
    except Exception:
        return False
    return _physics_operator_result_is_finished(result)


def _register_returned_physics_disk_cache(
    task_ref,
    scene,
    ui_context=None,
    *,
    bpy_module,
    require_payload_object_ref,
    compose_bake_override,
    capture_scene_frame_state,
    restore_scene_frame_state,
):
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "physics bake"))
    modifier_name = task_ref["modifier_name"]
    physics_type = str(task_ref.get("physics_type", "") or "")
    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        return {"registered": 0, "attempted": 0, "reason": "missing_modifier"}
    original_scene_state = capture_scene_frame_state(scene) if scene is not None else None

    base_override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
    }

    if bool(task_ref.get("override_settings", True)):
        try:
            scene.frame_start = int(task_ref["frame_start"])
            scene.frame_end = int(task_ref["frame_end"])
            scene.frame_set(scene.frame_start)
        except Exception:
            pass

    cache_root_dir = _physics_disk_cache_root_dir_for_current_blend(bpy_module=bpy_module, os_module=os)
    backup_cache_dir = ""
    backed_up_files = 0
    original_cache_signature = ()
    if cache_root_dir and os.path.isdir(cache_root_dir):
        try:
            original_cache_signature = _directory_file_signature(cache_root_dir, os_module=os)
            backup_cache_dir = tempfile.mkdtemp(prefix="af_physics_cache_restore_")
            backed_up_files = _copy_directory_contents(
                cache_root_dir,
                backup_cache_dir,
                shutil_module=shutil,
                os_module=os,
            )
        except Exception:
            backup_cache_dir = ""
            backed_up_files = 0

    def _finalize_report(payload):
        report = dict(payload or {})
        report["backed_up_cache_files"] = int(backed_up_files or 0)
        report["restored_cache_files"] = 0
        report["cache_files_changed_during_registration"] = False
        if int(report.get("registered", 0) or 0) > 0:
            report["mainfile_reload_required"] = True
            report["mainfile_reload_reason"] = "physics_disk_cache_runtime_metadata"
        if backup_cache_dir:
            try:
                current_cache_signature = _directory_file_signature(cache_root_dir, os_module=os) if cache_root_dir else ()
                cache_changed = tuple(current_cache_signature) != tuple(original_cache_signature)
                report["cache_files_changed_during_registration"] = bool(cache_changed)
                if cache_changed and backed_up_files > 0 and cache_root_dir:
                    os.makedirs(cache_root_dir, exist_ok=True)
                    _clear_directory_contents(cache_root_dir, shutil_module=shutil, os_module=os)
                    report["restored_cache_files"] = int(
                        _copy_directory_contents(
                            backup_cache_dir,
                            cache_root_dir,
                            shutil_module=shutil,
                            os_module=os,
                        )
                        or 0
                    )
            finally:
                try:
                    shutil.rmtree(backup_cache_dir, ignore_errors=True)
                except Exception:
                    pass
        return report

    try:
        if physics_type in {"CLOTH", "SOFT_BODY"}:
            point_cache = getattr(modifier, "point_cache", None)
            if point_cache is None:
                return _finalize_report({"registered": 0, "attempted": 0, "reason": "missing_point_cache"})
            if bool(task_ref.get("override_settings", True)):
                try:
                    point_cache.frame_start = int(task_ref["frame_start"])
                    point_cache.frame_end = int(task_ref["frame_end"])
                except Exception:
                    pass
            _apply_point_cache_disk_cache(point_cache, True)
            registered = _register_point_cache_from_disk(
                point_cache,
                base_override,
                ui_context=ui_context,
                bpy_module=bpy_module,
                compose_bake_override=compose_bake_override,
            )
            return _finalize_report({
                "registered": 1 if registered else 0,
                "attempted": 1,
                "physics_type": physics_type,
            })

        if physics_type == "DYNAMIC_PAINT":
            canvas_settings = getattr(modifier, "canvas_settings", None)
            if canvas_settings is None:
                return _finalize_report({"registered": 0, "attempted": 0, "reason": "missing_canvas_settings"})
            registered = 0
            attempted = 0
            for surface in getattr(canvas_settings, "canvas_surfaces", []):
                point_cache = getattr(surface, "point_cache", None)
                if point_cache is None:
                    continue
                attempted += 1
                if bool(task_ref.get("override_settings", True)):
                    try:
                        surface.frame_start = int(task_ref["frame_start"])
                        surface.frame_end = int(task_ref["frame_end"])
                    except Exception:
                        pass
                _apply_point_cache_disk_cache(point_cache, True)
                if _register_point_cache_from_disk(
                    point_cache,
                    base_override,
                    ui_context=ui_context,
                    bpy_module=bpy_module,
                    compose_bake_override=compose_bake_override,
                ):
                    registered += 1
            return _finalize_report({
                "registered": int(registered),
                "attempted": int(attempted),
                "physics_type": physics_type,
            })

        return _finalize_report({"registered": 0, "attempted": 0, "reason": "unsupported_physics_type", "physics_type": physics_type})
    finally:
        restore_scene_frame_state(scene, original_scene_state)


def _register_returned_physics_bake_all_disk_cache(
    task_ref,
    scene,
    ui_context=None,
    *,
    bpy_module,
    require_payload_object_ref,
    compose_bake_override,
    capture_scene_frame_state,
    restore_scene_frame_state,
):
    registered = 0
    attempted = 0
    backed_up_cache_files = 0
    restored_cache_files = 0
    cache_files_changed_during_registration = False
    mainfile_reload_required = False
    mainfile_reload_reason = ""
    reasons = []
    errors = []
    for item in list(task_ref.get("tasks", []) or []):
        if not isinstance(item, dict):
            continue
        report = _register_returned_physics_disk_cache(
            item,
            scene,
            ui_context=ui_context,
            bpy_module=bpy_module,
            require_payload_object_ref=require_payload_object_ref,
            compose_bake_override=compose_bake_override,
            capture_scene_frame_state=capture_scene_frame_state,
            restore_scene_frame_state=restore_scene_frame_state,
        )
        registered += int(report.get("registered", 0) or 0)
        attempted += int(report.get("attempted", 0) or 0)
        backed_up_cache_files += int(report.get("backed_up_cache_files", 0) or 0)
        restored_cache_files += int(report.get("restored_cache_files", 0) or 0)
        if bool(report.get("cache_files_changed_during_registration", False)):
            cache_files_changed_during_registration = True
        if bool(report.get("mainfile_reload_required", False)):
            mainfile_reload_required = True
            if not mainfile_reload_reason:
                mainfile_reload_reason = str(report.get("mainfile_reload_reason", "") or "")
        reason = str(report.get("reason", "") or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)
        error = str(report.get("error", "") or "").strip()
        if error and error not in errors:
            errors.append(error)
    merged_report = {
        "registered": int(registered),
        "attempted": int(attempted),
        "backed_up_cache_files": int(backed_up_cache_files),
        "restored_cache_files": int(restored_cache_files),
        "cache_files_changed_during_registration": bool(cache_files_changed_during_registration),
        "mainfile_reload_required": bool(mainfile_reload_required),
        "mainfile_reload_reason": str(mainfile_reload_reason or ""),
    }
    if reasons:
        merged_report["reason"] = "; ".join(reasons)
    if errors:
        merged_report["error"] = "; ".join(errors)
    return merged_report


def _resolve_physics_modifier_for_task(
    task_ref,
    error_context,
    *,
    flow_execution_error_cls,
    require_payload_object_ref,
):
    node_name = str(task_ref.get("source_node", "") or error_context)
    object_ref = require_payload_object_ref(task_ref, node_name)
    modifier_name = task_ref["modifier_name"]
    physics_type = task_ref["physics_type"]
    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing during {error_context}", node_name)
    if modifier.type != physics_type:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' changed type during {error_context}", node_name)
    return object_ref, modifier, physics_type


def _build_physics_bake_base_override(object_ref, scene, ui_context=None, *, bpy_module):
    return {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
    }


def _start_physics_bake_task(
    task_ref,
    scene,
    ui_context=None,
    *,
    bpy_module,
    flow_execution_error_cls,
    require_payload_object_ref,
    capture_scene_frame_state,
    physics_task_has_existing_cache,
    compose_bake_override,
    start_named_operator,
    restore_waiting_bake_cleanup,
    bake_job_type,
    task_kind_physics,
):
    object_ref, modifier, physics_type = _resolve_physics_modifier_for_task(
        task_ref,
        "execute",
        flow_execution_error_cls=flow_execution_error_cls,
        require_payload_object_ref=require_payload_object_ref,
    )
    base_override = _build_physics_bake_base_override(
        object_ref,
        scene,
        ui_context=ui_context,
        bpy_module=bpy_module,
    )
    wait_state = {
        "job_type": bake_job_type,
        "cleanup": {
            "kind": task_kind_physics,
            "scene": scene,
            "scene_state": capture_scene_frame_state(scene),
            "modifier": modifier,
            "original_cache_range": None,
            "original_surface_ranges": None,
            "original_disk_cache": None,
            "original_surface_disk_cache": None,
            "keep_overridden_range_on_success": bool(task_ref.get("override_settings", True)),
            "keep_overridden_disk_cache_on_success": _physics_disk_cache_enabled(task_ref),
        },
    }
    try:
        if not bool(task_ref.get("free_before_bake", False)) and physics_task_has_existing_cache(task_ref):
            return {"completed": True, "operator_result": "SKIPPED", "wait_state": wait_state}
        if bool(task_ref.get("override_settings", True)):
            scene.frame_start = int(task_ref["frame_start"])
            scene.frame_end = int(task_ref["frame_end"])
            scene.frame_set(scene.frame_start)
        if physics_type in {"CLOTH", "SOFT_BODY"}:
            wait_state["cleanup"]["original_cache_range"] = (
                int(modifier.point_cache.frame_start),
                int(modifier.point_cache.frame_end),
            )
            wait_state["cleanup"]["original_disk_cache"] = _capture_point_cache_disk_cache_state(getattr(modifier, "point_cache", None))
            if bool(task_ref.get("override_settings", True)):
                modifier.point_cache.frame_start = int(task_ref["frame_start"])
                modifier.point_cache.frame_end = int(task_ref["frame_end"])
            if _physics_disk_cache_enabled(task_ref):
                _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), True)
            override = compose_bake_override(
                {**base_override, "point_cache": modifier.point_cache},
                ui_context,
            )
            with bpy_module.context.temp_override(**override):
                if task_ref["free_before_bake"] and bpy_module.ops.ptcache.free_bake.poll():
                    bpy_module.ops.ptcache.free_bake()
            _op_path, result, _tokens = start_named_operator(
                ("ptcache.bake",),
                override,
                {"bake": True},
                task_ref["source_node"],
                invoke_async=True,
            )
            return {
                "completed": False,
                "operator_path": "bpy.ops.ptcache.bake",
                "operator_result": str(result),
                "wait_state": wait_state,
            }
        if physics_type == "DYNAMIC_PAINT":
            original_surface_ranges = []
            original_surface_disk_cache = []
            canvas_settings = modifier.canvas_settings
            if bool(task_ref.get("override_settings", True)):
                for surface in canvas_settings.canvas_surfaces:
                    original_surface_ranges.append((surface, int(surface.frame_start), int(surface.frame_end)))
                    surface.frame_start = int(task_ref["frame_start"])
                    surface.frame_end = int(task_ref["frame_end"])
            if _physics_disk_cache_enabled(task_ref):
                for surface in canvas_settings.canvas_surfaces:
                    point_cache = getattr(surface, "point_cache", None)
                    original_surface_disk_cache.append((surface, _capture_point_cache_disk_cache_state(point_cache)))
                    _apply_point_cache_disk_cache(point_cache, True)
            wait_state["cleanup"]["original_surface_ranges"] = original_surface_ranges
            wait_state["cleanup"]["original_surface_disk_cache"] = original_surface_disk_cache
            override = compose_bake_override(base_override, ui_context)
            _op_path, result, _tokens = start_named_operator(
                ("dpaint.bake",),
                override,
                {},
                task_ref["source_node"],
                invoke_async=True,
            )
            return {
                "completed": False,
                "operator_path": "bpy.ops.dpaint.bake",
                "operator_result": str(result),
                "wait_state": wait_state,
            }
        raise flow_execution_error_cls("AF_E005", f"Unsupported physics type '{physics_type}'", task_ref["source_node"])
    except Exception:
        restore_waiting_bake_cleanup(wait_state, bake_completed=False)
        raise


def _start_physics_bake_all_task(
    task_ref,
    scene,
    ui_context=None,
    *,
    bpy_module,
    flow_execution_error_cls,
    require_payload_object_ref,
    capture_scene_frame_state,
    physics_bake_all_has_pending_work,
    compose_bake_override,
    start_named_operator,
    restore_waiting_bake_cleanup,
    bake_job_type,
    task_kind_physics_bake_all,
):
    wait_state = {
        "job_type": bake_job_type,
        "cleanup": {
            "kind": task_kind_physics_bake_all,
            "scene": scene,
            "scene_state": capture_scene_frame_state(scene),
            "original_ranges": [],
            "original_disk_cache": [],
            "keep_overridden_range_on_success": bool(task_ref.get("override_settings", True)),
            "keep_overridden_disk_cache_on_success": any(_physics_disk_cache_enabled(item) for item in list(task_ref.get("tasks", []) or [])),
        },
    }
    try:
        if not physics_bake_all_has_pending_work(task_ref):
            return {"completed": True, "operator_result": "SKIPPED", "wait_state": wait_state}
        for item in task_ref["tasks"]:
            object_ref, modifier, _physics_type = _resolve_physics_modifier_for_task(
                item,
                "execute",
                flow_execution_error_cls=flow_execution_error_cls,
                require_payload_object_ref=require_payload_object_ref,
            )
            if bool(item.get("override_settings", True)):
                wait_state["cleanup"]["original_ranges"].append(
                    (
                        modifier,
                        int(modifier.point_cache.frame_start),
                        int(modifier.point_cache.frame_end),
                    )
                )
                modifier.point_cache.frame_start = int(item["frame_start"])
                modifier.point_cache.frame_end = int(item["frame_end"])
            if _physics_disk_cache_enabled(item):
                wait_state["cleanup"]["original_disk_cache"].append(
                    (
                        modifier,
                        _capture_point_cache_disk_cache_state(getattr(modifier, "point_cache", None)),
                    )
                )
                _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), True)
            if item["free_before_bake"]:
                override = compose_bake_override(
                    {
                        **_build_physics_bake_base_override(
                            object_ref,
                            scene,
                            ui_context=ui_context,
                            bpy_module=bpy_module,
                        ),
                        "point_cache": modifier.point_cache,
                    },
                    ui_context,
                )
                with bpy_module.context.temp_override(**override):
                    if bpy_module.ops.ptcache.free_bake.poll():
                        bpy_module.ops.ptcache.free_bake()
        if bool(task_ref.get("override_settings", True)):
            scene.frame_start = int(task_ref["scene_frame_start"])
            scene.frame_end = int(task_ref["scene_frame_end"])
            scene.frame_set(scene.frame_start)
        override = compose_bake_override(
            {
                "scene": scene,
                "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
            },
            ui_context,
        )
        _op_path, result, _tokens = start_named_operator(
            ("ptcache.bake_all",),
            override,
            {"bake": True},
            task_ref["source_node"],
            invoke_async=True,
        )
    except Exception:
        restore_waiting_bake_cleanup(wait_state, bake_completed=False)
        raise
    return {
        "completed": False,
        "operator_path": "bpy.ops.ptcache.bake_all",
        "operator_result": str(result),
        "wait_state": wait_state,
    }


def _invoke_physics_bake_task(
    task_ref,
    scene,
    *,
    bpy_module,
    flow_execution_error_cls,
    require_payload_object_ref,
    capture_scene_frame_state,
    physics_task_has_existing_cache,
    start_named_operator,
    ensure_operator_finished,
    restore_scene_frame_state,
):
    object_ref, modifier, physics_type = _resolve_physics_modifier_for_task(
        task_ref,
        "execute",
        flow_execution_error_cls=flow_execution_error_cls,
        require_payload_object_ref=require_payload_object_ref,
    )
    override = _build_physics_bake_base_override(
        object_ref,
        scene,
        bpy_module=bpy_module,
    )
    original_scene_state = capture_scene_frame_state(scene)
    original_cache_range = None
    original_surface_ranges = None
    original_disk_cache = None
    original_surface_disk_cache = None
    bake_succeeded = False
    try:
        if not bool(task_ref.get("free_before_bake", False)) and physics_task_has_existing_cache(task_ref):
            return {"FINISHED", "SKIPPED"}
        if bool(task_ref.get("override_settings", True)):
            scene.frame_start = int(task_ref["frame_start"])
            scene.frame_end = int(task_ref["frame_end"])
            scene.frame_set(scene.frame_start)
        if physics_type in {"CLOTH", "SOFT_BODY"}:
            original_cache_range = (int(modifier.point_cache.frame_start), int(modifier.point_cache.frame_end))
            original_disk_cache = _capture_point_cache_disk_cache_state(getattr(modifier, "point_cache", None))
            if bool(task_ref.get("override_settings", True)):
                modifier.point_cache.frame_start = int(task_ref["frame_start"])
                modifier.point_cache.frame_end = int(task_ref["frame_end"])
            if _physics_disk_cache_enabled(task_ref):
                _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), True)
            override["point_cache"] = modifier.point_cache
            with bpy_module.context.temp_override(**override):
                if task_ref["free_before_bake"] and bpy_module.ops.ptcache.free_bake.poll():
                    bpy_module.ops.ptcache.free_bake()
            _op_path, result, _tokens = start_named_operator(
                ("ptcache.bake",),
                override,
                {"bake": True},
                task_ref["source_node"],
                invoke_async=False,
            )
            bake_succeeded = True
            return ensure_operator_finished(result, "AF_E005", "bpy.ops.ptcache.bake", task_ref["source_node"])
        if physics_type == "DYNAMIC_PAINT":
            canvas_settings = modifier.canvas_settings
            original_surface_ranges = []
            original_surface_disk_cache = []
            if bool(task_ref.get("override_settings", True)):
                for surface in canvas_settings.canvas_surfaces:
                    original_surface_ranges.append((surface, int(surface.frame_start), int(surface.frame_end)))
                    surface.frame_start = int(task_ref["frame_start"])
                    surface.frame_end = int(task_ref["frame_end"])
            if _physics_disk_cache_enabled(task_ref):
                for surface in canvas_settings.canvas_surfaces:
                    point_cache = getattr(surface, "point_cache", None)
                    original_surface_disk_cache.append((surface, _capture_point_cache_disk_cache_state(point_cache)))
                    _apply_point_cache_disk_cache(point_cache, True)
            _op_path, result, _tokens = start_named_operator(
                ("dpaint.bake",),
                override,
                {},
                task_ref["source_node"],
                invoke_async=False,
            )
            bake_succeeded = True
            return ensure_operator_finished(result, "AF_E005", "bpy.ops.dpaint.bake", task_ref["source_node"])
        raise flow_execution_error_cls("AF_E005", f"Unsupported physics type '{physics_type}'", task_ref["source_node"])
    finally:
        keep_overridden_range = bake_succeeded and bool(task_ref.get("override_settings", True))
        keep_overridden_disk_cache = bake_succeeded and _physics_disk_cache_enabled(task_ref)
        if original_cache_range is not None and not keep_overridden_range:
            modifier.point_cache.frame_start = original_cache_range[0]
            modifier.point_cache.frame_end = original_cache_range[1]
        if original_disk_cache is not None and not keep_overridden_disk_cache:
            _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), original_disk_cache)
        if original_surface_ranges is not None and not keep_overridden_range:
            for surface, surface_frame_start, surface_frame_end in original_surface_ranges:
                surface.frame_start = surface_frame_start
                surface.frame_end = surface_frame_end
        if original_surface_disk_cache is not None and not keep_overridden_disk_cache:
            for surface, original_value in original_surface_disk_cache:
                _apply_point_cache_disk_cache(getattr(surface, "point_cache", None), original_value)
        restore_scene_frame_state(scene, original_scene_state)


def _invoke_physics_bake_all_task(
    task_ref,
    scene,
    *,
    bpy_module,
    flow_execution_error_cls,
    require_payload_object_ref,
    capture_scene_frame_state,
    physics_bake_all_has_pending_work,
    start_named_operator,
    ensure_operator_finished,
    restore_scene_frame_state,
):
    original_scene_state = capture_scene_frame_state(scene)
    original_ranges = []
    original_disk_cache = []
    bake_succeeded = False

    try:
        if not physics_bake_all_has_pending_work(task_ref):
            return {"FINISHED", "SKIPPED"}
        for item in task_ref["tasks"]:
            object_ref = require_payload_object_ref(item, str(task_ref.get("source_node", "") or "physics bake"))
            modifier_name = item["modifier_name"]
            modifier = object_ref.modifiers.get(modifier_name)
            if modifier is None:
                raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing during execute", task_ref["source_node"])
            if modifier.type != item["physics_type"]:
                raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' changed type during execute", task_ref["source_node"])

            if bool(item.get("override_settings", True)):
                original_ranges.append(
                    (
                        modifier,
                        int(modifier.point_cache.frame_start),
                        int(modifier.point_cache.frame_end),
                    )
                )
                modifier.point_cache.frame_start = int(item["frame_start"])
                modifier.point_cache.frame_end = int(item["frame_end"])
            if _physics_disk_cache_enabled(item):
                original_disk_cache.append(
                    (
                        modifier,
                        _capture_point_cache_disk_cache_state(getattr(modifier, "point_cache", None)),
                    )
                )
                _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), True)

            if item["free_before_bake"]:
                override = {
                    "object": object_ref,
                    "active_object": object_ref,
                    "selected_objects": [object_ref],
                    "selected_editable_objects": [object_ref],
                    "scene": scene,
                    "view_layer": bpy_module.context.view_layer,
                    "point_cache": modifier.point_cache,
                }
                with bpy_module.context.temp_override(**override):
                    if bpy_module.ops.ptcache.free_bake.poll():
                        bpy_module.ops.ptcache.free_bake()

        if bool(task_ref.get("override_settings", True)):
            scene.frame_start = int(task_ref["scene_frame_start"])
            scene.frame_end = int(task_ref["scene_frame_end"])
            scene.frame_set(scene.frame_start)
        _op_path, result, _tokens = start_named_operator(
            ("ptcache.bake_all",),
            {"scene": scene, "view_layer": bpy_module.context.view_layer},
            {"bake": True},
            task_ref["source_node"],
            invoke_async=False,
        )
        bake_succeeded = True
        return ensure_operator_finished(result, "AF_E005", "bpy.ops.ptcache.bake_all", task_ref["source_node"])
    finally:
        keep_overridden_range = bake_succeeded and bool(task_ref.get("override_settings", True))
        keep_overridden_disk_cache = bake_succeeded and any(
            _physics_disk_cache_enabled(item) for item in list(task_ref.get("tasks", []) or [])
        )
        if not keep_overridden_range:
            for modifier, frame_start, frame_end in original_ranges:
                modifier.point_cache.frame_start = frame_start
                modifier.point_cache.frame_end = frame_end
        if not keep_overridden_disk_cache:
            for modifier, original_value in original_disk_cache:
                _apply_point_cache_disk_cache(getattr(modifier, "point_cache", None), original_value)
        restore_scene_frame_state(scene, original_scene_state)


def _invoke_render_task(
    task_ref,
    fallback_scene,
    node_name,
    *,
    flow_execution_error_cls,
    capture_scene_frame_state,
    start_named_operator,
    ensure_operator_finished,
    restore_scene_frame_state,
):
    scene = task_ref.get("scene_ref") or fallback_scene
    if scene is None:
        raise flow_execution_error_cls("AF_E001", "Target scene is missing", node_name)
    if getattr(scene, "camera", None) is None:
        raise flow_execution_error_cls("AF_E001", "Render scene has no active camera", node_name)

    original_state = capture_scene_frame_state(scene)
    try:
        if str(task_ref.get("render_mode", "STILL")) == "STILL":
            frame = int(task_ref.get("frame", scene.frame_current))
            scene.frame_set(frame)
            _op_path, result, _tokens = start_named_operator(
                ("render.render",),
                {},
                {
                    "scene": scene.name,
                    "write_still": bool(task_ref.get("write_still", True)),
                    "use_viewport": bool(task_ref.get("use_viewport", False)),
                },
                node_name,
                invoke_async=False,
            )
            ensure_operator_finished(result, "AF_E005", "bpy.ops.render.render", node_name)
            return {"scene": scene.name, "mode": "STILL", "frame": frame, "camera": scene.camera.name}

        frame_start = int(scene.frame_start)
        frame_end = int(scene.frame_end)
        if bool(task_ref.get("override_frame_range", False)):
            frame_start = int(task_ref.get("frame_start", frame_start))
            frame_end = int(task_ref.get("frame_end", frame_end))
            scene.frame_start = frame_start
            scene.frame_end = frame_end
        scene.frame_set(frame_start)
        _op_path, result, _tokens = start_named_operator(
            ("render.render",),
            {},
            {
                "scene": scene.name,
                "animation": True,
                "use_viewport": bool(task_ref.get("use_viewport", False)),
            },
            node_name,
            invoke_async=False,
        )
        ensure_operator_finished(result, "AF_E005", "bpy.ops.render.render", node_name)
        return {
            "scene": scene.name,
            "mode": "ANIMATION",
            "frame_start": frame_start,
            "frame_end": frame_end,
            "camera": scene.camera.name,
        }
    finally:
        restore_scene_frame_state(scene, original_state)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
