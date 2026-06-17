import bpy
from mathutils import Matrix, Quaternion

from ...runtime_core.constants import FlowExecutionError, OBJECT_PERSISTENT_UUID_PROP
from ...runtime_math.values import _matrix_to_payload, _quaternion_to_payload


class RuntimeSceneLookupMixin:
    def _cache_object_lookup_entry(self, obj):
        if obj is None:
            return None
        try:
            object_id = int(getattr(obj, "session_uid", 0) or 0)
        except Exception:
            object_id = 0
        object_name = str(getattr(obj, "name", "") or "").strip()
        object_uuid = ""
        try:
            object_uuid = str(obj.get(OBJECT_PERSISTENT_UUID_PROP, "") or "").strip()
        except Exception:
            object_uuid = ""
        if object_id:
            self._object_lookup_cache[("ID", object_id)] = obj
        if object_name:
            self._object_lookup_cache[("NAME", object_name)] = obj
        if object_uuid:
            self._object_lookup_cache[("UUID", object_uuid)] = obj
        return obj

    def _cached_object_lookup_hit(self, cache_key, validator):
        cached = self._object_lookup_cache.get(cache_key)
        if cached is None:
            return None
        try:
            if validator(cached):
                return cached
        except Exception:
            pass
        self._object_lookup_cache.pop(cache_key, None)
        return None

    def _find_object_by_item_cached(self, item):
        if not isinstance(item, dict):
            return None
        try:
            target_id = int(item.get("id", 0) or 0)
        except Exception:
            target_id = 0
        target_name = str(item.get("name", "") or "").strip()
        target_uuid = str(item.get("uuid", "") or item.get("object_uuid", "") or "").strip()
        if target_uuid:
            cached = self._cached_object_lookup_hit(
                ("UUID", target_uuid),
                lambda obj: str(obj.get(OBJECT_PERSISTENT_UUID_PROP, "") or "").strip() == target_uuid,
            )
            if cached is not None:
                return cached
            for obj in bpy.data.objects:
                try:
                    if str(obj.get(OBJECT_PERSISTENT_UUID_PROP, "") or "").strip() == target_uuid:
                        return self._cache_object_lookup_entry(obj)
                except Exception:
                    continue
        if target_name:
            cached = self._cached_object_lookup_hit(
                ("NAME", target_name),
                lambda obj: str(getattr(obj, "name", "") or "").strip() == target_name,
            )
            if cached is not None:
                return cached
            obj = bpy.data.objects.get(target_name)
            if obj is not None:
                return self._cache_object_lookup_entry(obj)
        if target_id:
            cached = self._cached_object_lookup_hit(
                ("ID", target_id),
                lambda obj: int(getattr(obj, "session_uid", 0) or 0) == target_id,
            )
            if cached is not None:
                return cached
            for obj in bpy.data.objects:
                try:
                    if int(getattr(obj, "session_uid", 0) or 0) == target_id:
                        return self._cache_object_lookup_entry(obj)
                except Exception:
                    continue
        return None

    def _resolve_collection_items(self, payload):
        items = payload.get("items", []) if payload else []
        resolved = []
        for item in items:
            name = item["name"]
            collection = bpy.data.collections.get(name)
            if collection:
                resolved.append(collection)
        return resolved

    def _resolve_target_collections(self, node, input_name="Collection List", fallback_attr="target_collection", default_scene_root=False):
        resolved = []
        linked_payload = self._get_linked_output(node, input_name, "collection_list") if input_name else None
        if linked_payload:
            resolved.extend(self._resolve_collection_items(linked_payload))
        fallback_collection = getattr(node, fallback_attr, None) if fallback_attr else None
        if fallback_collection is not None:
            resolved.append(fallback_collection)
        if not resolved and default_scene_root and self.scene is not None:
            scene_collection = getattr(self.scene, "collection", None)
            if scene_collection is not None:
                resolved.append(scene_collection)
        deduped = []
        seen_ids = set()
        for collection in resolved:
            collection_id = int(getattr(collection, "session_uid", 0) or 0)
            if collection_id in seen_ids:
                continue
            seen_ids.add(collection_id)
            deduped.append(collection)
        return deduped

    def _handle_missing_object_action(self, node, obj_name, context_message):
        if str(getattr(node, "missing_policy", "WARN_AND_SKIP") or "WARN_AND_SKIP") == "FAIL":
            raise FlowExecutionError("AF_E008", f"Object '{obj_name}' missing while {context_message}", node.name)
        self.log("WARN", f"Object '{obj_name}' missing while {context_message}, skipping", node.name)
        return False

    def _read_geometry_attribute_element_value(self, node, attribute, data_type, element_index):
        data = getattr(attribute, "data", None)
        try:
            item = data[int(element_index)]
        except Exception:
            raise FlowExecutionError(
                "AF_E020",
                f"Element Index {int(element_index)} is out of range for attribute '{str(getattr(attribute, 'name', '') or '')}'",
                node.name,
            )

        if data_type == "BOOLEAN":
            return "BOOLEAN", bool(getattr(item, "value", False))
        if data_type == "INT":
            return "INTEGER", int(getattr(item, "value", 0))
        if data_type == "FLOAT":
            return "FLOAT", float(getattr(item, "value", 0.0))
        if data_type == "FLOAT_VECTOR":
            return "VECTOR", tuple(float(component) for component in getattr(item, "vector", (0.0, 0.0, 0.0))[:3])
        if data_type == "QUATERNION":
            quat = Quaternion(tuple(float(component) for component in getattr(item, "value", (1.0, 0.0, 0.0, 0.0))[:4]))
            return "ROTATION", _quaternion_to_payload(quat)
        if data_type == "FLOAT4X4":
            matrix_rows = tuple(tuple(float(component) for component in row) for row in getattr(item, "value", Matrix.Identity(4)))
            return "MATRIX", _matrix_to_payload(Matrix(matrix_rows))
        if data_type in {"FLOAT_COLOR", "BYTE_COLOR"}:
            return "VECTOR", tuple(float(component) for component in getattr(item, "color", (0.0, 0.0, 0.0, 1.0))[:3])
        raise FlowExecutionError("AF_E020", f"Attribute '{str(getattr(attribute, 'name', '') or '')}' uses unsupported type '{data_type}'", node.name)


__all__ = ["RuntimeSceneLookupMixin"]
