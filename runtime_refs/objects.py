import copy
import hashlib

import bpy


def _obj_item(obj, ensure_object_persistent_uuid):
    return {
        "id": int(obj.session_uid),
        "name": obj.name,
        "uuid": ensure_object_persistent_uuid(obj),
    }


def _stored_property_package_key_for_tree_node(tree_name, node_name, stored_property_package_prop_prefix):
    digest = hashlib.md5(f"{tree_name}::{node_name}".encode("utf-8")).hexdigest()[:16]
    return f"{stored_property_package_prop_prefix}{digest}"


def _stored_property_package_key_for_node(node, stored_property_package_prop_prefix):
    tree = getattr(node, "id_data", None)
    tree_name = getattr(tree, "name_full", getattr(tree, "name", ""))
    node_type = str(getattr(node, "bl_idname", "") or "")
    if node_type == "AFNodeStorePropertyPackage":
        store_asset_id = str(getattr(node, "store_asset_id", "") or "").strip()
        if store_asset_id:
            return _stored_property_package_key_for_tree_node(
                tree_name,
                store_asset_id,
                stored_property_package_prop_prefix,
            )
    return _stored_property_package_key_for_tree_node(
        tree_name,
        getattr(node, "name", ""),
        stored_property_package_prop_prefix,
    )


def _find_object_by_item(item, object_persistent_uuid_prop):
    target_uuid = str(item.get("uuid", "") or item.get("object_uuid", "") or "").strip()
    if target_uuid:
        for obj in bpy.data.objects:
            try:
                if str(obj.get(object_persistent_uuid_prop, "") or "").strip() == target_uuid:
                    return obj
            except Exception:
                continue
    target_id = int(item["id"])
    for obj in bpy.data.objects:
        if int(obj.session_uid) == target_id:
            return obj
    return bpy.data.objects.get(item["name"])


def _find_object_by_name(name):
    object_name = str(name or "").strip()
    if not object_name:
        return None
    return bpy.data.objects.get(object_name)


def _object_reference_identity(
    object_id,
    object_name,
    object_uuid="",
    object_resolver=None,
    find_object_by_item=None,
    ensure_object_persistent_uuid=None,
):
    object_id = int(object_id or 0)
    object_name = str(object_name or "").strip()
    object_uuid = str(object_uuid or "").strip()
    obj_item = {"id": object_id, "name": object_name, "uuid": object_uuid}
    obj = object_resolver(obj_item) if callable(object_resolver) else find_object_by_item(obj_item)
    resolved_object_id = int(getattr(obj, "session_uid", 0) or 0) if obj is not None else 0
    resolved_object_name = str(getattr(obj, "name", "") or "").strip() if obj is not None else object_name
    resolved_object_uuid = ensure_object_persistent_uuid(obj) if obj is not None else object_uuid
    if resolved_object_uuid:
        key = ("OBJECT_UUID", resolved_object_uuid)
    elif resolved_object_id:
        key = ("OBJECT_ID", resolved_object_id)
    elif resolved_object_name:
        key = ("OBJECT_NAME", resolved_object_name)
    elif object_name:
        key = ("SOURCE_NAME", object_name)
    else:
        key = ("SOURCE_ID", object_id)
    return key, obj, resolved_object_id, resolved_object_name, resolved_object_uuid


def _normalize_object_item_reference(item, object_resolver=None, object_reference_identity=None):
    if not isinstance(item, dict):
        return None
    raw_id = int(item.get("id", 0) or 0)
    raw_name = str(item.get("name", "") or "").strip()
    raw_uuid = str(item.get("uuid", "") or item.get("object_uuid", "") or "").strip()
    _identity_key, obj, resolved_object_id, resolved_object_name, resolved_object_uuid = object_reference_identity(
        raw_id,
        raw_name,
        raw_uuid,
        object_resolver=object_resolver,
    )
    normalized = {
        "id": int(resolved_object_id or raw_id),
        "name": str(resolved_object_name or raw_name),
    }
    final_uuid = str(resolved_object_uuid or raw_uuid or "")
    if final_uuid:
        normalized["uuid"] = final_uuid
    if obj is not None and not normalized["name"]:
        normalized["name"] = str(getattr(obj, "name", "") or "")
        normalized["id"] = int(getattr(obj, "session_uid", normalized["id"]) or normalized["id"])
    if not normalized["id"] and not normalized["name"] and "uuid" not in normalized:
        return None
    return normalized


def _dedup_obj_items(items, sort_mode, object_resolver=None, normalize_object_item_reference=None):
    by_identity = {}
    for item in items:
        normalized = normalize_object_item_reference(item, object_resolver=object_resolver)
        if normalized is None:
            continue
        dedup_key = (
            str(normalized.get("uuid", "") or "")
            or f"id:{int(normalized.get('id', 0) or 0)}"
            or f"name:{str(normalized.get('name', '') or '')}"
        )
        by_identity[dedup_key] = normalized
    values = list(by_identity.values())
    values.sort(key=lambda x: x["name"], reverse=(sort_mode == "NAME_DESC"))
    return values


def _object_list_from_task_ref(
    task_ref,
    sort_mode="NAME_ASC",
    scene=None,
    rehydrate_task_ref_object_references=None,
    rehydrate_property_package_bake_predicted_items=None,
    copy_runtime_state_value=None,
    dedup_obj_items=None,
    obj_item=None,
    ensure_object_persistent_uuid=None,
    task_kind_geometry="GEOMETRY_NODES",
    task_kind_render="RENDER",
    task_kind_property_package_bake="PROPERTY_PACKAGE_BAKE",
    task_kind_physics_bake_all="PHYSICS_BAKE_ALL",
):
    task_ref = rehydrate_task_ref_object_references(task_ref, scene=scene)
    task_kind = str(task_ref.get("task_kind", task_kind_geometry))
    source_task_ref = copy_runtime_state_value(task_ref) if isinstance(task_ref, dict) else None
    if task_kind == task_kind_property_package_bake:
        predicted_items = list(task_ref.get("predicted_object_items", []) or [])
        prediction_skipped = bool(task_ref.get("prediction_skipped", False))
        if not predicted_items and scene is not None and not prediction_skipped:
            predicted_items = rehydrate_property_package_bake_predicted_items(task_ref, scene)
            if predicted_items and isinstance(task_ref, dict):
                task_ref["predicted_object_items"] = copy.deepcopy(predicted_items)
        deduped = dedup_obj_items(predicted_items, sort_mode)
        payload = {"items": deduped, "count": len(deduped), "sort_mode": sort_mode}
        if source_task_ref is not None:
            payload["_source_task_kind"] = task_kind
            payload["_source_task_ref"] = source_task_ref
        return payload
    if task_kind == task_kind_render:
        render_items = task_ref.get("render_object_items", [])
        deduped = dedup_obj_items(render_items, sort_mode)
        payload = {"items": deduped, "count": len(deduped), "sort_mode": sort_mode}
        if source_task_ref is not None:
            payload["_source_task_kind"] = task_kind
            payload["_source_task_ref"] = source_task_ref
        return payload
    if task_kind == task_kind_physics_bake_all:
        obj_items = []
        seen_keys = set()
        for item in task_ref.get("tasks", []):
            obj = item.get("object_ref")
            if obj is None:
                continue
            obj_key = str(item.get("object_uuid", "") or ensure_object_persistent_uuid(obj) or f"id:{int(item.get('session_uid', 0) or 0)}")
            if obj_key in seen_keys:
                continue
            seen_keys.add(obj_key)
            obj_items.append(obj_item(obj))
        deduped = dedup_obj_items(obj_items, sort_mode)
        payload = {"items": deduped, "count": len(deduped), "sort_mode": sort_mode}
        if source_task_ref is not None:
            payload["_source_task_kind"] = task_kind
            payload["_source_task_ref"] = source_task_ref
        return payload

    object_ref = task_ref.get("object_ref")
    if object_ref is None:
        payload = {"items": [], "count": 0, "sort_mode": sort_mode}
        if source_task_ref is not None:
            payload["_source_task_kind"] = task_kind
            payload["_source_task_ref"] = source_task_ref
        return payload
    payload = {"items": [obj_item(object_ref)], "count": 1, "sort_mode": sort_mode}
    if source_task_ref is not None:
        payload["_source_task_kind"] = task_kind
        payload["_source_task_ref"] = source_task_ref
    return payload


def _property_package_object_identity(item, object_resolver=None, object_reference_identity=None):
    return object_reference_identity(
        int(item.get("object_id", 0) or 0),
        str(item.get("object_name", "") or "").strip(),
        str(item.get("object_uuid", "") or item.get("uuid", "") or "").strip(),
        object_resolver=object_resolver,
    )


def _build_allowed_object_identity_filter(object_items, object_resolver=None, object_reference_identity=None):
    items = list(object_items or [])
    if not items:
        return None
    identity_keys = set()
    object_ids = set()
    object_names = set()
    object_uuids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        object_id = int(item.get("id", 0) or 0)
        object_name = str(item.get("name", "") or "").strip()
        object_uuid = str(item.get("uuid", "") or item.get("object_uuid", "") or "").strip()
        if object_id:
            object_ids.add(object_id)
        if object_name:
            object_names.add(object_name)
        if object_uuid:
            object_uuids.add(object_uuid)
        identity_key, _obj, resolved_object_id, resolved_object_name, resolved_object_uuid = object_reference_identity(
            object_id,
            object_name,
            object_uuid,
            object_resolver=object_resolver,
        )
        identity_keys.add(identity_key)
        if resolved_object_id:
            object_ids.add(resolved_object_id)
        if resolved_object_name:
            object_names.add(resolved_object_name)
        if resolved_object_uuid:
            object_uuids.add(resolved_object_uuid)
    return {
        "identity_keys": identity_keys,
        "object_ids": object_ids,
        "object_names": object_names,
        "object_uuids": object_uuids,
    }


def _property_package_item_matches_allowed_objects(
    item,
    allowed_filter,
    object_resolver=None,
    property_package_object_identity=None,
):
    if not allowed_filter:
        return True
    identity_key, _obj, resolved_object_id, resolved_object_name, resolved_object_uuid = property_package_object_identity(
        item,
        object_resolver=object_resolver,
    )
    if identity_key in set(allowed_filter.get("identity_keys", set()) or set()):
        return True
    raw_object_id = int(item.get("object_id", 0) or 0)
    raw_object_name = str(item.get("object_name", "") or "").strip()
    raw_object_uuid = str(item.get("object_uuid", "") or item.get("uuid", "") or "").strip()
    allowed_ids = set(allowed_filter.get("object_ids", set()) or set())
    allowed_names = set(allowed_filter.get("object_names", set()) or set())
    allowed_uuids = set(allowed_filter.get("object_uuids", set()) or set())
    if raw_object_uuid and raw_object_uuid in allowed_uuids:
        return True
    if resolved_object_uuid and resolved_object_uuid in allowed_uuids:
        return True
    if raw_object_id and raw_object_id in allowed_ids:
        return True
    if resolved_object_id and resolved_object_id in allowed_ids:
        return True
    if raw_object_name and raw_object_name in allowed_names:
        return True
    if resolved_object_name and resolved_object_name in allowed_names:
        return True
    return False


def _property_package_to_object_list(
    package,
    sort_mode,
    is_composite_property_package=None,
    dedup_obj_items=None,
):
    if is_composite_property_package(package):
        obj_items = []
        for entry in package.get("entries", []):
            entry_payload = _property_package_to_object_list(
                entry,
                sort_mode,
                is_composite_property_package=is_composite_property_package,
                dedup_obj_items=dedup_obj_items,
            )
            obj_items.extend(list(entry_payload.get("items", [])))
        deduped = dedup_obj_items(obj_items, sort_mode)
        return {"items": deduped, "count": len(deduped), "sort_mode": sort_mode}
    obj_items = []
    for item in package.get("items", []):
        obj_items.append({"id": int(item["object_id"]), "name": str(item["object_name"])})
    deduped = dedup_obj_items(obj_items, sort_mode)
    return {"items": deduped, "count": len(deduped), "sort_mode": sort_mode}

