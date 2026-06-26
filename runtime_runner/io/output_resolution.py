from mathutils import Vector

from ...runtime_flow.helpers import (
    _numeric_output_key_family,
    _numeric_socket_family,
    _socket_specific_output_key,
    _string_socket_family,
)


class RuntimeOutputResolutionMixin:
    def _socket_output_keys(self, socket):
        if socket is getattr(self, "_last_socket_output_keys_source", None):
            return getattr(self, "_last_socket_output_keys_value", ())
        socket_token = self._socket_cache_token(socket)
        cache = getattr(self, "_socket_output_keys_cache", None)
        if cache is not None and socket_token is not None:
            cached = cache.get(socket_token)
            if cached is not None:
                self._last_socket_output_keys_source = socket
                self._last_socket_output_keys_value = cached
                return cached
        socket_type = _numeric_socket_family(socket) or _string_socket_family(socket) or str(getattr(socket, "bl_idname", "") or "")
        socket_name = str(getattr(socket, "name", "") or "")
        keys = []
        specific_key = _socket_specific_output_key(socket)
        if specific_key:
            keys.append(specific_key)
        if socket_type == "NodeSocketFloat":
            if socket_name == "X":
                keys.append("float_x")
            elif socket_name == "Y":
                keys.append("float_y")
            elif socket_name == "Z":
                keys.append("float_z")
            keys.append("float_value")
        elif socket_type == "NodeSocketInt":
            if socket_name == "Frame":
                keys.append("frame")
            elif socket_name == "Frame Start":
                keys.append("frame_start")
            elif socket_name == "Frame End":
                keys.append("frame_end")
            elif socket_name == "Count":
                keys.append("count")
            keys.append("int_value")
        elif socket_type == "NodeSocketBool":
            keys.append("bool_value")
        elif socket_type == "NodeSocketVector":
            keys.append("vector_value")
        elif socket_type in {"NodeSocketRotation", "AFSocketRotationValue"}:
            keys.append("rotation_value")
        elif socket_type in {"NodeSocketMatrix", "AFSocketMatrixValue"}:
            keys.append("matrix_value")
        else:
            if socket_type == "NodeSocketString":
                if socket_name == "Status":
                    keys.append("status")
                keys.append("string_value")
                value = tuple(keys)
                self._last_socket_output_keys_source = socket
                self._last_socket_output_keys_value = value
                if cache is not None and socket_token is not None:
                    cache[socket_token] = value
                return value
            custom_map = {
                "AFSocketCollectionList": "collection_list",
                "AFSocketObjectList": "object_list",
                "AFSocketDisplayType": "display_type_value",
                "AFSocketObjectInteractionMode": "object_interaction_mode_value",
                "AFSocketRotationMode": "rotation_mode_value",
                "AFSocketViewportShadingMode": "viewport_shading_mode_value",
                "AFSocketPropertyPackage": "property_package",
                "AFSocketPropertyDefinition": "property_definition",
                "AFSocketPropertyAssignment": "property_assignment",
                "AFSocketTaskRef": "task_ref",
                "AFSocketTaskPlan": "task_plan",
                "AFSocketTaskHandle": "task_handle",
                "AFSocketReport": "report",
            }
            key = custom_map.get(socket_type)
            if key:
                keys.append(key)
        value = tuple(keys)
        self._last_socket_output_keys_source = socket
        self._last_socket_output_keys_value = value
        if cache is not None and socket_token is not None:
            cache[socket_token] = value
        return value

    def _coerce_numeric_output_value(self, source_key, target_key, value):
        if value is None:
            return None
        if source_key == target_key:
            return value

        epsilon = 1e-6
        source_family = _numeric_output_key_family(source_key)
        target_family = _numeric_output_key_family(target_key)

        if source_family and target_family and source_family == target_family:
            return value

        bool_like_keys = {"bool_value"}
        int_like_keys = {"int_value", "frame", "frame_start", "frame_end", "count"}
        float_like_keys = {"float_value", "float_x", "float_y", "float_z"}

        if source_family == "NodeSocketBool" or source_key in bool_like_keys:
            bool_value = bool(value)
            if target_family == "NodeSocketInt" or target_key == "int_value":
                return 1 if bool_value else 0
            if target_family == "NodeSocketFloat" or target_key == "float_value":
                return 1.0 if bool_value else 0.0
            if target_family == "NodeSocketVector" or target_key == "vector_value":
                scalar = 1.0 if bool_value else 0.0
                return (scalar, scalar, scalar)
            return None

        if source_family == "NodeSocketInt" or source_key in int_like_keys:
            int_value = int(value)
            if target_family == "NodeSocketInt" or target_key in int_like_keys:
                return int_value
            if target_family == "NodeSocketBool" or target_key == "bool_value":
                return int_value != 0
            if target_family == "NodeSocketFloat" or target_key == "float_value":
                return float(int_value)
            if target_family == "NodeSocketVector" or target_key == "vector_value":
                scalar = float(int_value)
                return (scalar, scalar, scalar)
            return None

        if source_family == "NodeSocketFloat" or source_key in float_like_keys:
            float_value = float(value)
            if target_family == "NodeSocketFloat" or target_key in float_like_keys:
                return float_value
            if target_family == "NodeSocketBool" or target_key == "bool_value":
                return abs(float_value) > epsilon
            if target_family == "NodeSocketInt" or target_key == "int_value":
                return int(float_value)
            if target_family == "NodeSocketVector" or target_key == "vector_value":
                return (float_value, float_value, float_value)
            return None

        if source_family == "NodeSocketVector" or source_key == "vector_value":
            vector = Vector(value)
            if target_family == "NodeSocketBool" or target_key == "bool_value":
                return any(abs(float(component)) > epsilon for component in vector)
            if target_family == "NodeSocketInt" or target_key == "int_value":
                return int(float(vector.x))
            if target_family == "NodeSocketFloat" or target_key == "float_value":
                return float(vector.x)
            return None

        return None

    def _resolve_output_value(self, from_node, from_socket, output_key, group_path=None, allow_missing_fallback=True):
        active_group_path = list(self.current_group_path if group_path is None else group_path)
        source_keys = []
        if from_socket is not None:
            source_keys = self._socket_output_keys(from_socket)

        if output_key == "float_value" and from_socket is not None:
            socket_name = str(getattr(from_socket, "name", "") or "")
            if socket_name == "X":
                source_keys = ["float_x", "float_value"] + [key for key in source_keys if key not in {"float_x", "float_value"}]
            elif socket_name == "Y":
                source_keys = ["float_y", "float_value"] + [key for key in source_keys if key not in {"float_y", "float_value"}]
            elif socket_name == "Z":
                source_keys = ["float_z", "float_value"] + [key for key in source_keys if key not in {"float_z", "float_value"}]

        for source_key in source_keys:
            raw_value = self._get_output(from_node, source_key, active_group_path, normalize=False)
            if raw_value is None:
                continue
            if output_key == "string_value" and source_key == "status":
                return str(raw_value)
            if output_key == "status" and source_key == "string_value":
                return str(raw_value)
            coerced = self._coerce_numeric_output_value(source_key, output_key, raw_value)
            if coerced is not None:
                return coerced
            if source_key == output_key:
                return raw_value

        value = self._get_output(from_node, output_key, active_group_path, normalize=False)
        if (
            allow_missing_fallback
            and value is None
            and from_socket is not None
            and self._socket_supports_output_key(from_socket, output_key)
        ):
            value = self._normalize_output_value(output_key, None, from_node)
        if value is not None:
            return value
        return None


__all__ = ["RuntimeOutputResolutionMixin"]
