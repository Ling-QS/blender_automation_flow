import copy
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from ...runtime_core.constants import FlowExecutionError
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_property.definitions import _make_empty_property_assignment
from ...runtime_scene.objects import _obj_item
from ...runtime_math.values import (
    _context_reduce_output_key_for_type,
    _identity_matrix_payload,
    _identity_rotation_payload,
    _matrix_to_payload,
    _median_numeric,
    _population_variance,
    _sample_object_index_output_key_for_mode,
)


class RuntimeContextSamplingMixin:
    def _context_reduce_object_items_signature(self, object_items):
        signature = []
        for item in list(object_items or []):
            if not isinstance(item, dict):
                signature.append(("", 0, ""))
                continue
            try:
                object_id = int(item.get("id", 0) or 0)
            except Exception:
                object_id = 0
            signature.append(
                (
                    str(item.get("uuid", "") or ""),
                    object_id,
                    str(item.get("name", "") or ""),
                )
            )
        return tuple(signature)

    def _context_reduce_source_signature(self, from_node, from_socket):
        if from_node is None or from_socket is None:
            return ("DEFAULT",)
        socket_identifier = str(getattr(from_socket, "identifier", "") or getattr(from_socket, "name", "") or "")
        tree_name = str(getattr(getattr(from_node, "id_data", None), "name", "") or "")
        return (
            tree_name,
            self._node_identity(from_node),
            socket_identifier,
            bool(getattr(from_socket, "is_output", False)),
        )

    def _context_reduce_cache_key(self, node, object_items, value_type, operation, vector_mode, output_key, from_node, from_socket):
        return (
            self._node_identity(node),
            self._group_path_key(self.current_group_path),
            self._context_reduce_object_items_signature(object_items),
            str(value_type or "FLOAT"),
            str(operation or "AVERAGE"),
            str(vector_mode or "COMPONENTS"),
            str(output_key or ""),
            self._context_reduce_source_signature(from_node, from_socket),
        )

    def _context_selected_object_item(self, node):
        context = dict(self.current_property_context or {})
        context_items = list(self._current_property_context_items())
        if not context_items:
            context_item = self._current_property_context_item()
            fallback_index = int(context.get("object_index", 0)) if isinstance(context, dict) else 0
            return (copy.deepcopy(context_item) if isinstance(context_item, dict) and context_item else None, fallback_index)

        requested_index = int(context.get("object_index", 0)) if isinstance(context, dict) else 0
        index_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Object Index")
        if index_socket is not None and _find_single_from_input_socket(index_socket)[0] is not None:
            requested_index = self._input_int(node, "Object Index", requested_index)
        clamped_index = max(0, min(int(requested_index), len(context_items) - 1))
        return copy.deepcopy(context_items[clamped_index]), clamped_index

    def _geometry_attribute_source_object(self, node, group_path=None):
        object_list = None
        object_list_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Object List")
        if object_list_socket is not None:
            from_node, from_socket = _find_single_from_input_socket(object_list_socket)
            if from_node is not None:
                object_list = self._get_output_from_source(from_node, from_socket, "object_list", group_path)
        if object_list is None:
            object_list = self._get_linked_output(node, "Object List", "object_list")
        if isinstance(object_list, dict):
            items = list(object_list.get("items", []))
            if items:
                obj = self._find_object_by_item_cached(items[0])
                if obj is not None:
                    return obj, copy.deepcopy(items[0]), int(object_list.get("count", len(items)) or len(items))
        target_object = getattr(node, "target_object", None)
        if target_object is not None:
            item = _obj_item(target_object)
            return target_object, item, 1
        return None, None, 0

    def _sample_object_index_default_value(self, node):
        mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
        value_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Value")
        default_value = getattr(value_socket, "default_value", None) if value_socket is not None else None
        if mode == "BOOLEAN":
            return bool(default_value) if default_value is not None else False
        if mode == "INTEGER":
            return int(default_value) if default_value is not None else 0
        if mode == "VECTOR":
            fallback = default_value if default_value is not None else (0.0, 0.0, 0.0)
            return tuple(float(component) for component in Vector(fallback))
        if mode == "ROTATION":
            return _identity_rotation_payload()
        if mode == "MATRIX":
            return _identity_matrix_payload()
        if mode == "PROPERTY_ASSIGNMENT":
            return None
        return float(default_value) if default_value is not None else 0.0

    def _sample_object_index_value(self, node):
        object_list = self._get_linked_output(node, "Object List", "object_list")
        object_items = list(object_list.get("items", [])) if isinstance(object_list, dict) else []
        if not object_items:
            return self._sample_object_index_default_value(node)

        requested_index = self._input_int(node, "Object Index", 0)
        clamped_index = max(0, min(int(requested_index), len(object_items) - 1))
        obj_item = dict(object_items[clamped_index] or {})
        obj = self._find_object_by_item_cached(obj_item)
        if obj is None:
            return self._sample_object_index_default_value(node)

        value_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Value")
        if value_socket is None:
            return self._sample_object_index_default_value(node)
        from_node, from_socket = _find_single_from_input_socket(value_socket)
        if from_node is None or from_socket is None:
            return self._sample_object_index_default_value(node)

        output_key = _sample_object_index_output_key_for_mode(getattr(node, "mode", "FLOAT"))
        previous_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
        try:
            self.current_property_context = self._make_object_property_context(obj_item, obj, clamped_index, len(object_items), object_items)
            sampled_value = self._get_output_from_source(from_node, from_socket, output_key)
        finally:
            self.current_property_context = previous_context

        if sampled_value is None:
            return self._sample_object_index_default_value(node)
        return copy.deepcopy(sampled_value)

    def _sample_context_data_real_inputs(self, node):
        return [
            socket
            for socket in getattr(node, "inputs", [])
            if str(getattr(socket, "bl_idname", "") or "") == "AFSocketPreviewData"
            and not bool(getattr(socket, "af_is_virtual", False))
        ]

    def _sample_context_data_output_default(self, node, output_socket):
        output_keys = tuple(self._socket_output_keys(output_socket))
        if "property_assignment" in output_keys:
            return _make_empty_property_assignment(node.name)
        if "display_type_value" in output_keys:
            return str(getattr(output_socket, "default_value", "TEXTURED") or "TEXTURED")
        if "object_interaction_mode_value" in output_keys:
            return str(getattr(output_socket, "default_value", "OBJECT") or "OBJECT")
        if "rotation_mode_value" in output_keys:
            return str(getattr(output_socket, "default_value", "XYZ") or "XYZ")
        if "viewport_shading_mode_value" in output_keys:
            return str(getattr(output_socket, "default_value", "SOLID") or "SOLID")
        if "rotation_value" in output_keys:
            return _identity_rotation_payload()
        if "matrix_value" in output_keys:
            return _identity_matrix_payload()
        if "vector_value" in output_keys:
            return (0.0, 0.0, 0.0)
        if "bool_value" in output_keys:
            return False
        if "int_value" in output_keys or "count" in output_keys:
            return 0
        if "float_value" in output_keys:
            return 0.0
        if "string_value" in output_keys or "status" in output_keys:
            return ""
        if hasattr(output_socket, "default_value"):
            try:
                return copy.deepcopy(getattr(output_socket, "default_value"))
            except Exception:
                return getattr(output_socket, "default_value", None)
        return None

    def _sample_context_data_source_items(self, node):
        object_list_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Object List")
        if object_list_socket is not None and bool(getattr(object_list_socket, "is_linked", False)):
            object_list = self._get_linked_output(node, "Object List", "object_list")
            items = []
            if isinstance(object_list, dict):
                for item in list(object_list.get("items", [])):
                    if isinstance(item, dict) and item:
                        items.append(copy.deepcopy(dict(item)))
            return items, "INPUT"

        context_items = list(self._current_property_context_items())
        if context_items:
            return [copy.deepcopy(dict(item)) for item in context_items if isinstance(item, dict) and item], "CONTEXT"
        context_item = self._current_property_context_item()
        if isinstance(context_item, dict) and context_item:
            return [copy.deepcopy(dict(context_item))], "CONTEXT"
        return [], "CONTEXT"

    def _sample_context_data_output_entries(self, node):
        entries = []
        outputs = getattr(node, "outputs", None)
        output_get = getattr(outputs, "get", lambda _name: None)
        for input_socket in self._sample_context_data_real_inputs(node):
            output_socket = output_get(str(getattr(input_socket, "name", "") or ""))
            if output_socket is None or str(getattr(output_socket, "bl_idname", "") or "") == "AFSocketReport":
                continue
            from_node, from_socket = _find_single_from_input_socket(input_socket)
            entries.append((input_socket, output_socket, from_node, from_socket))
        return entries

    def _sample_context_data_resolve_value(self, node, from_node, from_socket):
        if from_node is None or from_socket is None:
            return None
        source_keys = tuple(self._socket_output_keys(from_socket))
        if not source_keys:
            return None
        sampled_value = self._get_output_from_source(from_node, from_socket, source_keys[0])
        if sampled_value is None:
            return None
        if "property_assignment" in source_keys:
            explicitify = getattr(self, "_sample_context_data_explicit_property_assignment", None)
            if callable(explicitify):
                return explicitify(node, sampled_value)
        return copy.deepcopy(sampled_value)

    def _sample_context_data_outputs(self, node):
        output_entries = self._sample_context_data_output_entries(node)
        output_values = {
            str(getattr(output_socket, "name", "") or ""): self._sample_context_data_output_default(node, output_socket)
            for _input_socket, output_socket, _from_node, _from_socket in output_entries
        }
        object_items, object_source = self._sample_context_data_source_items(node)
        requested_index = int(self._input_int(node, "Object Index", 0))
        report = {
            "object_source": str(object_source),
            "object_count": int(len(object_items)),
            "requested_index": int(requested_index),
            "sampled_index": -1,
            "has_valid_object": False,
            "sampled_input_count": int(len(output_entries)),
        }
        if not object_items:
            return output_values, report

        clamped_index = max(0, min(int(requested_index), len(object_items) - 1))
        obj_item = copy.deepcopy(dict(object_items[clamped_index] or {}))
        obj = self._find_object_by_item_cached(obj_item)
        report["sampled_index"] = int(clamped_index)
        report["object_name"] = str(obj_item.get("name", "") or "")
        if obj is None:
            return output_values, report

        previous_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
        try:
            self.current_property_context = self._make_object_property_context(
                obj_item,
                obj,
                clamped_index,
                len(object_items),
                object_items,
                copy_payload=False,
            )
            for _input_socket, output_socket, from_node, from_socket in output_entries:
                sampled_value = self._sample_context_data_resolve_value(node, from_node, from_socket)
                output_name = str(getattr(output_socket, "name", "") or "")
                if sampled_value is None:
                    sampled_value = self._sample_context_data_output_default(node, output_socket)
                output_values[output_name] = copy.deepcopy(sampled_value)
        finally:
            self.current_property_context = previous_context

        report["has_valid_object"] = True
        return output_values, report

    def _context_reduce_items(self):
        context_items = list(self._current_property_context_items())
        if context_items:
            return [dict(item or {}) for item in context_items]
        context_item = self._current_property_context_item()
        if isinstance(context_item, dict) and context_item:
            return [dict(context_item)]
        return []

    def _context_reduce_default_value(self, node):
        value_type = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
        value_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Value")
        default_value = getattr(value_socket, "default_value", None) if value_socket is not None else None
        if value_type == "INTEGER":
            return int(default_value) if default_value is not None else 0
        if value_type == "VECTOR":
            fallback = default_value if default_value is not None else (0.0, 0.0, 0.0)
            return tuple(float(component) for component in Vector(fallback))
        return float(default_value) if default_value is not None else 0.0

    def _context_reduce_constant_result(self, object_items, value_type, operation, vector_mode, sampled_value):
        empty_object_payload = {"items": [], "count": 0, "sort_mode": "CONTEXT"}
        matched_object_payload = copy.deepcopy(empty_object_payload)
        matched_index = -1
        object_count = len(list(object_items or []))
        first_item = dict(object_items[0] or {}) if object_count > 0 and isinstance(object_items[0], dict) else None

        if value_type == "VECTOR":
            vector_value = tuple(float(component) for component in Vector(sampled_value if sampled_value is not None else (0.0, 0.0, 0.0)))
            if operation in {"MINIMUM", "MAXIMUM"}:
                if first_item is not None:
                    matched_index = 0
                    matched_object_payload = {
                        "items": [copy.deepcopy(first_item)],
                        "count": 1,
                        "sort_mode": "CONTEXT",
                    }
                reduced_value = vector_value
            elif operation in {"VARIANCE", "STANDARD_DEVIATION"}:
                reduced_value = (0.0, 0.0, 0.0)
            else:
                reduced_value = vector_value
            report = {
                "value_type": value_type,
                "operation": operation,
                "vector_mode": vector_mode,
                "sample_count": int(object_count),
                "matched_index": int(matched_index),
            }
            return reduced_value, matched_object_payload, matched_index, report

        if value_type == "INTEGER":
            numeric_value = int(sampled_value if sampled_value is not None else 0)
            zero_value = 0
        else:
            numeric_value = float(sampled_value if sampled_value is not None else 0.0)
            zero_value = 0.0

        if operation in {"MINIMUM", "MAXIMUM"}:
            if first_item is not None:
                matched_index = 0
                matched_object_payload = {
                    "items": [copy.deepcopy(first_item)],
                    "count": 1,
                    "sort_mode": "CONTEXT",
                }
            reduced_value = numeric_value
        elif operation in {"VARIANCE", "STANDARD_DEVIATION"}:
            reduced_value = zero_value
        else:
            reduced_value = numeric_value

        report = {
            "value_type": value_type,
            "operation": operation,
            "sample_count": int(object_count),
            "matched_index": int(matched_index),
        }
        return reduced_value, matched_object_payload, matched_index, report

    def _reduce_context_value(self, node):
        object_items = self._context_reduce_items()
        if not object_items:
            raise FlowExecutionError("AF_E011", "Current Property Context has no objects to reduce", node.name)

        value_type = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
        operation = str(getattr(node, "operation", "AVERAGE") or "AVERAGE")
        vector_mode = str(getattr(node, "vector_mode", "COMPONENTS") or "COMPONENTS")
        value_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Value")
        from_node, from_socket = _find_single_from_input_socket(value_socket) if value_socket is not None else (None, None)
        output_key = _context_reduce_output_key_for_type(value_type)
        cache_key = self._context_reduce_cache_key(
            node,
            object_items,
            value_type,
            operation,
            vector_mode,
            output_key,
            from_node,
            from_socket,
        )
        cached_result = getattr(self, "_context_reduce_cache", {}).get(cache_key)
        if cached_result is not None:
            return copy.deepcopy(cached_result)

        source_depends_on_context = False
        if from_node is not None and from_socket is not None:
            try:
                source_depends_on_context = bool(self._source_depends_on_property_context(from_node, from_socket, set()))
            except Exception:
                source_depends_on_context = True
        if not source_depends_on_context:
            if from_node is not None and from_socket is not None:
                sampled_value = self._get_output_from_source(from_node, from_socket, output_key)
            else:
                sampled_value = self._context_reduce_default_value(node)
            if sampled_value is None:
                sampled_value = self._context_reduce_default_value(node)
            result = self._context_reduce_constant_result(
                object_items,
                value_type,
                operation,
                vector_mode,
                sampled_value,
            )
            self._context_reduce_cache[cache_key] = copy.deepcopy(result)
            return result

        previous_context = dict(self.current_property_context or {}) if isinstance(self.current_property_context, dict) else self.current_property_context
        sampled_entries = []
        try:
            object_count = len(object_items)
            for index, obj_item in enumerate(object_items):
                obj = self._find_object_by_item_cached(obj_item)
                if obj is None:
                    continue
                self.current_property_context = self._make_object_property_context(obj_item, obj, index, object_count, object_items, copy_payload=False)
                if from_node is not None and from_socket is not None:
                    sampled_value = self._get_output_from_source(from_node, from_socket, output_key)
                else:
                    sampled_value = self._context_reduce_default_value(node)
                if sampled_value is None:
                    sampled_value = self._context_reduce_default_value(node)
                sampled_entries.append(
                    {
                        "index": int(index),
                        "item": copy.deepcopy(obj_item),
                        "object": obj,
                        "value": copy.deepcopy(sampled_value),
                    }
                )
        finally:
            self.current_property_context = previous_context

        if not sampled_entries:
            raise FlowExecutionError("AF_E001", "No valid objects were available in the current Property Context", node.name)

        empty_object_payload = {"items": [], "count": 0, "sort_mode": "CONTEXT"}
        matched_object_payload = copy.deepcopy(empty_object_payload)
        matched_index = -1

        if value_type == "VECTOR":
            vectors = [Vector(entry["value"]) for entry in sampled_entries]
            if operation in {"MINIMUM", "MAXIMUM"} and vector_mode == "LENGTH":
                lengths = [float(vector.length) for vector in vectors]
                matched_position = lengths.index(min(lengths) if operation == "MINIMUM" else max(lengths))
                matched_entry = sampled_entries[matched_position]
                matched_vector = vectors[matched_position]
                matched_index = int(matched_entry["index"])
                matched_object_payload = {
                    "items": [copy.deepcopy(matched_entry["item"])],
                    "count": 1,
                    "sort_mode": "CONTEXT",
                }
                reduced_value = tuple(float(component) for component in matched_vector)
            else:
                components = list(zip(*[(float(vector.x), float(vector.y), float(vector.z)) for vector in vectors]))
                reduced_components = []
                for component_values in components:
                    values = [float(component) for component in component_values]
                    if operation == "MINIMUM":
                        reduced_components.append(min(values))
                    elif operation == "MAXIMUM":
                        reduced_components.append(max(values))
                    elif operation == "MEDIAN":
                        reduced_components.append(_median_numeric(values))
                    elif operation == "VARIANCE":
                        reduced_components.append(_population_variance(values))
                    elif operation == "STANDARD_DEVIATION":
                        reduced_components.append(math.sqrt(_population_variance(values)))
                    else:
                        reduced_components.append(sum(values) / float(len(values)))
                reduced_value = tuple(float(component) for component in reduced_components)
            report = {
                "value_type": value_type,
                "operation": operation,
                "vector_mode": vector_mode,
                "sample_count": len(sampled_entries),
                "matched_index": int(matched_index),
            }
            result = (reduced_value, matched_object_payload, matched_index, report)
            self._context_reduce_cache[cache_key] = copy.deepcopy(result)
            return result

        numeric_values = []
        for entry in sampled_entries:
            raw_value = entry["value"]
            if value_type == "INTEGER":
                numeric_values.append(int(raw_value))
            else:
                numeric_values.append(float(raw_value))

        matched_entry = None
        if operation == "MINIMUM":
            reduced_numeric = min(numeric_values)
            matched_entry = sampled_entries[numeric_values.index(reduced_numeric)]
        elif operation == "MAXIMUM":
            reduced_numeric = max(numeric_values)
            matched_entry = sampled_entries[numeric_values.index(reduced_numeric)]
        elif operation == "MEDIAN":
            reduced_numeric = _median_numeric(numeric_values)
        elif operation == "VARIANCE":
            reduced_numeric = _population_variance(numeric_values)
        elif operation == "STANDARD_DEVIATION":
            reduced_numeric = math.sqrt(_population_variance(numeric_values))
        else:
            reduced_numeric = float(sum(float(value) for value in numeric_values) / float(len(numeric_values)))

        if matched_entry is not None:
            matched_index = int(matched_entry["index"])
            matched_object_payload = {
                "items": [copy.deepcopy(matched_entry["item"])],
                "count": 1,
                "sort_mode": "CONTEXT",
            }

        if value_type == "INTEGER":
            reduced_value = int(reduced_numeric) if operation in {"MINIMUM", "MAXIMUM"} else int(round(float(reduced_numeric)))
        else:
            reduced_value = float(reduced_numeric)

        report = {
            "value_type": value_type,
            "operation": operation,
            "sample_count": len(sampled_entries),
            "matched_index": int(matched_index),
        }
        result = (reduced_value, matched_object_payload, matched_index, report)
        self._context_reduce_cache[cache_key] = copy.deepcopy(result)
        return result

    def _read_geometry_attribute_value(self, node, obj, attribute_name, element_index):
        if obj is None:
            raise FlowExecutionError("AF_E001", "Source object is missing", node.name)
        if getattr(obj, "type", "") != "MESH":
            raise FlowExecutionError("AF_E020", "Geometry Attribute source object must be a Mesh", node.name)
        attribute_name = str(attribute_name or "").strip()
        if not attribute_name:
            raise FlowExecutionError("AF_E011", "Attribute Name is empty", node.name)
        if int(element_index) < 0:
            raise FlowExecutionError("AF_E020", "Element Index cannot be negative", node.name)

        if str(getattr(obj, "mode", "") or "") == "EDIT":
            try:
                obj.update_from_editmode()
            except Exception:
                pass

        scene_ref = self.scene if self.scene is not None else bpy.context.scene
        frame_current = int(getattr(scene_ref, "frame_current", 0) or 0)
        frame_subframe = float(getattr(scene_ref, "frame_subframe", 0.0) or 0.0)
        cache_key = (
            int(getattr(obj, "session_uid", 0) or 0),
            frame_current,
            round(frame_subframe, 6),
            str(attribute_name),
        )
        cache_entry = self._geometry_attribute_cache.get(cache_key)
        if cache_entry is None:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated_object = obj.evaluated_get(depsgraph)
            mesh = getattr(evaluated_object, "data", None)
            attributes = getattr(mesh, "attributes", None)
            attribute = attributes.get(attribute_name) if attributes is not None and hasattr(attributes, "get") else None
            if attribute is None:
                raise FlowExecutionError("AF_E017", f"Attribute '{attribute_name}' not found", node.name)
            domain = str(getattr(attribute, "domain", "") or "")
            if domain != "POINT":
                raise FlowExecutionError("AF_E020", f"Attribute '{attribute_name}' must be on the Point domain", node.name)
            data_type = str(getattr(attribute, "data_type", "") or "")
            data = getattr(attribute, "data", None)
            try:
                element_count = len(data)
            except Exception:
                element_count = 0
            if element_count <= 0:
                raise FlowExecutionError("AF_E020", f"Attribute '{attribute_name}' has no elements", node.name)
            runtime_type, _sample_value = self._read_geometry_attribute_element_value(node, attribute, data_type, 0)

            cache_entry = {
                "runtime_type": runtime_type,
                "domain": domain,
                "data_type": data_type,
                "attribute": attribute,
                "element_count": int(element_count),
            }
            self._geometry_attribute_cache[cache_key] = cache_entry

        data_length = int(cache_entry.get("element_count", 0) or 0)
        if int(element_index) >= data_length:
            raise FlowExecutionError("AF_E020", f"Element Index {int(element_index)} is out of range for attribute '{attribute_name}'", node.name)
        runtime_type, value = self._read_geometry_attribute_element_value(
            node,
            cache_entry.get("attribute"),
            str(cache_entry.get("data_type", "") or ""),
            int(element_index),
        )
        return {
            "runtime_type": str(runtime_type or cache_entry.get("runtime_type", "") or ""),
            "value": copy.deepcopy(value),
            "domain": str(cache_entry.get("domain", "") or ""),
            "data_type": str(cache_entry.get("data_type", "") or ""),
            "element_count": data_length,
        }

    def _coerce_geometry_attribute_output(self, node, value_payload):
        runtime_type = str(value_payload.get("runtime_type", "") or "")
        selected_mode = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
        value = value_payload.get("value")
        output_mode = selected_mode

        if output_mode == "BOOLEAN":
            if runtime_type not in {"BOOLEAN", "INTEGER", "FLOAT"}:
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Boolean", node.name)
            return output_mode, bool(value)
        if output_mode == "INTEGER":
            if runtime_type not in {"BOOLEAN", "INTEGER", "FLOAT"}:
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Integer", node.name)
            return output_mode, int(value)
        if output_mode == "FLOAT":
            if runtime_type not in {"BOOLEAN", "INTEGER", "FLOAT"}:
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Float", node.name)
            return output_mode, float(value)
        if output_mode == "VECTOR":
            if runtime_type != "VECTOR":
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Vector", node.name)
            return output_mode, tuple(float(component) for component in (value or (0.0, 0.0, 0.0))[:3])
        if output_mode == "ROTATION":
            if runtime_type != "ROTATION":
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Rotation", node.name)
            return output_mode, copy.deepcopy(value) if isinstance(value, dict) else _identity_rotation_payload()
        if output_mode == "MATRIX":
            if runtime_type != "MATRIX":
                raise FlowExecutionError("AF_E020", f"Geometry Attribute cannot convert {runtime_type} to Matrix", node.name)
            return output_mode, copy.deepcopy(value) if isinstance(value, dict) else _matrix_to_payload(Matrix.Identity(4))
        raise FlowExecutionError("AF_E020", f"Geometry Attribute output type '{output_mode}' is not supported", node.name)

    def _geometry_attribute_data_type_for_value_type(self, node, value_type):
        data_type = {
            "BOOLEAN": "BOOLEAN",
            "FLOAT": "FLOAT",
            "INTEGER": "INT",
            "VECTOR": "FLOAT_VECTOR",
            "ROTATION": "QUATERNION",
            "MATRIX": "FLOAT4X4",
        }.get(str(value_type or "FLOAT"), "")
        if data_type:
            return data_type
        raise FlowExecutionError("AF_E020", f"Geometry Attribute value type '{value_type}' is not supported", node.name)

    def _ensure_geometry_attribute(self, node, attributes, attribute_name, data_type, domain, dry_run=False):
        attribute_name = str(attribute_name or "").strip()
        if not attribute_name:
            raise FlowExecutionError("AF_E011", "Attribute Name is empty", node.name)
        attribute = attributes.get(attribute_name) if hasattr(attributes, "get") else None
        created = False
        if attribute is None and not dry_run:
            try:
                attribute = attributes.new(name=attribute_name, type=data_type, domain=domain)
                created = True
            except Exception as exc:
                raise FlowExecutionError("AF_E020", f"Failed to create attribute '{attribute_name}': {exc}", node.name)
        if attribute is not None:
            existing_domain = str(getattr(attribute, "domain", "") or "")
            if existing_domain != str(domain or ""):
                raise FlowExecutionError("AF_E020", f"Attribute '{attribute_name}' must be on the {domain.title()} domain", node.name)
            existing_data_type = str(getattr(attribute, "data_type", "") or "")
            if existing_data_type != str(data_type or ""):
                raise FlowExecutionError(
                    "AF_E020",
                    f"Attribute '{attribute_name}' has type '{existing_data_type}' but expected '{data_type}'",
                    node.name,
                )
        return attribute, created

    def _geometry_attribute_element_count(self, attribute):
        try:
            return int(len(getattr(attribute, "data", None)))
        except Exception:
            return 0

    def _rebuild_geometry_attribute_carrier_mesh(self, node, mesh, point_count):
        if mesh is None:
            raise FlowExecutionError("AF_E020", "Carrier Object mesh data is unavailable", node.name)
        point_count = max(0, int(point_count or 0))
        coordinates = [(float(index), 0.0, 0.0) for index in range(point_count)]
        try:
            if hasattr(mesh, "clear_geometry"):
                mesh.clear_geometry()
            mesh.from_pydata(coordinates, [], [])
            mesh.update()
        except Exception as exc:
            raise FlowExecutionError("AF_E020", f"Failed to rebuild carrier mesh: {exc}", node.name)
        return point_count

    def _geometry_attribute_input_value(self, node):
        value_type = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
        if value_type == "BOOLEAN":
            return bool(self._input_bool(node, "Value", False))
        if value_type == "INTEGER":
            return int(self._input_int(node, "Value", 0))
        if value_type == "VECTOR":
            vector_value = self._input_vector(node, "Value", (0.0, 0.0, 0.0))
            return (float(vector_value.x), float(vector_value.y), float(vector_value.z))
        if value_type == "ROTATION":
            return self._input_rotation(node, "Value")
        if value_type == "MATRIX":
            return self._input_matrix(node, "Value")
        return float(self._input_float(node, "Value", 0.0))

    def _prepare_geometry_attribute_target(self, node, target_object, attribute_name, value_type, expected_count=None, dry_run=False):
        if target_object is None:
            raise FlowExecutionError("AF_E001", "Target Object is missing", node.name)
        if getattr(target_object, "type", "") != "MESH":
            raise FlowExecutionError("AF_E020", "Geometry Attribute target object must be a Mesh", node.name)
        if str(getattr(target_object, "mode", "") or "") == "EDIT":
            raise FlowExecutionError("AF_E020", "Geometry Attribute target object must not be in Edit Mode", node.name)
        attribute_name = str(attribute_name or "").strip()
        if not attribute_name:
            raise FlowExecutionError("AF_E011", "Attribute Name is empty", node.name)

        mesh = getattr(target_object, "data", None)
        attributes = getattr(mesh, "attributes", None) if mesh is not None else None
        if mesh is None or attributes is None:
            raise FlowExecutionError("AF_E020", "Target Object mesh data is unavailable", node.name)

        try:
            point_count = len(getattr(mesh, "vertices", []))
        except Exception:
            point_count = 0
        if expected_count is not None and int(expected_count) != int(point_count):
            raise FlowExecutionError(
                "AF_E020",
                "Object List count must match target mesh point count",
                node.name,
            )

        data_type = self._geometry_attribute_data_type_for_value_type(node, value_type)
        attribute, created = self._ensure_geometry_attribute(
            node,
            attributes,
            attribute_name,
            data_type,
            "POINT",
            dry_run=dry_run,
        )
        if attribute is not None:
            attribute_count = self._geometry_attribute_element_count(attribute)
            if int(attribute_count) != int(point_count):
                raise FlowExecutionError(
                    "AF_E020",
                    "Geometry Attribute point count does not match target mesh point count",
                    node.name,
                )

        return mesh, attribute, created, int(point_count), data_type

    def _prepare_geometry_attribute_carrier_target(
        self,
        node,
        carrier_object,
        attribute_name,
        index_attribute_name,
        value_type,
        expected_count=None,
        dry_run=False,
    ):
        if carrier_object is None:
            raise FlowExecutionError("AF_E001", "Carrier Object is missing", node.name)
        if getattr(carrier_object, "type", "") != "MESH":
            raise FlowExecutionError("AF_E020", "Geometry Attribute carrier object must be a Mesh", node.name)
        if str(getattr(carrier_object, "mode", "") or "") == "EDIT":
            raise FlowExecutionError("AF_E020", "Geometry Attribute carrier object must not be in Edit Mode", node.name)
        attribute_name = str(attribute_name or "").strip()
        if not attribute_name:
            raise FlowExecutionError("AF_E011", "Attribute Name is empty", node.name)
        index_attribute_name = str(index_attribute_name or "").strip()
        if not index_attribute_name:
            raise FlowExecutionError("AF_E011", "Index Attribute Name is empty", node.name)

        mesh = getattr(carrier_object, "data", None)
        attributes = getattr(mesh, "attributes", None) if mesh is not None else None
        if mesh is None or attributes is None:
            raise FlowExecutionError("AF_E020", "Carrier Object mesh data is unavailable", node.name)

        try:
            point_count = len(getattr(mesh, "vertices", []))
        except Exception:
            point_count = 0
        desired_count = int(point_count if expected_count is None else max(0, int(expected_count or 0)))
        rebuilt = False
        will_rebuild = int(point_count) != int(desired_count)
        if will_rebuild and not dry_run:
            point_count = self._rebuild_geometry_attribute_carrier_mesh(node, mesh, desired_count)
            rebuilt = True
            attributes = getattr(mesh, "attributes", None)
            if attributes is None:
                raise FlowExecutionError("AF_E020", "Carrier Object mesh data is unavailable", node.name)
        else:
            point_count = desired_count

        data_type = self._geometry_attribute_data_type_for_value_type(node, value_type)
        attribute, created = self._ensure_geometry_attribute(
            node,
            attributes,
            attribute_name,
            data_type,
            "POINT",
            dry_run=dry_run,
        )
        index_attribute, created_index_attribute = self._ensure_geometry_attribute(
            node,
            attributes,
            index_attribute_name,
            "INT",
            "POINT",
            dry_run=dry_run,
        )

        should_validate_counts = not dry_run or not will_rebuild
        if should_validate_counts:
            if attribute is not None and self._geometry_attribute_element_count(attribute) != int(point_count):
                raise FlowExecutionError(
                    "AF_E020",
                    "Geometry Attribute point count does not match target mesh point count",
                    node.name,
                )
            if index_attribute is not None and self._geometry_attribute_element_count(index_attribute) != int(point_count):
                raise FlowExecutionError(
                    "AF_E020",
                    "Geometry Attribute point count does not match target mesh point count",
                    node.name,
                )

        return (
            mesh,
            attribute,
            created,
            index_attribute,
            created_index_attribute,
            rebuilt,
            int(point_count),
            data_type,
        )

    def _write_geometry_attribute_element_value(self, node, attribute, data_type, element_index, value):
        if attribute is None:
            return
        try:
            item = attribute.data[int(element_index)]
        except Exception:
            raise FlowExecutionError(
                "AF_E020",
                f"Element Index {int(element_index)} is out of range for attribute '{str(getattr(attribute, 'name', '') or '')}'",
                node.name,
            )

        try:
            if data_type == "BOOLEAN":
                item.value = bool(value)
                return
            if data_type == "INT":
                item.value = int(value)
                return
            if data_type == "FLOAT":
                item.value = float(value)
                return
            if data_type == "FLOAT_VECTOR":
                vector_value = Vector(value if value is not None else (0.0, 0.0, 0.0))
                item.vector = (float(vector_value.x), float(vector_value.y), float(vector_value.z))
                return
            if data_type == "QUATERNION":
                quaternion_value = value.copy() if isinstance(value, Quaternion) else Quaternion(tuple(value or (1.0, 0.0, 0.0, 0.0)))
                item.value = quaternion_value
                return
            if data_type == "FLOAT4X4":
                matrix_value = value.copy() if isinstance(value, Matrix) else Matrix(value)
                item.value = matrix_value
                return
        except Exception as exc:
            raise FlowExecutionError(
                "AF_E020",
                f"Failed to write attribute '{str(getattr(attribute, 'name', '') or '')}' at element {int(element_index)}: {exc}",
                node.name,
            )

        raise FlowExecutionError("AF_E020", f"Attribute type '{data_type}' is not supported for writing", node.name)

    def _vector_scalar_component(self, vector_value, mode):
        vector = Vector(vector_value)
        if mode == "Y":
            return float(vector.y)
        if mode == "Z":
            return float(vector.z)
        if mode == "LENGTH":
            return float(vector.length)
        if mode == "AVERAGE":
            return float((vector.x + vector.y + vector.z) / 3.0)
        return float(vector.x)


__all__ = ["RuntimeContextSamplingMixin"]
