import bpy

from ..runtime_core.constants import TASK_KIND_GEOMETRY, TASK_KIND_PHYSICS
from ..runtime_task_ref import (
    _ensure_object_persistent_uuid,
    _resolve_bake_target,
    _resolve_physics_task_target,
)

def find_bake_task_paths_for_node(context):
    node = getattr(context, "active_node", None)
    space = context.space_data
    if node is None or space is None:
        return []
    tree = getattr(space, "edit_tree", None)
    if tree is None:
        return []
    if getattr(tree, "bl_idname", "") != "GeometryNodeTree":
        return []
    if node.bl_idname not in {"GeometryNodeBake", "GeometryNodeSimulationOutput"}:
        return []

    found = []
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type != "NODES":
                continue
            if getattr(modifier, "node_group", None) != tree:
                continue
            bakes = getattr(modifier, "bakes", None)
            if bakes is None:
                continue
            for bake_entry in bakes:
                node_ref = getattr(bake_entry, "node", None)
                if node_ref and node_ref.name == node.name:
                    found.append(f"{obj.name}/{modifier.name}/{node.name}")
                    break

    return sorted(set(found))


def _find_supported_physics_modifier(obj, modifier_name):
    if obj is None:
        return None
    modifiers = getattr(obj, "modifiers", None)
    modifier = modifiers.get(modifier_name) if modifiers is not None and modifier_name else None
    if modifier is None:
        return None
    modifier_type = str(getattr(modifier, "type", "") or "")
    if modifier_type not in {"CLOTH", "SOFT_BODY", "DYNAMIC_PAINT"}:
        return None
    if modifier_type == "DYNAMIC_PAINT" and getattr(modifier, "canvas_settings", None) is None:
        return None
    return modifier


def _physics_context_modifier(context):
    obj = getattr(context, "object", None)
    if obj is None:
        return None
    for attr_name, expected_type in (
        ("cloth", "CLOTH"),
        ("soft_body", "SOFT_BODY"),
        ("dynamic_paint", "DYNAMIC_PAINT"),
    ):
        modifier = getattr(context, attr_name, None)
        if modifier is None:
            continue
        if str(getattr(modifier, "type", "") or "") != expected_type:
            continue
        if expected_type == "DYNAMIC_PAINT" and getattr(modifier, "canvas_settings", None) is None:
            continue
        return modifier
    active_modifier = getattr(getattr(obj, "modifiers", None), "active", None)
    if active_modifier is None:
        return None
    return _find_supported_physics_modifier(obj, getattr(active_modifier, "name", ""))


def _physics_modifier_task_path(obj_name, modifier_name):
    obj = bpy.data.objects.get(str(obj_name or "").strip())
    if obj is None:
        return ""
    modifier = _find_supported_physics_modifier(obj, str(modifier_name or "").strip())
    if modifier is None:
        return ""
    return f"{obj.name}/{modifier.name}"


def _resolve_physics_bake_task_path_from_context(context, object_name="", modifier_name=""):
    task_path = _physics_modifier_task_path(object_name, modifier_name)
    if task_path:
        return task_path
    modifier = _physics_context_modifier(context)
    obj = getattr(context, "object", None)
    if modifier is None or obj is None:
        return ""
    return _physics_modifier_task_path(obj.name, modifier.name)


def _resolve_bake_task_node(node_tree_name, node_name):
    node_tree = bpy.data.node_groups.get(str(node_tree_name or "").strip())
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    node = node_tree.nodes.get(str(node_name or "").strip())
    if node is None or getattr(node, "bl_idname", "") != "AFNodeBakeTask":
        return node_tree, None
    return node_tree, node


def _resolve_physics_bake_settings_node(node_tree_name, node_name):
    node_tree = bpy.data.node_groups.get(str(node_tree_name or "").strip())
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    node = node_tree.nodes.get(str(node_name or "").strip())
    if node is None or getattr(node, "bl_idname", "") != "AFNodePhysicsBakeSettings":
        return node_tree, None
    return node_tree, node


def _resolve_physics_bake_target_node(node_tree_name, node_name):
    node_tree = bpy.data.node_groups.get(str(node_tree_name or "").strip())
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    node = node_tree.nodes.get(str(node_name or "").strip())
    if node is None or getattr(node, "bl_idname", "") != "AFNodePhysicsBakeTask":
        return node_tree, None
    return node_tree, node


def _resolve_property_package_bake_target_node(node_tree_name, node_name):
    node_tree = bpy.data.node_groups.get(str(node_tree_name or "").strip())
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    node = node_tree.nodes.get(str(node_name or "").strip())
    if node is None or getattr(node, "bl_idname", "") != "AFNodePropertyPackageBakeTarget":
        return node_tree, None
    return node_tree, node


def _find_named_int_input_socket(node, socket_name):
    for socket in getattr(node, "inputs", []):
        if getattr(socket, "bl_idname", "") != "NodeSocketInt":
            continue
        if str(getattr(socket, "name", "") or "") != str(socket_name or ""):
            continue
        return socket
    return None


def _bake_task_int_input_value(node, socket_name, fallback):
    socket = _find_named_int_input_socket(node, socket_name)
    if socket is None:
        return int(fallback)
    try:
        return int(getattr(socket, "default_value", fallback))
    except Exception:
        return int(fallback)


def _build_geometry_bake_task_ref_from_node(node):
    object_ref, modifier, bake_node, bake_entry = _resolve_bake_target(node.bake_task_path, node.name)
    frame_start = _bake_task_int_input_value(node, "Frame Start", 1)
    frame_end = _bake_task_int_input_value(node, "Frame End", 250)
    return {
        "task_kind": TASK_KIND_GEOMETRY,
        "task_uid": "manual_geometry_bake_target",
        "source_node": node.name,
        "source_tree_name": getattr(getattr(node, "id_data", None), "name", ""),
        "task_path": str(node.bake_task_path),
        "object_ref": object_ref,
        "object_name": object_ref.name,
        "session_uid": int(object_ref.session_uid),
        "object_uuid": _ensure_object_persistent_uuid(object_ref),
        "modifier_name": modifier.name,
        "bake_node_name": bake_node.name,
        "bake_id": int(bake_entry.bake_id),
        "bake_mode": str(node.bake_mode),
        "bake_target": str(node.bake_target),
        "use_custom_path": bool(node.use_custom_path),
        "directory": str(node.directory or ""),
        "use_custom_simulation_frame_range": bool(node.use_custom_simulation_frame_range),
        "frame_start": int(frame_start),
        "frame_end": int(frame_end),
        "apply_settings_on_run": bool(node.apply_settings_on_run),
        "free_before_bake": bool(node.free_before_bake),
    }


def _build_physics_bake_task_ref_from_node(node):
    object_ref, modifier = _resolve_physics_task_target(node.physics_task_path, node.name)
    frame_start = _bake_task_int_input_value(node, "Frame Start", 1)
    frame_end = _bake_task_int_input_value(node, "Frame End", 250)
    return {
        "task_kind": TASK_KIND_PHYSICS,
        "task_uid": "manual_physics_bake_settings",
        "source_node": node.name,
        "task_path": str(node.physics_task_path),
        "object_ref": object_ref,
        "object_name": object_ref.name,
        "session_uid": int(object_ref.session_uid),
        "object_uuid": _ensure_object_persistent_uuid(object_ref),
        "modifier_name": modifier.name,
        "physics_type": str(modifier.type),
        "frame_start": int(frame_start),
        "frame_end": int(frame_end),
        "override_settings": bool(node.override_settings),
        "free_before_bake": bool(node.free_before_bake),
        "disk_cache": bool(getattr(node, "disk_cache", False)),
    }


def _free_physics_cache_for_task_ref(task_ref, context):
    object_ref = task_ref["object_ref"]
    modifier = object_ref.modifiers.get(task_ref["modifier_name"])
    if modifier is None:
        return "ERROR", "Supported physics bake modifier not found"

    override = {
        "object": object_ref,
        "active_object": object_ref,
        "selected_objects": [object_ref],
        "selected_editable_objects": [object_ref],
        "scene": getattr(context, "scene", None) or bpy.context.scene,
        "view_layer": getattr(context, "view_layer", None) or bpy.context.view_layer,
    }
    physics_type = str(task_ref["physics_type"])
    if physics_type in {"CLOTH", "SOFT_BODY"}:
        override["point_cache"] = modifier.point_cache
        with bpy.context.temp_override(**override):
            if not bpy.ops.ptcache.free_bake.poll():
                return "NO_CACHE", "No Physics Bake cache to free"
            result = bpy.ops.ptcache.free_bake()
        tokens = {str(item) for item in result} if isinstance(result, (set, list, tuple)) else {str(result)}
        if "FINISHED" not in tokens:
            return "ERROR", "Failed to free Physics Bake cache"
        return "FINISHED", "Freed Physics Bake cache"
    if physics_type == "DYNAMIC_PAINT":
        return "UNSUPPORTED", "Free Physics Bake cache is not supported for Dynamic Paint yet"
    return "ERROR", "Supported physics bake modifier not found"
