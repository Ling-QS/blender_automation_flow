import re

import bpy

from ..runtime_core.constants import OBJECT_PERSISTENT_UUID_PROP
from ..runtime_refs.objects import (
    _dedup_obj_items as _dedup_obj_items_impl,
    _find_object_by_item as _find_object_by_item_impl,
    _normalize_object_item_reference as _normalize_object_item_reference_impl,
    _obj_item as _obj_item_impl,
)
from ..runtime_persistence.serialization import _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl


def _ensure_object_persistent_uuid(obj):
    return _ensure_object_persistent_uuid_impl(obj, OBJECT_PERSISTENT_UUID_PROP)


def _obj_item(obj):
    return _obj_item_impl(obj, _ensure_object_persistent_uuid)


def _find_object_by_item(item):
    return _find_object_by_item_impl(item, OBJECT_PERSISTENT_UUID_PROP)


def _normalize_object_item_reference(item, object_resolver=None):
    return _normalize_object_item_reference_impl(
        item,
        object_resolver=object_resolver,
        object_reference_identity=_object_reference_identity,
    )


def _dedup_obj_items(items, sort_mode, object_resolver=None):
    return _dedup_obj_items_impl(
        items,
        sort_mode,
        object_resolver=object_resolver,
        normalize_object_item_reference=_normalize_object_item_reference,
    )


def _object_reference_identity(object_id, object_name, object_uuid="", object_resolver=None):
    object_id = int(object_id or 0)
    object_name = str(object_name or "").strip()
    object_uuid = str(object_uuid or "").strip()
    obj_item = {"id": object_id, "name": object_name, "uuid": object_uuid}
    obj = object_resolver(obj_item) if callable(object_resolver) else _find_object_by_item(obj_item)
    resolved_object_id = int(getattr(obj, "session_uid", 0) or 0) if obj is not None else 0
    resolved_object_name = str(getattr(obj, "name", "") or "").strip() if obj is not None else object_name
    resolved_object_uuid = _ensure_object_persistent_uuid(obj) if obj is not None else object_uuid
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


def _iter_collection_objects(collection, recursive, include_hidden, object_type_filter):
    if collection is None:
        return []
    source = collection.all_objects if recursive else collection.objects
    result = []
    for obj in source:
        if not include_hidden and obj.hide_get():
            continue
        if object_type_filter != "ALL" and obj.type != object_type_filter:
            continue
        result.append(obj)
    return result


def _iter_scene_objects(scene, recursive, include_hidden, object_type_filter):
    if scene is None:
        return []
    return _iter_collection_objects(scene.collection, recursive, include_hidden, object_type_filter)


def _link_object_to_collection_safe(obj, collection):
    if obj is None or collection is None:
        return False
    if collection in getattr(obj, "users_collection", ()):
        return False
    collection.objects.link(obj)
    return True


def _unlink_object_from_collection_safe(obj, collection):
    if obj is None or collection is None:
        return False
    if collection not in getattr(obj, "users_collection", ()):
        return False
    collection.objects.unlink(obj)
    return True


def _remove_unused_object_data(data_block):
    if data_block is None:
        return False
    try:
        if int(getattr(data_block, "users", 0)) > 0:
            return False
    except Exception:
        return False
    rna_identifier = str(getattr(getattr(data_block, "bl_rna", None), "identifier", "") or "")
    data_container = {
        "Mesh": getattr(bpy.data, "meshes", None),
        "Camera": getattr(bpy.data, "cameras", None),
        "Light": getattr(bpy.data, "lights", None),
        "Curve": getattr(bpy.data, "curves", None),
        "Armature": getattr(bpy.data, "armatures", None),
        "Lattice": getattr(bpy.data, "lattices", None),
        "MetaBall": getattr(bpy.data, "metaballs", None),
        "Speaker": getattr(bpy.data, "speakers", None),
        "GreasePencil": getattr(bpy.data, "grease_pencils", None),
        "GreasePencilv3": getattr(bpy.data, "grease_pencils_v3", None),
    }.get(rna_identifier)
    if data_container is None:
        return False
    try:
        data_container.remove(data_block)
        return True
    except Exception:
        return False


def _collect_render_enabled_scene_objects(scene):
    if scene is None:
        return []
    items = []
    seen_ids = set()
    for obj in getattr(scene, "objects", []):
        if bool(getattr(obj, "hide_render", False)):
            continue
        obj_id = int(obj.session_uid)
        if obj_id in seen_ids:
            continue
        seen_ids.add(obj_id)
        items.append(_obj_item(obj))
    return _dedup_obj_items(items, "NAME_ASC")


def _socket_default_pointer(node, socket_name):
    socket = node.inputs.get(socket_name)
    if socket is None:
        return None
    return getattr(socket, "default_value", None)


def _collect_objects_from_node_group(node_group, visited_groups=None):
    if node_group is None:
        return []
    if visited_groups is None:
        visited_groups = set()
    key = node_group.name_full
    if key in visited_groups:
        return []
    visited_groups.add(key)

    found = []
    for node in node_group.nodes:
        if node.bl_idname == "GeometryNodeObjectInfo":
            obj = _socket_default_pointer(node, "Object")
            if obj is None:
                obj = getattr(node, "object", None)
            if obj is not None:
                found.append(obj)
            continue

        if node.bl_idname == "GeometryNodeCollectionInfo":
            collection = _socket_default_pointer(node, "Collection")
            if collection is None:
                collection = getattr(node, "collection", None)
            if collection is not None:
                found.extend(_iter_collection_objects(collection, recursive=True, include_hidden=True, object_type_filter="ALL"))
            continue

        if node.bl_idname == "GeometryNodeGroup":
            sub_group = getattr(node, "node_tree", None)
            found.extend(_collect_objects_from_node_group(sub_group, visited_groups))

    dedup = {}
    for obj in found:
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _collect_modifier_pointer_references(modifier):
    found = []
    for prop in modifier.bl_rna.properties:
        if prop.identifier == "rna_type":
            continue
        if prop.type != "POINTER":
            continue
        try:
            value = getattr(modifier, prop.identifier)
        except Exception:
            continue
        if isinstance(value, bpy.types.Object):
            found.append(value)
            continue
        if isinstance(value, bpy.types.Collection):
            found.extend(_iter_collection_objects(value, recursive=True, include_hidden=True, object_type_filter="ALL"))
            continue
    dedup = {}
    for obj in found:
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _collect_constraint_pointer_references(owner):
    if owner is None:
        return []
    found = []
    for constraint in getattr(owner, "constraints", []):
        for prop in constraint.bl_rna.properties:
            if prop.identifier == "rna_type" or prop.type != "POINTER":
                continue
            try:
                value = getattr(constraint, prop.identifier)
            except Exception:
                continue
            if isinstance(value, bpy.types.Object):
                found.append(value)
                continue
            if isinstance(value, bpy.types.Collection):
                found.extend(_iter_collection_objects(value, recursive=True, include_hidden=True, object_type_filter="ALL"))
                continue
    dedup = {}
    for obj in found:
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _object_has_collision_modifier(obj):
    if obj is None:
        return False
    try:
        return any(modifier.type == "COLLISION" for modifier in obj.modifiers)
    except Exception:
        return False


def _iter_physics_collision_collection_objects(collection):
    if collection is None:
        return []
    found = []
    for obj in _iter_collection_objects(collection, recursive=True, include_hidden=True, object_type_filter="ALL"):
        if _object_has_collision_modifier(obj):
            found.append(obj)
    dedup = {}
    for obj in found:
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _get_physics_collision_collection(modifier):
    if modifier is None:
        return None
    if modifier.type == "CLOTH":
        collision_settings = getattr(modifier, "collision_settings", None)
        if collision_settings is None or not bool(getattr(collision_settings, "use_collision", False)):
            return None
        return getattr(collision_settings, "collection", None)
    if modifier.type == "SOFT_BODY":
        settings = getattr(modifier, "settings", None)
        if settings is None:
            return None
        use_collision = bool(getattr(settings, "use_edge_collision", False)) or bool(getattr(settings, "use_face_collision", False))
        if not use_collision:
            return None
        return getattr(settings, "collision_collection", None)
    return None


def _collect_explicit_physics_collision_objects(modifier):
    return _iter_physics_collision_collection_objects(_get_physics_collision_collection(modifier))


def _collect_explicit_physics_collision_filter_ids(task_object):
    if task_object is None:
        return None

    allowed_ids = set()
    has_explicit_collection = False
    has_unbounded_collision = False

    for modifier in task_object.modifiers:
        if modifier.type not in {"CLOTH", "SOFT_BODY"}:
            continue
        collection = _get_physics_collision_collection(modifier)
        if collection is None:
            if modifier.type == "CLOTH":
                collision_settings = getattr(modifier, "collision_settings", None)
                if collision_settings is not None and bool(getattr(collision_settings, "use_collision", False)):
                    has_unbounded_collision = True
            else:
                settings = getattr(modifier, "settings", None)
                if settings is not None and (
                    bool(getattr(settings, "use_edge_collision", False))
                    or bool(getattr(settings, "use_face_collision", False))
                ):
                    has_unbounded_collision = True
            continue

        has_explicit_collection = True
        for obj in _iter_physics_collision_collection_objects(collection):
            allowed_ids.add(int(obj.session_uid))

    if has_unbounded_collision or not has_explicit_collection:
        return None
    return allowed_ids


def _collect_direct_static_dependency_objects(task_object):
    if task_object is None:
        return []

    found = []
    found.extend(_collect_constraint_pointer_references(task_object))
    for modifier in task_object.modifiers:
        found.extend(_collect_modifier_pointer_references(modifier))
        found.extend(_collect_explicit_physics_collision_objects(modifier))

        if modifier.type != "NODES":
            continue
        node_group = getattr(modifier, "node_group", None)
        if node_group is None:
            continue
        found.extend(_collect_objects_from_node_group(node_group))

    dedup = {}
    for obj in found:
        if int(obj.session_uid) == int(task_object.session_uid):
            continue
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _collect_static_task_dependency_objects(task_object):
    if task_object is None:
        return []

    visited_obj_ids = set()
    queue = [task_object]
    collected = []

    while queue:
        obj = queue.pop(0)
        obj_id = int(obj.session_uid)
        if obj_id in visited_obj_ids:
            continue
        visited_obj_ids.add(obj_id)
        collected.append(obj)

        for ref_obj in _collect_constraint_pointer_references(obj):
            rid = int(ref_obj.session_uid)
            if rid not in visited_obj_ids:
                queue.append(ref_obj)

        for modifier in obj.modifiers:
            for ref_obj in _collect_modifier_pointer_references(modifier):
                rid = int(ref_obj.session_uid)
                if rid not in visited_obj_ids:
                    queue.append(ref_obj)
            for ref_obj in _collect_explicit_physics_collision_objects(modifier):
                rid = int(ref_obj.session_uid)
                if rid not in visited_obj_ids:
                    queue.append(ref_obj)

            if modifier.type != "NODES":
                continue
            node_group = getattr(modifier, "node_group", None)
            if node_group is None:
                continue

            for ref_obj in _collect_objects_from_node_group(node_group):
                rid = int(ref_obj.session_uid)
                if rid not in visited_obj_ids:
                    queue.append(ref_obj)

    return collected


_DG_CLUSTER_START_RE = re.compile(r'^\s*subgraph\s+cluster_[^\s]+\s*\{')
_DG_OBJECT_LABEL_RE = re.compile(r'ID_REF\s*:\s*OB(.+?)\s*\(')
_DG_NODE_RE = re.compile(r'^\s*"(\d+)"\s*\[')
_DG_EDGE_RE = re.compile(r'^\s*"(\d+)"\s*->\s*"(\d+)"')


def _collect_depsgraph_dependency_objects(task_object):
    if task_object is None:
        return []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    dot = depsgraph.debug_relations_graphviz()
    if not dot:
        return []

    stack = []
    node_to_obj_name = {}
    predecessors = {}

    for line in dot.splitlines():
        close_count = line.count("}")
        if _DG_CLUSTER_START_RE.match(line):
            stack.append({"obj_name": None})

        obj_match = _DG_OBJECT_LABEL_RE.search(line)
        if obj_match and stack:
            stack[-1]["obj_name"] = obj_match.group(1)

        node_match = _DG_NODE_RE.match(line)
        if node_match:
            node_id = node_match.group(1)
            obj_name = None
            for ctx in reversed(stack):
                if ctx.get("obj_name") is not None:
                    obj_name = ctx["obj_name"]
                    break
            if obj_name is not None:
                node_to_obj_name[node_id] = obj_name

        edge_match = _DG_EDGE_RE.match(line)
        if edge_match:
            src, dst = edge_match.group(1), edge_match.group(2)
            predecessors.setdefault(dst, set()).add(src)

        for _ in range(close_count):
            if stack:
                stack.pop()

    target_name = task_object.name
    target_nodes = [node_id for node_id, obj_name in node_to_obj_name.items() if obj_name == target_name]
    if not target_nodes:
        return []

    visited_nodes = set(target_nodes)
    queue = list(target_nodes)
    while queue:
        current = queue.pop(0)
        for pred in predecessors.get(current, ()):
            if pred in visited_nodes:
                continue
            visited_nodes.add(pred)
            queue.append(pred)

    result = []
    seen_ids = set()
    for node_id in visited_nodes:
        obj_name = node_to_obj_name.get(node_id)
        if obj_name is None or obj_name == target_name:
            continue
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            continue
        obj_id = int(obj.session_uid)
        if obj_id in seen_ids:
            continue
        seen_ids.add(obj_id)
        result.append(obj)
    return result


def _collect_direct_depsgraph_dependency_objects(task_object):
    if task_object is None:
        return []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    dot = depsgraph.debug_relations_graphviz()
    if not dot:
        return []

    stack = []
    node_to_obj_name = {}
    predecessors = {}

    for line in dot.splitlines():
        close_count = line.count("}")
        if _DG_CLUSTER_START_RE.match(line):
            stack.append({"obj_name": None})

        obj_match = _DG_OBJECT_LABEL_RE.search(line)
        if obj_match and stack:
            stack[-1]["obj_name"] = obj_match.group(1)

        node_match = _DG_NODE_RE.match(line)
        if node_match:
            node_id = node_match.group(1)
            obj_name = None
            for ctx in reversed(stack):
                if ctx.get("obj_name") is not None:
                    obj_name = ctx["obj_name"]
                    break
            if obj_name is not None:
                node_to_obj_name[node_id] = obj_name

        edge_match = _DG_EDGE_RE.match(line)
        if edge_match:
            src, dst = edge_match.group(1), edge_match.group(2)
            predecessors.setdefault(dst, set()).add(src)

        for _ in range(close_count):
            if stack:
                stack.pop()

    target_name = task_object.name
    target_nodes = [node_id for node_id, obj_name in node_to_obj_name.items() if obj_name == target_name]
    if not target_nodes:
        return []

    distances = {}
    queue = [(node_id, 0) for node_id in target_nodes]
    visited = set(target_nodes)
    while queue:
        current, depth = queue.pop(0)
        for pred in predecessors.get(current, ()):
            if pred in visited:
                continue
            visited.add(pred)
            next_depth = depth + 1
            queue.append((pred, next_depth))
            obj_name = node_to_obj_name.get(pred)
            if obj_name is None or obj_name == target_name:
                continue
            previous = distances.get(obj_name)
            if previous is None or next_depth < previous:
                distances[obj_name] = next_depth

    if not distances:
        return []

    min_depth = min(distances.values())
    result = []
    seen_ids = set()
    for obj_name, depth in distances.items():
        if depth != min_depth:
            continue
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            continue
        obj_id = int(obj.session_uid)
        if obj_id in seen_ids:
            continue
        seen_ids.add(obj_id)
        result.append(obj)
    return result


def _collect_task_dependency_objects(task_object, strategy):
    static_objs = _collect_static_task_dependency_objects(task_object)
    if strategy != "STATIC_PLUS_DEPSGRAPH":
        return static_objs

    collision_filter_ids = _collect_explicit_physics_collision_filter_ids(task_object)
    depsgraph_objs = _collect_depsgraph_dependency_objects(task_object)
    dedup = {int(obj.session_uid): obj for obj in static_objs}
    for obj in depsgraph_objs:
        if (
            collision_filter_ids is not None
            and _object_has_collision_modifier(obj)
            and int(obj.session_uid) not in collision_filter_ids
        ):
            continue
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())


def _collect_direct_task_dependency_objects(task_object, strategy):
    static_objs = _collect_direct_static_dependency_objects(task_object)
    if strategy != "STATIC_PLUS_DEPSGRAPH":
        return static_objs

    collision_filter_ids = _collect_explicit_physics_collision_filter_ids(task_object)
    depsgraph_objs = _collect_direct_depsgraph_dependency_objects(task_object)
    dedup = {int(obj.session_uid): obj for obj in static_objs}
    for obj in depsgraph_objs:
        if (
            collision_filter_ids is not None
            and _object_has_collision_modifier(obj)
            and int(obj.session_uid) not in collision_filter_ids
        ):
            continue
        dedup[int(obj.session_uid)] = obj
    return list(dedup.values())
