import copy
import json
import re

import bpy

from ..runtime_persistence.serialization import (
    _deserialize_runtime_state_value,
    _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl,
    _serialize_runtime_state_value,
)
from ..runtime_persistence.reload_checkpoint import (
    _read_reload_resume_checkpoint as _read_reload_resume_checkpoint_impl,
    _reload_resume_checkpoint_path as _reload_resume_checkpoint_path_impl,
    _remove_reload_resume_checkpoint as _remove_reload_resume_checkpoint_impl,
    _write_reload_resume_checkpoint as _write_reload_resume_checkpoint_impl,
)
from ..runtime_core.constants import (
    PROPERTY_PACKAGE_BAKE_ACTION_NAME_PREFIX,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_BAKE_ASSET_ID,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_END,
    PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START,
    BAKE_JOB_TYPE,
    FLOW_TOGGLE_CACHE_PROP,
    FlowExecutionError,
    PROPERTY_DEFINITION_KIND_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_SETTINGS,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    PROPERTY_SCOPE_KIND_MIXED,
    STATUS_REPORT_CACHE_PROP,
    STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    OBJECT_PERSISTENT_UUID_PROP,
)
from ..runtime_property.packages import (
    _clone_property_package as _clone_property_package_impl,
    _is_composite_property_package as _is_composite_property_package_impl,
    _make_composite_property_package as _make_composite_property_package_impl,
    _property_package_item_count as _property_package_item_count_impl,
    _property_role_label as _property_role_label_impl,
    _property_scope_label as _property_scope_label_impl,
    _validate_property_package as _validate_property_package_impl,
)
from ..runtime_refs.objects import (
    _find_object_by_item as _find_object_by_item_impl,
    _object_reference_identity as _object_reference_identity_impl,
    _property_package_object_identity as _property_package_object_identity_impl,
)
from ..runtime_flow.helpers import _find_single_from_input_socket
from ..runtime_refs.objects import (
    _stored_property_package_key_for_node as _stored_property_package_key_for_node_impl,
    _stored_property_package_key_for_tree_node as _stored_property_package_key_for_tree_node_impl,
)


def _property_package_bake_action_name_from_task_ref(task_ref):
    bake_asset_id = str(task_ref.get("bake_asset_id", "") or "").strip()
    if bake_asset_id:
        return f"{PROPERTY_PACKAGE_BAKE_ACTION_NAME_PREFIX}{bake_asset_id[:12]}"
    source_tree_name = str(task_ref.get("source_tree_name", "") or "").strip() or "Tree"
    source_node_name = str(task_ref.get("source_node", "") or "").strip() or "Target"
    fallback = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{source_tree_name}_{source_node_name}").strip("_") or "Bake"
    return f"{PROPERTY_PACKAGE_BAKE_ACTION_NAME_PREFIX}{fallback}"


def _property_package_bake_record_node_from_target(node):
    if node is None or getattr(node, "bl_idname", "") != "AFNodePropertyPackageBakeTarget":
        return None
    task_ref_input = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Task Ref")
    if task_ref_input is None:
        return None
    upstream_node, _upstream_socket = _find_single_from_input_socket(task_ref_input)
    if upstream_node is None:
        return None
    if getattr(upstream_node, "bl_idname", "") == "AFNodeRecordPropertyPackage":
        return upstream_node
    return None


def _property_package_bake_identity_node(node):
    if node is None:
        return None
    node_type = str(getattr(node, "bl_idname", "") or "")
    if node_type == "AFNodeRecordPropertyPackage":
        return node
    if node_type == "AFNodePropertyPackageBakeTarget":
        record_node = _property_package_bake_record_node_from_target(node)
        if record_node is not None:
            return record_node
    return node


def _component_path_for_object_impl(obj):
    return str(getattr(obj, "name", "") or "")


def _property_package_to_definition_impl(package, node_name):
    metadata = dict(package.get("metadata", {}) or {})
    return copy.deepcopy(metadata.get("property_definition", {})) if metadata.get("property_definition") is not None else None


def _property_scope_label(scope_kind):
    return _property_scope_label_impl(scope_kind, "OBJECT", "MODIFIER")


def _property_role_label(package_role):
    return _property_role_label_impl(package_role, "SNAPSHOT", "TARGET", "SETTINGS", PROPERTY_PACKAGE_ROLE_COMPOSITE)


def _is_composite_property_package(property_package):
    return _is_composite_property_package_impl(property_package, PROPERTY_PACKAGE_ROLE_COMPOSITE)


def _property_package_item_count(property_package):
    return _property_package_item_count_impl(property_package, _is_composite_property_package)


def _validate_property_package(property_package, node_name):
    return _validate_property_package_impl(
        property_package,
        node_name,
        flow_execution_error_cls=FlowExecutionError,
        property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
    )


def _make_composite_property_package(source_node, entries, metadata=None):
    return _make_composite_property_package_impl(
        source_node,
        entries,
        metadata=metadata,
        clone_property_package=_clone_property_package_impl,
        property_package_item_count=_property_package_item_count,
        property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
        property_scope_kind_mixed=PROPERTY_SCOPE_KIND_MIXED,
    )


def _property_package_has_property_content(property_package, node_name):
    summary = _property_package_to_definition_impl(property_package, node_name)
    if not isinstance(summary, dict):
        return False
    if str(summary.get("definition_kind", "") or "") == PROPERTY_DEFINITION_KIND_COMPOSITE:
        return bool(list(summary.get("entries", [])))
    return bool(dict(summary.get("properties", {}) or {}))


def _property_package_bake_action_identifiers_from_node(node):
    identity_node = _property_package_bake_identity_node(node)
    if identity_node is not None and getattr(identity_node, "bl_idname", "") == "AFNodeRecordPropertyPackage":
        bake_asset_id = str(getattr(identity_node, "record_asset_id", "") or "").strip()
    else:
        bake_asset_id = str(getattr(node, "bake_asset_id", "") or "").strip()
    action_name = _property_package_bake_action_name_from_task_ref(
        {
            "bake_asset_id": bake_asset_id,
            "source_tree_name": getattr(getattr(identity_node, "id_data", None), "name", getattr(getattr(node, "id_data", None), "name", "")),
            "source_node": getattr(identity_node, "name", getattr(node, "name", "")),
        }
    )
    return bake_asset_id, action_name


def _find_property_package_bake_action_by_identifier(bake_asset_id="", action_name=""):
    bake_asset_id = str(bake_asset_id or "").strip()
    action_name = str(action_name or "").strip()
    for action in bpy.data.actions:
        if bake_asset_id and str(action.get(PROPERTY_PACKAGE_BAKE_ACTION_PROP_BAKE_ASSET_ID, "") or "").strip() == bake_asset_id:
            return action
    if action_name:
        return bpy.data.actions.get(action_name)
    return None


def _find_property_package_bake_action_for_node(node):
    bake_asset_id, action_name = _property_package_bake_action_identifiers_from_node(node)
    return _find_property_package_bake_action_by_identifier(bake_asset_id, action_name)


def _property_package_bake_action_has_cached_data(action):
    if action is None:
        return False
    try:
        if len(getattr(action, "layers", [])) > 0 and len(getattr(action, "slots", [])) > 0:
            return True
    except Exception:
        pass
    try:
        if len(getattr(action, "fcurves", [])) > 0:
            return True
    except Exception:
        pass
    return False


def _property_package_bake_action_frame_range(action):
    if action is None or not _property_package_bake_action_has_cached_data(action):
        return None
    tagged_start = action.get(PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START, None)
    tagged_end = action.get(PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_END, None)
    try:
        if tagged_start is not None and tagged_end is not None:
            return (int(tagged_start), int(tagged_end))
    except Exception:
        pass
    for attr_name in ("curve_frame_range", "frame_range"):
        try:
            frame_range = getattr(action, attr_name, None)
            if frame_range is None or len(frame_range) < 2:
                continue
            return (int(round(float(frame_range[0]))), int(round(float(frame_range[1]))))
        except Exception:
            continue
    return None


def _property_package_bake_cache_status_from_node(node):
    if node is None or getattr(node, "bl_idname", "") not in {"AFNodePropertyPackageBakeTarget", "AFNodeRecordPropertyPackage"}:
        return None
    action = _find_property_package_bake_action_for_node(node)
    if not _property_package_bake_action_has_cached_data(action):
        return {"has_cache": False, "frame_range": None, "source": "ACTION"}
    return {
        "has_cache": True,
        "frame_range": _property_package_bake_action_frame_range(action),
        "source": "ACTION",
        "action_name": str(getattr(action, "name", "") or ""),
    }


def _property_package_bake_slot_display_name(obj):
    try:
        return f"obj_{int(getattr(obj, 'session_uid', 0) or 0)}"
    except Exception:
        return f"obj_{str(getattr(obj, 'name', 'Object') or 'Object')}"


def _operator_result_tokens(result):
    if isinstance(result, (set, list, tuple)):
        return {str(item) for item in result}
    if result is None:
        return set()
    return {str(result)}


def _reload_resume_checkpoint_path(blend_filepath):
    return _reload_resume_checkpoint_path_impl(blend_filepath)


def _write_reload_resume_checkpoint(filepath, payload):
    return _write_reload_resume_checkpoint_impl(
        filepath,
        payload,
        _serialize_runtime_state_value,
    )


def _read_reload_resume_checkpoint(filepath):
    return _read_reload_resume_checkpoint_impl(
        filepath,
        _deserialize_runtime_state_value,
    )


def _remove_reload_resume_checkpoint(filepath):
    return _remove_reload_resume_checkpoint_impl(filepath)


def _stored_property_package_key_for_tree_node(tree_name, node_name):
    return _stored_property_package_key_for_tree_node_impl(
        tree_name,
        node_name,
        STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    )


def _stored_property_package_key_for_node(node):
    return _stored_property_package_key_for_node_impl(
        node,
        STORED_PROPERTY_PACKAGE_PROP_PREFIX,
    )


def _read_stored_property_package_direct(node, owner=None):
    owner = owner if owner is not None else node
    if owner is None:
        return None
    raw = str(owner.get(_stored_property_package_key_for_node(node), "") or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _fallback_group_instance_stored_property_package(node):
    group_tree = getattr(node, "id_data", None)
    if group_tree is None:
        return None
    found = []
    for node_tree in bpy.data.node_groups:
        if getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            continue
        for candidate in getattr(node_tree, "nodes", []):
            if getattr(candidate, "bl_idname", "") != "AFNodeGroup":
                continue
            if getattr(candidate, "group_tree", None) != group_tree:
                continue
            package = _read_stored_property_package_direct(node, owner=candidate)
            if package is None:
                continue
            found.append(package)
    if not found:
        return None
    if len(found) == 1:
        return copy.deepcopy(found[0])
    return _make_composite_property_package("GroupInstances", found)


def _rehydrate_property_package_object_references(property_package, object_resolver=None, node_name=""):
    try:
        package = _validate_property_package(property_package, node_name or str(property_package.get("source_node", "") or "PropertyPackage"))
    except Exception:
        return property_package
    if _is_composite_property_package(package):
        entries = [
            _rehydrate_property_package_object_references(entry, object_resolver=object_resolver, node_name=node_name)
            for entry in list(package.get("entries", []))
        ]
        result = _make_composite_property_package(
            str(package.get("source_node", "") or ""),
            entries,
            metadata=copy.deepcopy(dict(package.get("metadata", {}) or {})),
        )
        result["metadata"] = copy.deepcopy(dict(result.get("metadata", {}) or {}))
        result["metadata"]["property_definition"] = _property_package_to_definition_impl(
            result,
            node_name or str(package.get("source_node", "") or "PropertyPackage"),
        )
        return result

    result = _clone_property_package_impl(package)
    refreshed_items = []
    for item in list(package.get("items", [])):
        refreshed_item = copy.deepcopy(item)
        _identity_key, obj, resolved_object_id, resolved_object_name, resolved_object_uuid = _property_package_object_identity_impl(
            refreshed_item,
            object_resolver=object_resolver,
            object_reference_identity=lambda object_id, object_name, object_uuid="", object_resolver=None: _object_reference_identity_impl(
                object_id,
                object_name,
                object_uuid=object_uuid,
                object_resolver=object_resolver,
                find_object_by_item=_find_object_by_item_impl,
                ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid_impl(
                    obj,
                    OBJECT_PERSISTENT_UUID_PROP,
                ),
            ),
        )
        if obj is not None:
            refreshed_item["object_id"] = int(resolved_object_id or int(refreshed_item.get("object_id", 0) or 0))
            refreshed_item["object_name"] = str(resolved_object_name or refreshed_item.get("object_name", "") or "")
            refreshed_item["object_uuid"] = str(resolved_object_uuid or refreshed_item.get("object_uuid", "") or "")
            component_type = str(refreshed_item.get("component_type", "") or "")
            component_name = str(refreshed_item.get("component_name", "") or "")
            if str(refreshed_item.get("target_kind", "") or "") == PROPERTY_PACKAGE_SCOPE_OBJECT:
                refreshed_item["component_name"] = str(getattr(obj, "name", "") or refreshed_item["object_name"])
                refreshed_item["component_type"] = str(getattr(obj, "type", "") or component_type or "OBJECT")
                refreshed_item["component_path"] = _component_path_for_object_impl(obj)
            elif component_name:
                refreshed_item["component_path"] = f"{getattr(obj, 'name', refreshed_item['object_name'])}/{component_name}"
                refreshed_item["component_type"] = component_type
        refreshed_items.append(refreshed_item)
    result["items"] = refreshed_items
    result["metadata"] = copy.deepcopy(dict(result.get("metadata", {}) or {}))
    result["metadata"]["count"] = len(refreshed_items)
    result["metadata"]["object_count"] = len({int(item.get("object_id", 0) or 0) for item in refreshed_items})
    return result


def _iter_store_property_package_owners(node):
    if node is None:
        return
    yield node
    group_tree = getattr(node, "id_data", None)
    if group_tree is None:
        return
    for node_tree in bpy.data.node_groups:
        if getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            continue
        for candidate in getattr(node_tree, "nodes", []):
            if getattr(candidate, "bl_idname", "") != "AFNodeGroup":
                continue
            if getattr(candidate, "group_tree", None) != group_tree:
                continue
            yield candidate


def _status_report_cache_key(tree_name, node_name, output_key, group_path=None):
    payload = {
        "tree_name": str(tree_name or ""),
        "node_name": str(node_name or ""),
        "output_key": str(output_key or ""),
        "group_path": [dict(item) for item in list(group_path or []) if isinstance(item, dict)],
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _read_status_report_cache(scene):
    if scene is None:
        return {}
    raw_value = str(scene.get(STATUS_REPORT_CACHE_PROP, "") or "").strip()
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_status_report_cache(scene, payload):
    if scene is None:
        return
    safe_payload = payload if isinstance(payload, dict) else {}
    try:
        scene[STATUS_REPORT_CACHE_PROP] = json.dumps(safe_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except Exception:
        pass


def _flow_toggle_cache_key(tree_name, node_name, group_path=None):
    payload = {
        "tree_name": str(tree_name or ""),
        "node_name": str(node_name or ""),
        "group_path": [dict(item) for item in list(group_path or []) if isinstance(item, dict)],
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _read_flow_toggle_cache(scene):
    if scene is None:
        return {}
    raw_value = str(scene.get(FLOW_TOGGLE_CACHE_PROP, "") or "").strip()
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_flow_toggle_cache(scene, payload):
    if scene is None:
        return
    safe_payload = payload if isinstance(payload, dict) else {}
    try:
        scene[FLOW_TOGGLE_CACHE_PROP] = json.dumps(safe_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except Exception:
        pass


def _clear_flow_toggle_state(scene, tree_name, node_name, group_path=None, clear_all_paths=False):
    if scene is None:
        return 0
    cache_payload = _read_flow_toggle_cache(scene)
    if not cache_payload:
        return 0

    removed_keys = []
    target_tree_name = str(tree_name or "")
    target_node_name = str(node_name or "")
    target_group_path = [dict(item) for item in list(group_path or []) if isinstance(item, dict)]

    for cache_key in list(cache_payload.keys()):
        try:
            decoded = json.loads(str(cache_key or ""))
        except Exception:
            continue
        if not isinstance(decoded, dict):
            continue
        if str(decoded.get("tree_name", "") or "") != target_tree_name:
            continue
        if str(decoded.get("node_name", "") or "") != target_node_name:
            continue
        if not clear_all_paths:
            decoded_group_path = [dict(item) for item in list(decoded.get("group_path", []) or []) if isinstance(item, dict)]
            if decoded_group_path != target_group_path:
                continue
        removed_keys.append(cache_key)

    for cache_key in removed_keys:
        cache_payload.pop(cache_key, None)

    if removed_keys:
        _write_flow_toggle_cache(scene, cache_payload)
    return len(removed_keys)


def _has_stored_property_package(node, owner=None):
    owners = (owner,) if owner is not None else _iter_store_property_package_owners(node)
    for owner in owners:
        if _read_stored_property_package_direct(node, owner=owner) is not None:
            return True
    return False


def _clear_stored_property_package(node, owner=None):
    key = _stored_property_package_key_for_node(node)
    cleared_count = 0
    visited_ids = set()
    owners = (owner,) if owner is not None else _iter_store_property_package_owners(node)
    for owner in owners:
        owner_id = owner.as_pointer() if hasattr(owner, "as_pointer") else id(owner)
        if owner_id in visited_ids:
            continue
        visited_ids.add(owner_id)
        try:
            if key in owner:
                del owner[key]
                cleared_count += 1
        except Exception:
            continue
    return cleared_count


def _property_scope_label(scope_kind):
    return _property_scope_label_impl(
        scope_kind,
        PROPERTY_PACKAGE_SCOPE_OBJECT,
        PROPERTY_PACKAGE_SCOPE_MODIFIER,
    )


def _property_role_label(package_role):
    return _property_role_label_impl(
        package_role,
        PROPERTY_PACKAGE_ROLE_SNAPSHOT,
        PROPERTY_PACKAGE_ROLE_TARGET,
        PROPERTY_PACKAGE_ROLE_SETTINGS,
        PROPERTY_PACKAGE_ROLE_COMPOSITE,
    )


def _summarize_property_package(property_package):
    if not isinstance(property_package, dict):
        return {
            "package_role": "",
            "scope_kind": "",
            "definition_kind": "",
            "item_count": 0,
            "object_count": 0,
            "entry_count": 0,
            "has_properties": False,
            "title": "Empty",
            "detail": "Empty",
        }

    package_role = str(property_package.get("package_role", "") or "")
    scope_kind = str(property_package.get("scope_kind", "") or "")
    metadata = dict(property_package.get("metadata", {}) or {})
    definition_kind = str(metadata.get("definition_kind", "") or "")
    item_count = int(metadata.get("count", _property_package_item_count(property_package)) or 0)
    object_count = int(metadata.get("object_count", 0) or 0)
    entry_count = int(metadata.get("entry_count", 0) or 0)
    has_properties = _property_package_has_property_content(property_package, str(property_package.get("source_node", "") or ""))

    if item_count <= 0 and object_count <= 0 and entry_count <= 0:
        title = "Empty"
    elif not has_properties:
        title = "Objects Only"
    elif package_role == PROPERTY_PACKAGE_ROLE_COMPOSITE:
        title = "Composite"
    elif package_role == PROPERTY_PACKAGE_ROLE_SETTINGS:
        title = f"{_property_scope_label(scope_kind)} Settings"
    else:
        title = f"{_property_scope_label(scope_kind)} {_property_role_label(package_role)}".strip()

    detail_parts = [title]
    if entry_count > 0:
        detail_parts.append(f"{entry_count} entries")
    if item_count > 0:
        detail_parts.append(f"{item_count} items")
    if object_count > 0:
        detail_parts.append(f"{object_count} objs")
    if not has_properties and object_count > 0:
        detail_parts.append("No Properties")
    if definition_kind and definition_kind != PROPERTY_DEFINITION_KIND_COMPOSITE and title == "Composite":
        detail_parts.append(definition_kind.title())

    return {
        "package_role": package_role,
        "scope_kind": scope_kind,
        "definition_kind": definition_kind,
        "item_count": item_count,
        "object_count": object_count,
        "entry_count": entry_count,
        "has_properties": bool(has_properties),
        "title": title,
        "detail": " | ".join(detail_parts) if detail_parts else "Empty",
    }


def _capture_scene_frame_state(scene):
    return {
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "frame_current": int(scene.frame_current),
    }


def _restore_scene_frame_state(scene, state):
    if not state:
        return
    frame_start = int(state["frame_start"])
    frame_end = int(state["frame_end"])
    frame_current = int(state["frame_current"])
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(min(max(frame_current, scene.frame_start), scene.frame_end))


def _is_bake_job_running():
    try:
        return bool(bpy.app.is_job_running(BAKE_JOB_TYPE))
    except Exception:
        return False


def _tag_all_node_editor_redraw():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in getattr(wm, "windows", []):
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in getattr(screen, "areas", []):
            if getattr(area, "type", "") == "NODE_EDITOR":
                area.tag_redraw()
