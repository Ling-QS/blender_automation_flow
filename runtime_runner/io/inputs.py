from mathutils import Matrix, Quaternion, Vector

from ...runtime_core.constants import FlowExecutionError
from ...runtime_math.values import (
    _identity_matrix_payload,
    _identity_rotation_payload,
    _is_matrix_payload,
    _is_rotation_payload,
    _payload_to_matrix,
    _payload_to_quaternion,
)


class RuntimeInputsMixin:
    def _input_socket_default(self, node, input_name, fallback):
        socket = node.inputs.get(input_name)
        if socket is None:
            return fallback
        return getattr(socket, "default_value", fallback)

    def _input_float(self, node, input_name, fallback=0.0):
        linked = self._get_linked_output(node, input_name, "float_value")
        if linked is not None:
            return float(linked)
        return float(self._input_socket_default(node, input_name, fallback))

    def _input_int(self, node, input_name, fallback=0):
        linked = self._get_linked_output(node, input_name, "int_value")
        if linked is not None:
            return int(linked)
        return int(self._input_socket_default(node, input_name, fallback))

    def _input_bool(self, node, input_name, fallback=False):
        linked = self._get_linked_output(node, input_name, "bool_value")
        if linked is not None:
            return bool(linked)
        return bool(self._input_socket_default(node, input_name, fallback))

    def _input_string(self, node, input_name, fallback=""):
        linked = self._get_linked_output(node, input_name, "string_value")
        if linked is not None:
            return str(linked)
        return str(self._input_socket_default(node, input_name, fallback))

    def _input_string_forgiving(self, node, input_name, fallback=""):
        try:
            return self._input_string(node, input_name, fallback)
        except FlowExecutionError:
            return str(fallback)

    def _playback_state_snapshot(self):
        snapshot = dict(self.ui_context.get("playback_state", {}) or {})
        if "playing" not in snapshot:
            try:
                from ... import operators as operators_module

                snapshot["playing"] = bool(getattr(operators_module, "_is_animation_playing", lambda: False)())
            except Exception:
                snapshot["playing"] = False
        snapshot["on_play"] = bool(snapshot.get("on_play", False))
        snapshot["on_pause"] = bool(snapshot.get("on_pause", False))
        snapshot["playing"] = bool(snapshot.get("playing", False))
        return snapshot

    def _input_vector(self, node, input_name, fallback=(0.0, 0.0, 0.0)):
        linked = self._get_linked_output(node, input_name, "vector_value")
        if linked is not None:
            return Vector(linked)
        value = self._input_socket_default(node, input_name, fallback)
        return Vector(value)

    def _cached_runtime_rotation(self, value):
        if isinstance(value, Quaternion):
            return value
        cache_key = None
        if _is_rotation_payload(value):
            cache_key = ("ROTATION_PAYLOAD", id(value))
        if cache_key is None:
            return _payload_to_quaternion(value)
        cached = self._runtime_rotation_cache.get(cache_key)
        if cached is not None:
            return cached
        cached = _payload_to_quaternion(value)
        self._runtime_rotation_cache[cache_key] = cached
        return cached

    def _input_rotation(self, node, input_name, fallback=None):
        linked = self._get_linked_output(node, input_name, "rotation_value")
        if linked is not None:
            return self._cached_runtime_rotation(linked)
        if fallback is None:
            fallback = self._input_socket_default(node, input_name, _identity_rotation_payload())
        return self._cached_runtime_rotation(fallback)

    def _cached_runtime_matrix(self, value):
        if isinstance(value, Matrix):
            return value
        cache_key = None
        if _is_matrix_payload(value):
            cache_key = ("MATRIX_PAYLOAD", id(value))
        if cache_key is None:
            return _payload_to_matrix(value)
        cached = self._runtime_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        cached = _payload_to_matrix(value)
        self._runtime_matrix_cache[cache_key] = cached
        return cached

    def _input_matrix(self, node, input_name, fallback=None):
        linked = self._get_linked_output(node, input_name, "matrix_value")
        if linked is not None:
            return self._cached_runtime_matrix(linked)
        if fallback is None:
            fallback = self._input_socket_default(node, input_name, _identity_matrix_payload())
        return self._cached_runtime_matrix(fallback)

    def _input_display_type(self, node, input_name, fallback="TEXTURED"):
        linked = self._get_linked_output(node, input_name, "display_type_value")
        if linked is not None:
            return str(linked or fallback)
        return str(getattr(node, "target_display_type", fallback) or fallback)

    def _input_rotation_mode(self, node, input_name, fallback="XYZ"):
        linked = self._get_linked_output(node, input_name, "rotation_mode_value")
        if linked is not None:
            return str(linked or fallback)
        return str(getattr(node, "target_rotation_mode", fallback) or fallback)


__all__ = ["RuntimeInputsMixin"]
