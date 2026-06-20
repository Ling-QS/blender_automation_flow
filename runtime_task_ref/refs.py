import bpy


def _rehydrate_task_ref_object_references(
    task_ref,
    *,
    task_kind_geometry,
    task_kind_physics,
    task_kind_render,
    task_kind_property_package_bake,
    task_kind_physics_bake_all,
    copy_task_ref_payload,
    copy_runtime_state_value,
    ensure_object_persistent_uuid,
    find_object_by_item,
    dedup_obj_items,
    scene=None,
    object_resolver=None,
):
    if not isinstance(task_ref, dict):
        return task_ref
    task_kind = str(task_ref.get("task_kind", task_kind_geometry) or task_kind_geometry)
    refreshed = copy_task_ref_payload(task_ref)
    if task_kind in {task_kind_geometry, task_kind_physics}:
        refreshed.setdefault("object_ref", None)

    if isinstance(refreshed.get("object_ref"), bpy.types.ID):
        obj = refreshed.get("object_ref")
        if getattr(obj, "bl_rna", None) is not None and str(getattr(getattr(obj, "bl_rna", None), "identifier", "") or "") == "Object":
            refreshed["object_name"] = str(getattr(obj, "name", "") or refreshed.get("object_name", ""))
            refreshed["session_uid"] = int(getattr(obj, "session_uid", refreshed.get("session_uid", 0)) or refreshed.get("session_uid", 0))
            refreshed["object_uuid"] = ensure_object_persistent_uuid(obj)

    object_name = str(refreshed.get("object_name", "") or "").strip()
    session_uid = int(refreshed.get("session_uid", 0) or 0)
    object_uuid = str(refreshed.get("object_uuid", "") or "").strip()
    if object_name or session_uid or object_uuid:
        obj = (object_resolver or find_object_by_item)({"id": session_uid, "name": object_name, "uuid": object_uuid})
        if obj is not None:
            refreshed["object_ref"] = obj
            refreshed["object_name"] = str(getattr(obj, "name", "") or object_name)
            refreshed["session_uid"] = int(getattr(obj, "session_uid", session_uid) or session_uid)
            refreshed["object_uuid"] = ensure_object_persistent_uuid(obj)

    if task_kind == task_kind_render:
        refreshed["render_object_items"] = dedup_obj_items(
            list(refreshed.get("render_object_items", []) or []),
            "NAME_ASC",
            object_resolver=object_resolver,
        )
    if task_kind == task_kind_property_package_bake:
        refreshed["predicted_object_items"] = dedup_obj_items(
            list(refreshed.get("predicted_object_items", []) or []),
            "NAME_ASC",
            object_resolver=object_resolver,
        )
    if task_kind == task_kind_physics_bake_all:
        refreshed_tasks = []
        for item in list(refreshed.get("tasks", []) or []):
            if not isinstance(item, dict):
                continue
            task_item = copy_runtime_state_value(item)
            task_item.setdefault("object_ref", None)
            item_name = str(task_item.get("object_name", "") or "").strip()
            item_uid = int(task_item.get("session_uid", 0) or 0)
            item_uuid = str(task_item.get("object_uuid", "") or "").strip()
            obj = (object_resolver or find_object_by_item)({"id": item_uid, "name": item_name, "uuid": item_uuid})
            if obj is not None:
                task_item["object_ref"] = obj
                task_item["object_name"] = str(getattr(obj, "name", "") or item_name)
                task_item["session_uid"] = int(getattr(obj, "session_uid", item_uid) or item_uid)
                task_item["object_uuid"] = ensure_object_persistent_uuid(obj)
            refreshed_tasks.append(task_item)
        refreshed["tasks"] = refreshed_tasks
        refreshed["target_object_ids"] = sorted({int(item.get("session_uid", 0) or 0) for item in refreshed_tasks if int(item.get("session_uid", 0) or 0)})

    del scene
    return refreshed


def _validate_task_ref_object_targets(
    task_ref,
    node_name,
    *,
    flow_execution_error_cls,
    task_kind_geometry,
    task_kind_physics,
    task_kind_physics_bake_all,
):
    if not isinstance(task_ref, dict):
        raise flow_execution_error_cls("AF_E011", "Task Ref payload is invalid", node_name)
    task_kind = str(task_ref.get("task_kind", task_kind_geometry) or task_kind_geometry)
    if task_kind in {task_kind_geometry, task_kind_physics}:
        object_ref = task_ref.get("object_ref")
        if object_ref is None:
            object_name = str(task_ref.get("object_name", "") or "").strip()
            if object_name:
                raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' is missing", node_name)
            raise flow_execution_error_cls("AF_E002", "Target object is missing", node_name)
    elif task_kind == task_kind_physics_bake_all:
        for item in list(task_ref.get("tasks", []) or []):
            if not isinstance(item, dict):
                continue
            if item.get("object_ref") is not None:
                continue
            object_name = str(item.get("object_name", "") or "").strip()
            modifier_name = str(item.get("modifier_name", "") or "").strip()
            if object_name and modifier_name:
                raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' for modifier '{modifier_name}' is missing", node_name)
            if object_name:
                raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' is missing", node_name)
            raise flow_execution_error_cls("AF_E002", "Target object is missing", node_name)
    return task_ref


def _invalid_task_ref_issue(task_ref):
    if not isinstance(task_ref, dict):
        return None
    status_value = str(task_ref.get("status", "") or "").strip().upper()
    report = dict(task_ref.get("report") or {})
    report_status = str(report.get("status", "") or "").strip().upper()
    if status_value != "INVALID" and report_status != "INVALID":
        return None
    error_code = str(report.get("error_code", "") or "").strip() or "AF_E011"
    error_message = str(report.get("error_message", "") or "").strip() or "Task Ref is invalid"
    node_name = str(report.get("node_name", "") or task_ref.get("source_node", "") or "").strip()
    return {
        "code": error_code,
        "message": error_message,
        "node_name": node_name,
    }


def _raise_if_invalid_task_ref(task_ref, fallback_node_name, *, flow_execution_error_cls):
    issue = _invalid_task_ref_issue(task_ref)
    if issue is None:
        return task_ref
    raise flow_execution_error_cls(
        str(issue.get("code", "AF_E011") or "AF_E011"),
        str(issue.get("message", "Task Ref is invalid") or "Task Ref is invalid"),
        str(issue.get("node_name", "") or fallback_node_name),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
