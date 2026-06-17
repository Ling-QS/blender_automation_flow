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
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "physics bake"))
    modifier_name = task_ref["modifier_name"]
    physics_type = task_ref["physics_type"]
    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing during execute", task_ref["source_node"])
    if modifier.type != physics_type:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' changed type during execute", task_ref["source_node"])
    base_override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
    }
    wait_state = {
        "job_type": bake_job_type,
        "cleanup": {
            "kind": task_kind_physics,
            "scene": scene,
            "scene_state": capture_scene_frame_state(scene),
            "modifier": modifier,
            "original_cache_range": None,
            "original_surface_ranges": None,
            "keep_overridden_range_on_success": bool(task_ref.get("override_settings", True)),
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
            if bool(task_ref.get("override_settings", True)):
                modifier.point_cache.frame_start = int(task_ref["frame_start"])
                modifier.point_cache.frame_end = int(task_ref["frame_end"])
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
            canvas_settings = modifier.canvas_settings
            if bool(task_ref.get("override_settings", True)):
                for surface in canvas_settings.canvas_surfaces:
                    original_surface_ranges.append((surface, int(surface.frame_start), int(surface.frame_end)))
                    surface.frame_start = int(task_ref["frame_start"])
                    surface.frame_end = int(task_ref["frame_end"])
            wait_state["cleanup"]["original_surface_ranges"] = original_surface_ranges
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
            "keep_overridden_range_on_success": bool(task_ref.get("override_settings", True)),
        },
    }
    try:
        if not physics_bake_all_has_pending_work(task_ref):
            return {"completed": True, "operator_result": "SKIPPED", "wait_state": wait_state}
        for item in task_ref["tasks"]:
            object_ref = require_payload_object_ref(item, str(task_ref.get("source_node", "") or "physics bake"))
            modifier_name = item["modifier_name"]
            modifier = object_ref.modifiers.get(modifier_name)
            if modifier is None:
                raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing during execute", task_ref["source_node"])
            if modifier.type != item["physics_type"]:
                raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' changed type during execute", task_ref["source_node"])
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
            if item["free_before_bake"]:
                override = compose_bake_override(
                    {
                        "object": object_ref,
                        "active_object": object_ref,
                        "selected_objects": [object_ref],
                        "selected_editable_objects": [object_ref],
                        "scene": scene,
                        "view_layer": (ui_context or {}).get("view_layer", bpy_module.context.view_layer),
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
    object_ref = require_payload_object_ref(task_ref, str(task_ref.get("source_node", "") or "physics bake"))
    modifier_name = task_ref["modifier_name"]
    physics_type = task_ref["physics_type"]
    modifier = object_ref.modifiers.get(modifier_name)
    if modifier is None:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' missing during execute", task_ref["source_node"])
    if modifier.type != physics_type:
        raise flow_execution_error_cls("AF_E017", f"Modifier '{modifier_name}' changed type during execute", task_ref["source_node"])
    override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": scene,
        "view_layer": bpy_module.context.view_layer,
    }
    original_scene_state = capture_scene_frame_state(scene)
    original_cache_range = None
    original_surface_ranges = None
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
            if bool(task_ref.get("override_settings", True)):
                modifier.point_cache.frame_start = int(task_ref["frame_start"])
                modifier.point_cache.frame_end = int(task_ref["frame_end"])
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
            if bool(task_ref.get("override_settings", True)):
                for surface in canvas_settings.canvas_surfaces:
                    original_surface_ranges.append((surface, int(surface.frame_start), int(surface.frame_end)))
                    surface.frame_start = int(task_ref["frame_start"])
                    surface.frame_end = int(task_ref["frame_end"])
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
        if original_cache_range is not None and not keep_overridden_range:
            modifier.point_cache.frame_start = original_cache_range[0]
            modifier.point_cache.frame_end = original_cache_range[1]
        if original_surface_ranges is not None and not keep_overridden_range:
            for surface, surface_frame_start, surface_frame_end in original_surface_ranges:
                surface.frame_start = surface_frame_start
                surface.frame_end = surface_frame_end
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
        if not keep_overridden_range:
            for modifier, frame_start, frame_end in original_ranges:
                modifier.point_cache.frame_start = frame_start
                modifier.point_cache.frame_end = frame_end
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
