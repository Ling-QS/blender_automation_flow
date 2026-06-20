import uuid

import bpy

from ..node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME, find_node_input_socket

def _frame_range_from_task_ref(
    task_ref,
    scene,
    *,
    task_kind_render,
    task_kind_property_package_bake,
    task_kind_physics_bake_all,
    task_kind_geometry,
):
    fallback_start = int(getattr(scene, "frame_start", 1))
    fallback_end = int(getattr(scene, "frame_end", fallback_start))
    task_kind = str(task_ref.get("task_kind", task_kind_geometry))

    if task_kind == task_kind_render:
        if str(task_ref.get("render_mode", "STILL")) == "STILL":
            frame = int(task_ref.get("frame", fallback_start))
            return frame, frame
        return int(task_ref.get("frame_start", fallback_start)), int(task_ref.get("frame_end", fallback_end))

    if task_kind == task_kind_property_package_bake:
        return int(task_ref.get("frame_start", fallback_start)), int(task_ref.get("frame_end", fallback_end))

    if task_kind == task_kind_physics_bake_all:
        tasks = [item for item in task_ref.get("tasks", []) if isinstance(item, dict)]
        if not tasks:
            return fallback_start, fallback_end
        return (
            min(int(item.get("frame_start", fallback_start)) for item in tasks),
            max(int(item.get("frame_end", fallback_end)) for item in tasks),
        )

    return int(task_ref.get("frame_start", fallback_start)), int(task_ref.get("frame_end", fallback_end))


def _make_property_package_bake_task_ref_payload(
    node,
    owner_tree_name,
    start_tree_name,
    start_node_name,
    frame_start,
    frame_end,
    bake_asset_id,
    action_name,
    predicted_targets,
    preview_degraded=False,
    record_tree_name="",
    record_node_name="",
    record_group_path=None,
    ref_role="TARGET",
    *,
    task_kind_property_package_bake,
    dedup_obj_items,
):
    payload = {
        "task_kind": task_kind_property_package_bake,
        "task_uid": str(uuid.uuid4()),
        "source_node": node.name,
        "source_tree_name": str(owner_tree_name or ""),
        "start_tree_name": str(start_tree_name or ""),
        "start_node_name": str(start_node_name or ""),
        "record_tree_name": str(record_tree_name or owner_tree_name or ""),
        "record_node_name": str(record_node_name or ""),
        "record_group_path": list(record_group_path or []),
        "property_package_bake_ref_role": str(ref_role or "TARGET"),
        "frame_start": int(frame_start),
        "frame_end": int(frame_end),
        "free_before_bake": bool(getattr(node, "free_before_bake", False)),
        "restore_current_frame": bool(getattr(node, "restore_current_frame", True)),
        "bake_asset_id": str(bake_asset_id or ""),
        "action_name": str(action_name or ""),
        "predicted_object_items": dedup_obj_items(list(predicted_targets.get("predicted_object_items", []) or []), "NAME_ASC"),
        "predicted_component_paths": list(predicted_targets.get("predicted_component_paths", []) or []),
        "record_node_names": list(predicted_targets.get("record_node_names", []) or []),
        "object_scope_mode": str(predicted_targets.get("object_scope_mode", "DYNAMIC") or "DYNAMIC"),
        "prediction_skipped": bool(predicted_targets.get("prediction_skipped", False)),
        "prediction_reason": str(predicted_targets.get("prediction_reason", "") or ""),
    }
    if preview_degraded:
        payload["preview_degraded"] = True
    return payload


def _build_property_package_bake_task_ref_fallback(
    runner,
    node,
    *,
    flow_execution_error_cls,
    make_property_package_bake_task_ref_payload,
):
    if runner is None or node is None:
        return None
    try:
        return runner._build_property_package_bake_task_ref(node)
    except flow_execution_error_cls as exc:
        return runner._make_invalid_task_ref_payload(node, exc)
    except Exception as exc:
        return runner._make_invalid_task_ref_payload(node, exc)


def _collect_predicted_items_from_property_package(
    property_package,
    owner_node_name,
    predicted_by_id,
    predicted_component_paths,
    *,
    iter_property_package_entries,
    property_package_role_snapshot,
    property_package_role_target,
    property_package_scope_modifier,
    property_package_scope_object,
):
    package_entries = iter_property_package_entries(
        property_package,
        owner_node_name,
        allow_roles={property_package_role_snapshot, property_package_role_target},
        allow_scopes={property_package_scope_modifier, property_package_scope_object},
    )
    for entry in package_entries:
        for item in list(entry.get("items", [])):
            object_id = int(item.get("object_id", 0) or 0)
            object_name = str(item.get("object_name", "") or "").strip()
            if object_id or object_name:
                predicted_by_id[object_id or object_name] = {
                    "id": int(object_id),
                    "name": object_name,
                }
            component_path = str(item.get("component_path", "") or "").strip()
            if component_path:
                predicted_component_paths.add(component_path)


def _manual_predict_property_package_bake_targets(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
    *,
    flow_runner_cls,
    find_single_from_input_socket,
    first_output_node,
    collect_predicted_items_from_property_package,
    dedup_obj_items,
):
    start_node = getattr(getattr(start_tree, "nodes", None), "get", lambda _name: None)(str(start_node_name or ""))
    if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
        return {
            "predicted_object_items": [],
            "predicted_component_paths": [],
            "record_node_names": [],
            "object_scope_mode": "DYNAMIC",
        }

    predictor_runner = None
    try:
        predictor_runner = flow_runner_cls(
            start_tree,
            scene,
            start_node_name=str(start_node_name or ""),
            auto_follow=False,
        )
    except Exception:
        predictor_runner = None

    predicted_by_id = {}
    predicted_component_paths = set()
    record_node_names = []
    prediction_dynamic = predictor_runner is None
    visited = set()
    current = start_node

    while current is not None and current.name not in visited:
        visited.add(current.name)
        if str(getattr(current, "bl_idname", "") or "") == "AFNodeRecordPropertyPackage" and not bool(getattr(current, "mute", False)):
            record_node_names.append(str(getattr(current, "name", "") or ""))
            property_package = None
            package_input = find_node_input_socket(current, PROPERTY_PACKAGE_SOCKET_NAME)
            upstream_node, upstream_socket = find_single_from_input_socket(package_input) if package_input is not None else (None, None)
            if upstream_node is None:
                prediction_dynamic = True
            elif predictor_runner is not None:
                try:
                    property_package = predictor_runner._get_output_from_source(upstream_node, upstream_socket, "property_package")
                    if property_package is None:
                        property_package = predictor_runner.preview_flow_output(upstream_node, "property_package")
                    if property_package is None:
                        property_package = predictor_runner._get_output_from_source(upstream_node, upstream_socket, "property_package")
                except Exception:
                    prediction_dynamic = True
            if property_package is None:
                prediction_dynamic = True
            else:
                try:
                    collect_predicted_items_from_property_package(
                        property_package,
                        owner_node_name,
                        predicted_by_id,
                        predicted_component_paths,
                    )
                except Exception:
                    prediction_dynamic = True
        if str(getattr(current, "bl_idname", "") or "") == "AFNodeEnd":
            break
        current = first_output_node(current, "Flow Out")

    predicted_items = dedup_obj_items(list(predicted_by_id.values()), "NAME_ASC")
    return {
        "predicted_object_items": predicted_items,
        "predicted_component_paths": sorted(predicted_component_paths),
        "record_node_names": record_node_names,
        "object_scope_mode": "DYNAMIC" if prediction_dynamic else "STATIC",
    }


def _predict_property_package_bake_targets_resilient(
    start_tree,
    start_node_name,
    scene,
    owner_node_name,
    *,
    flow_runner_cls,
    manual_predict_property_package_bake_targets,
):
    direct_targets = None
    try:
        predictor_runner = flow_runner_cls(
            start_tree,
            scene,
            start_node_name=str(start_node_name or ""),
            auto_follow=False,
        )
        direct_targets = predictor_runner._predict_property_package_bake_targets(start_tree, start_node_name, owner_node_name)
    except Exception:
        direct_targets = None

    if direct_targets is not None and list(direct_targets.get("predicted_object_items", []) or []):
        return direct_targets

    manual_targets = manual_predict_property_package_bake_targets(start_tree, start_node_name, scene, owner_node_name)
    if list(manual_targets.get("predicted_object_items", []) or []):
        return manual_targets
    if direct_targets is not None:
        return direct_targets
    return manual_targets


def _rehydrate_property_package_bake_predicted_items(
    task_ref,
    scene,
    *,
    predict_property_package_bake_targets_resilient,
):
    if not isinstance(task_ref, dict) or scene is None:
        return []
    start_tree_name = str(task_ref.get("start_tree_name", "") or task_ref.get("source_tree_name", "") or "")
    start_node_name = str(task_ref.get("start_node_name", "") or "").strip()
    if not start_tree_name or not start_node_name:
        return []
    start_tree = bpy.data.node_groups.get(start_tree_name)
    if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
        return []
    owner_node_name = str(task_ref.get("source_node", "") or "")
    targets = predict_property_package_bake_targets_resilient(start_tree, start_node_name, scene, owner_node_name)
    return list(targets.get("predicted_object_items", []) or [])


def _require_payload_object_ref(payload, node_name, object_name_key="object_name", *, flow_execution_error_cls):
    if not isinstance(payload, dict):
        raise flow_execution_error_cls("AF_E011", "Payload is invalid", node_name)
    object_ref = payload.get("object_ref")
    if object_ref is not None:
        return object_ref
    object_name = str(payload.get(object_name_key, "") or "").strip()
    if object_name:
        raise flow_execution_error_cls("AF_E002", f"Target object '{object_name}' is missing", node_name)
    raise flow_execution_error_cls("AF_E002", "Target object is missing", node_name)


def _precheck_failure_message(issues):
    error_count = len([issue for issue in issues if issue["level"] == "ERROR"])
    first_issue = issues[0] if issues else None
    if first_issue is None:
        return f"Precheck failed with {error_count} error(s). See PRECHECK_REPORT logs."
    first_node_name = str(first_issue.get("node_name", "") or "").strip()
    first_code = str(first_issue.get("code", "") or "").strip()
    first_message = str(first_issue.get("message", "") or "").strip() or "Unknown precheck error"
    details = f"{first_code}: {first_message}" if first_code else first_message
    if first_node_name:
        details = f"{first_node_name}: {details}"
    return f"Precheck failed with {error_count} error(s). First issue: {details}"


__all__ = [
    name
    for name in globals()
    if name.startswith("_") and not name.startswith("__")
]
