import bpy


def _task_operator_result_is_skipped(result):
    if isinstance(result, str):
        return str(result).strip().upper() == "SKIPPED"
    if isinstance(result, (set, tuple, list)):
        return any(str(item).strip().upper() == "SKIPPED" for item in result)
    return False


def _restore_waiting_bake_cleanup(
    wait_state,
    bake_completed,
    *,
    task_kind_geometry,
    task_kind_physics,
    task_kind_physics_bake_all,
    restore_geometry_bake_entry_settings,
    restore_scene_frame_state,
):
    cleanup = wait_state.get("cleanup")
    if cleanup is None:
        return
    kind = cleanup.get("kind", "")
    if kind == task_kind_geometry:
        bake_entry = cleanup.get("bake_entry")
        original_state = cleanup.get("original_bake_entry_state")
        keep_overridden_settings = bake_completed and bool(cleanup.get("keep_overridden_settings_on_success", False))
        if bake_entry is not None and original_state is not None and not keep_overridden_settings:
            restore_geometry_bake_entry_settings(bake_entry, original_state)
        restore_scene_frame_state(cleanup.get("scene"), cleanup.get("scene_state"))
        return
    if kind == task_kind_physics:
        modifier = cleanup.get("modifier")
        keep_overridden_range = bake_completed and bool(cleanup.get("keep_overridden_range_on_success", False))
        if modifier is not None and not keep_overridden_range:
            original_cache_range = cleanup.get("original_cache_range")
            if original_cache_range is not None and hasattr(modifier, "point_cache"):
                modifier.point_cache.frame_start = int(original_cache_range[0])
                modifier.point_cache.frame_end = int(original_cache_range[1])
            original_surface_ranges = cleanup.get("original_surface_ranges")
            if original_surface_ranges:
                for surface, frame_start, frame_end in original_surface_ranges:
                    surface.frame_start = int(frame_start)
                    surface.frame_end = int(frame_end)
        restore_scene_frame_state(cleanup.get("scene"), cleanup.get("scene_state"))
        return
    if kind == task_kind_physics_bake_all:
        if not (bake_completed and bool(cleanup.get("keep_overridden_range_on_success", False))):
            for modifier, frame_start, frame_end in cleanup.get("original_ranges", []):
                if modifier is None or not hasattr(modifier, "point_cache"):
                    continue
                modifier.point_cache.frame_start = int(frame_start)
                modifier.point_cache.frame_end = int(frame_end)
        restore_scene_frame_state(cleanup.get("scene"), cleanup.get("scene_state"))


def _refresh_geometry_bake_cache_state_after_completion(
    task_ref,
    scene=None,
    *,
    find_geometry_bake_entry_for_task,
    geometry_bake_entry_has_cached_data,
    geometry_bake_entry_cached_frame_range,
    resolve_geometry_task_effective_bake_target=None,
    tag_all_node_editor_redraw=None,
):
    scene_ref = scene
    if scene_ref is not None:
        try:
            scene_ref.frame_set(int(scene_ref.frame_current))
        except Exception:
            pass
    view_layer = getattr(bpy.context, "view_layer", None)
    if view_layer is not None and hasattr(view_layer, "update"):
        try:
            view_layer.update()
        except Exception:
            pass

    try:
        bake_entry = find_geometry_bake_entry_for_task(task_ref, "refreshing geometry bake cache state")
    except Exception:
        if tag_all_node_editor_redraw is not None:
            tag_all_node_editor_redraw()
        return None

    if resolve_geometry_task_effective_bake_target is not None:
        task_target = resolve_geometry_task_effective_bake_target(task_ref)
    else:
        task_target = str(task_ref.get("bake_target", "") or "")
        if task_target == "INHERIT":
            bake_target = str(getattr(bake_entry, "bake_target", "") or "")
            task_target = bake_target or task_target
    if task_target != "DISK" and not geometry_bake_entry_has_cached_data(bake_entry):
        for _index in range(6):
            if scene_ref is not None:
                try:
                    scene_ref.frame_set(int(scene_ref.frame_current))
                except Exception:
                    pass
            if view_layer is not None and hasattr(view_layer, "update"):
                try:
                    view_layer.update()
                except Exception:
                    pass
            if geometry_bake_entry_has_cached_data(bake_entry):
                break

    if tag_all_node_editor_redraw is not None:
        tag_all_node_editor_redraw()
    return geometry_bake_entry_cached_frame_range(bake_entry)


def _schedule_geometry_bake_cache_refresh(
    task_ref,
    scene=None,
    retries=24,
    interval=0.12,
    *,
    refresh_geometry_bake_cache_state_after_completion,
    find_geometry_bake_entry_for_task,
    geometry_bake_entry_has_cached_data,
    geometry_bake_disk_cache_exists,
    tag_all_node_editor_redraw=None,
):
    task_ref_copy = dict(task_ref or {})
    scene_ref = scene
    remaining_retries = max(1, int(retries))
    interval_seconds = max(0.05, float(interval))

    def _timer():
        nonlocal remaining_retries
        cache_status = None
        try:
            frame_range = refresh_geometry_bake_cache_state_after_completion(task_ref_copy, scene_ref)
            try:
                object_ref = task_ref_copy.get("object_ref")
                modifier_name = str(task_ref_copy.get("modifier_name", "") or "")
                if object_ref is not None and modifier_name:
                    modifier = object_ref.modifiers.get(modifier_name)
                    if modifier is not None:
                        bake_entry = find_geometry_bake_entry_for_task(task_ref_copy, "refreshing delayed geometry bake cache state")
                        cache_status = {
                            "has_cache": geometry_bake_entry_has_cached_data(bake_entry) or bool(geometry_bake_disk_cache_exists(task_ref_copy, bake_entry=bake_entry)),
                            "frame_range": frame_range,
                        }
            except Exception:
                cache_status = None
        except Exception:
            cache_status = None

        if cache_status is not None and bool(cache_status.get("has_cache", False)):
            if tag_all_node_editor_redraw is not None:
                tag_all_node_editor_redraw()
            return None

        remaining_retries -= 1
        if remaining_retries <= 0:
            if tag_all_node_editor_redraw is not None:
                tag_all_node_editor_redraw()
            return None
        return interval_seconds

    try:
        bpy.app.timers.register(_timer, first_interval=interval_seconds)
    except Exception:
        pass


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
