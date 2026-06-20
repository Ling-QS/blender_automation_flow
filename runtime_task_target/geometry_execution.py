def _run_geometry_bake_free_operators(
    override,
    payload,
    *,
    bpy_module,
    call_operator_with_override,
):
    free_operators = ("object.geometry_node_bake_delete_single", "object.geometry_nodes_bake_delete_single")
    last_tokens = set()
    executed = False
    for op_path in free_operators:
        namespace, name = op_path.split(".")
        group = getattr(bpy_module.ops, namespace, None)
        if group is None or not hasattr(group, name):
            continue
        operator = getattr(group, name)
        try:
            _result, tokens = call_operator_with_override(operator, override, payload)
        except Exception:
            continue
        last_tokens = set(tokens)
        if "POLL_FAILED" in last_tokens:
            continue
        executed = True
        if "FINISHED" in last_tokens or "CANCELLED" in last_tokens:
            break
    return executed, last_tokens


def _find_geometry_bake_entry_for_task(
    task_ref,
    error_context,
    *,
    flow_execution_error_cls,
    require_payload_object_ref,
):
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or error_context))
    modifier_name = task_ref["modifier_name"]
    bake_id = int(task_ref["bake_id"])

    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing while {error_context}", task_ref["source_node"])

    for entry in modifier.bakes:
        if int(entry.bake_id) == bake_id:
            return entry
    raise flow_execution_error_cls("AF_E017", f"Bake entry missing while {error_context}", task_ref["source_node"])


def _resolve_geometry_task_effective_bake_target(task_ref, *, find_geometry_bake_entry_for_task):
    task_target = str(task_ref.get("bake_target", "INHERIT") or "INHERIT")
    if task_target != "INHERIT":
        return task_target
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "resolving bake target")
    bake_target = str(getattr(bake_entry, "bake_target", "") or "")
    return bake_target or task_target


def _ensure_background_geometry_task_supported(
    task_ref,
    node_name,
    *,
    flow_execution_error_cls,
    resolve_geometry_task_effective_bake_target,
):
    effective_target = resolve_geometry_task_effective_bake_target(task_ref)
    if effective_target != "DISK":
        raise flow_execution_error_cls(
            "AF_E020",
            "Background Task Plan requires GN Bake Target to use Disk bake target",
            node_name,
        )
    return effective_target


def _start_geometry_nodes_bake_task(
    task_ref,
    scene,
    ui_context=None,
    *,
    bpy_module,
    require_payload_object_ref,
    find_geometry_bake_entry_for_task,
    compose_bake_override,
    capture_scene_frame_state,
    geometry_bake_has_existing_cache_for_current_entry,
    geometry_bake_has_existing_cache,
    apply_temporary_geometry_bake_settings,
    apply_current_geometry_bake_temporary_override,
    build_geometry_bake_release_task_ref,
    normalize_geometry_bake_modifier_directory_for_task,
    clear_geometry_bake_recorded_cache_state,
    call_operator_with_override,
    start_named_operator,
    restore_waiting_bake_cleanup,
    bake_job_type,
    task_kind_geometry,
):
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    modifier_name = task_ref["modifier_name"]
    bake_id = int(task_ref["bake_id"])
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "executing geometry bake")
    base_override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
    }
    override = compose_bake_override(base_override, ui_context)
    payload = {
        "session_uid": int(object_ref.session_uid),
        "modifier_name": modifier_name,
        "bake_id": bake_id,
    }
    operators = ("object.geometry_node_bake_single", "object.geometry_nodes_bake_single")
    wait_state = {
        "job_type": bake_job_type,
        "cleanup": {
            "kind": task_kind_geometry,
            "scene": scene,
            "scene_state": capture_scene_frame_state(scene),
            "bake_entry": None,
            "original_bake_entry_state": None,
            "keep_overridden_settings_on_success": False,
        },
    }
    try:
        normalize_geometry_bake_modifier_directory_for_task(task_ref, bake_entry=bake_entry)
        temporary_override, original_state = apply_current_geometry_bake_temporary_override(task_ref)
        wait_state["cleanup"]["bake_entry"] = temporary_override
        wait_state["cleanup"]["original_bake_entry_state"] = original_state
        bake_entry = temporary_override
        if not bool(task_ref.get("free_before_bake", False)):
            if bool(task_ref.get("apply_settings_on_run", False)):
                if geometry_bake_has_existing_cache(task_ref, scene, bake_entry):
                    return {"completed": True, "operator_result": "SKIPPED", "wait_state": wait_state}
            elif geometry_bake_has_existing_cache_for_current_entry(task_ref, scene, bake_entry):
                return {"completed": True, "operator_result": "SKIPPED", "wait_state": wait_state}
        if bool(task_ref.get("apply_settings_on_run", False)):
            if bool(task_ref.get("use_custom_simulation_frame_range", False)):
                scene.frame_start = int(task_ref["frame_start"])
                scene.frame_end = int(task_ref["frame_end"])
                scene.frame_set(scene.frame_start)
        if bool(task_ref.get("free_before_bake", False)):
            release_task_ref, force_release_settings = build_geometry_bake_release_task_ref(task_ref)
            if force_release_settings:
                release_override, _ignored_release_state = apply_temporary_geometry_bake_settings(release_task_ref)
                wait_state["cleanup"]["bake_entry"] = release_override
                wait_state["cleanup"]["original_bake_entry_state"] = original_state
                bake_entry = release_override
            clear_geometry_bake_recorded_cache_state(task_ref)
            _run_geometry_bake_free_operators(
                override,
                payload,
                bpy_module=bpy_module,
                call_operator_with_override=call_operator_with_override,
            )
            if force_release_settings:
                current_override, _ignored_current_state = apply_current_geometry_bake_temporary_override(task_ref)
                wait_state["cleanup"]["bake_entry"] = current_override
                wait_state["cleanup"]["original_bake_entry_state"] = original_state
                bake_entry = current_override
        op_path, result, tokens = start_named_operator(
            operators,
            override,
            payload,
            task_ref["source_node"],
            invoke_async=True,
        )
        wait_state["cleanup"]["keep_overridden_settings_on_success"] = True
    except Exception:
        restore_waiting_bake_cleanup(wait_state, bake_completed=False)
        raise
    return {
        "completed": False,
        "operator_path": op_path,
        "operator_result": str(result),
        "wait_state": wait_state,
    }


def _invoke_geometry_nodes_bake_task(
    task_ref,
    scene,
    *,
    bpy_module,
    require_payload_object_ref,
    find_geometry_bake_entry_for_task,
    capture_scene_frame_state,
    geometry_bake_has_existing_cache_for_current_entry,
    geometry_bake_has_existing_cache,
    apply_temporary_geometry_bake_settings,
    apply_current_geometry_bake_temporary_override,
    build_geometry_bake_release_task_ref,
    normalize_geometry_bake_modifier_directory_for_task,
    clear_geometry_bake_recorded_cache_state,
    call_operator_with_override,
    start_named_operator,
    refresh_geometry_bake_cache_state_after_completion,
    schedule_geometry_bake_cache_refresh,
    resolve_geometry_task_effective_bake_target,
    geometry_bake_entry_has_cached_data,
    geometry_bake_disk_cache_exists,
    clear_geometry_bake_tracked_packed_cache_state,
    write_geometry_bake_tracked_packed_cache_state,
    write_geometry_bake_last_bake_state,
    ensure_operator_finished,
    restore_geometry_bake_entry_settings,
    restore_scene_frame_state,
):
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "geometry bake"))
    modifier_name = task_ref["modifier_name"]
    bake_id = int(task_ref["bake_id"])
    bake_entry = find_geometry_bake_entry_for_task(task_ref, "executing geometry bake")
    override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": bpy_module.context.view_layer,
    }
    payload = {
        "session_uid": int(object_ref.session_uid),
        "modifier_name": modifier_name,
        "bake_id": bake_id,
    }
    operators = ("object.geometry_node_bake_single", "object.geometry_nodes_bake_single")
    temporary_override = None
    original_state = None
    original_scene_state = capture_scene_frame_state(scene)
    keep_overridden_settings = False
    try:
        normalize_geometry_bake_modifier_directory_for_task(task_ref, bake_entry=bake_entry)
        temporary_override, original_state = apply_current_geometry_bake_temporary_override(task_ref)
        bake_entry = temporary_override
        if not bool(task_ref.get("free_before_bake", False)):
            if bool(task_ref.get("apply_settings_on_run", False)):
                if geometry_bake_has_existing_cache(task_ref, scene, bake_entry):
                    return {"FINISHED", "SKIPPED"}
            elif geometry_bake_has_existing_cache_for_current_entry(task_ref, scene, bake_entry):
                return {"FINISHED", "SKIPPED"}
        if bool(task_ref.get("apply_settings_on_run", False)):
            if bool(task_ref.get("use_custom_simulation_frame_range", False)):
                scene.frame_start = int(task_ref["frame_start"])
                scene.frame_end = int(task_ref["frame_end"])
                scene.frame_set(scene.frame_start)
        if bool(task_ref.get("free_before_bake", False)):
            release_task_ref, force_release_settings = build_geometry_bake_release_task_ref(task_ref)
            if force_release_settings:
                release_override, _ignored_release_state = apply_temporary_geometry_bake_settings(release_task_ref)
                bake_entry = release_override
            clear_geometry_bake_recorded_cache_state(task_ref)
            _run_geometry_bake_free_operators(
                override,
                payload,
                bpy_module=bpy_module,
                call_operator_with_override=call_operator_with_override,
            )
            if force_release_settings:
                current_override, _ignored_current_state = apply_current_geometry_bake_temporary_override(task_ref)
                temporary_override = current_override
                bake_entry = current_override
        op_path, result, _tokens = start_named_operator(
            operators,
            override,
            payload,
            task_ref["source_node"],
            invoke_async=False,
        )
        finished_result = ensure_operator_finished(result, "AF_E005", op_path, task_ref["source_node"])
        frame_range = refresh_geometry_bake_cache_state_after_completion(task_ref, scene)
        effective_target = resolve_geometry_task_effective_bake_target(task_ref)
        write_geometry_bake_last_bake_state(task_ref, frame_range=frame_range)
        if effective_target == "PACKED":
            write_geometry_bake_tracked_packed_cache_state(task_ref, frame_range=frame_range)
        else:
            clear_geometry_bake_tracked_packed_cache_state(task_ref)
        should_schedule_refresh = False
        try:
            has_immediate_cache = bool(
                geometry_bake_entry_has_cached_data(bake_entry)
                or geometry_bake_disk_cache_exists(task_ref, bake_entry=bake_entry)
            )
            should_schedule_refresh = not has_immediate_cache
        except Exception:
            should_schedule_refresh = True
        if should_schedule_refresh and schedule_geometry_bake_cache_refresh is not None:
            schedule_geometry_bake_cache_refresh(task_ref, scene)
        keep_overridden_settings = True
        return finished_result
    finally:
        if temporary_override is not None and original_state is not None and not keep_overridden_settings:
            restore_geometry_bake_entry_settings(temporary_override, original_state)
        restore_scene_frame_state(scene, original_scene_state)


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
