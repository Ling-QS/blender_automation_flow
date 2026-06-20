import uuid

import bpy
from mathutils import Vector


def _ensure_object_persistent_uuid(obj, object_persistent_uuid_prop):
    if obj is None:
        return ""
    try:
        existing = str(obj.get(object_persistent_uuid_prop, "") or "").strip()
    except Exception:
        existing = ""
    if existing:
        return existing
    new_value = uuid.uuid4().hex
    try:
        obj[object_persistent_uuid_prop] = new_value
    except Exception:
        return ""
    return new_value


def _serialize_id_reference(value):
    try:
        id_type = str(getattr(getattr(value, "bl_rna", None), "identifier", "") or "")
        name = str(getattr(value, "name_full", getattr(value, "name", "")) or "")
    except Exception:
        return None
    if not id_type or not name:
        return None
    return {
        "__af_id_ref__": True,
        "id_type": id_type,
        "name": name,
    }


def _serialize_runtime_state_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Vector):
        return [float(component) for component in value]
    if isinstance(value, (list, tuple)):
        return [_serialize_runtime_state_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_runtime_state_value(item)
            for key, item in value.items()
        }
    id_ref = _serialize_id_reference(value)
    if id_ref is not None:
        return id_ref
    return repr(value)


def _deserialize_id_reference(payload):
    if not isinstance(payload, dict) or not payload.get("__af_id_ref__"):
        return payload
    id_type = str(payload.get("id_type", "") or "")
    name = str(payload.get("name", "") or "")
    if not id_type or not name:
        return None
    data_map = {
        "Object": getattr(bpy.data, "objects", None),
        "Scene": getattr(bpy.data, "scenes", None),
        "Collection": getattr(bpy.data, "collections", None),
        "NodeTree": getattr(bpy.data, "node_groups", None),
        "GeometryNodeTree": getattr(bpy.data, "node_groups", None),
    }
    collection = data_map.get(id_type)
    if collection is None:
        return None
    try:
        return collection.get(name)
    except Exception:
        return None


def _deserialize_runtime_state_value(value):
    if isinstance(value, list):
        return [_deserialize_runtime_state_value(item) for item in value]
    if isinstance(value, dict):
        if value.get("__af_id_ref__"):
            return _deserialize_id_reference(value)
        return {
            str(key): _deserialize_runtime_state_value(item)
            for key, item in value.items()
        }
    return value


def _copy_runtime_state_value(value):
    return _deserialize_runtime_state_value(_serialize_runtime_state_value(value))


def _copy_task_ref_payload(task_ref):
    return _copy_runtime_state_value(task_ref)


def _copy_task_plan_payload(task_plan):
    return _copy_runtime_state_value(task_plan)

