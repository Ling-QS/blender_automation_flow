from mathutils import Vector

from ...node_system.socket_aliases import find_node_input_socket
from ...node_system.socket_aliases import PROPERTY_ASSIGNMENT_SOCKET_NAME
from ...node_system.socket_aliases import PROPERTY_DEFINITION_SOCKET_NAME
from ...runtime_core.constants import GROUP_INPUT_DEFAULT_MISSING, FlowExecutionError
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_property.definitions import (
    _property_assignment_to_definition_payload,
    _property_definition_to_assignment,
)
from ...runtime_task_ref import _build_auto_flow_bake_task_ref_fallback
from ...runtime_persistence.serialization import _copy_runtime_state_value
from ...runtime_math.values import _matrix_to_payload, _quaternion_to_payload


class RuntimeLinksMixin:
    def _input_socket(self, node, *names):
        return find_node_input_socket(node, *names)

    def _resolve_group_input_parent_socket(self, group_input_node, from_socket, group_path):
        if not group_path:
            return None, None, []

        parent_group_node = None
        parent_group_path = list(group_path[:-1])
        target_tree = getattr(group_input_node, "id_data", None)
        for index in range(len(group_path) - 1, -1, -1):
            candidate = self._resolve_step_ref(group_path[index], group_input_node.name)
            if getattr(candidate, "group_tree", None) == target_tree:
                parent_group_node = candidate
                parent_group_path = list(group_path[:index])
                break
        if parent_group_node is None:
            return None, None, []

        socket_index = -1
        for index, socket in enumerate(group_input_node.outputs):
            if socket == from_socket:
                socket_index = index
                break
        if socket_index < 0 or socket_index >= len(parent_group_node.inputs):
            return None, None, []

        parent_input_socket = parent_group_node.inputs[socket_index]
        return parent_group_node, parent_input_socket, parent_group_path

    def _resolve_group_input_source(self, group_input_node, from_socket, group_path):
        _parent_group_node, parent_input_socket, parent_group_path = self._resolve_group_input_parent_socket(group_input_node, from_socket, group_path)
        if parent_input_socket is None:
            return None, None, []
        upstream_node, upstream_socket = _find_single_from_input_socket(parent_input_socket)
        return upstream_node, upstream_socket, parent_group_path

    def _socket_default_output_value(self, socket, output_key):
        if socket is None or not output_key:
            return GROUP_INPUT_DEFAULT_MISSING

        try:
            default_value = getattr(socket, "default_value")
        except Exception:
            return GROUP_INPUT_DEFAULT_MISSING

        try:
            if output_key == "bool_value":
                return bool(default_value)
            if output_key in {"int_value", "frame", "frame_start", "frame_end", "count"}:
                return int(default_value)
            if output_key in {"float_value", "float_x", "float_y", "float_z"}:
                if output_key == "float_x":
                    return float(Vector(default_value).x)
                if output_key == "float_y":
                    return float(Vector(default_value).y)
                if output_key == "float_z":
                    return float(Vector(default_value).z)
                return float(default_value)
            if output_key == "vector_value":
                vector = Vector(default_value)
                return (float(vector.x), float(vector.y), float(vector.z))
            if output_key == "rotation_value":
                return _quaternion_to_payload(default_value)
            if output_key == "matrix_value":
                return _matrix_to_payload(default_value)
            if output_key in {
                "string_value",
                "status",
                "display_type_value",
                "rotation_mode_value",
            }:
                return str(default_value)
        except Exception:
            return GROUP_INPUT_DEFAULT_MISSING

        return GROUP_INPUT_DEFAULT_MISSING

    def _resolve_group_input_default_output(self, group_input_node, from_socket, output_key, group_path):
        _parent_group_node, parent_input_socket, _parent_group_path = self._resolve_group_input_parent_socket(group_input_node, from_socket, group_path)
        if parent_input_socket is None or bool(getattr(parent_input_socket, "is_linked", False)):
            return GROUP_INPUT_DEFAULT_MISSING

        source_keys = list(self._socket_output_keys(parent_input_socket))
        socket_name = str(getattr(from_socket, "name", "") or "")
        if output_key == "float_value":
            if socket_name == "X":
                source_keys = ["float_x", "float_value"] + [key for key in source_keys if key not in {"float_x", "float_value"}]
            elif socket_name == "Y":
                source_keys = ["float_y", "float_value"] + [key for key in source_keys if key not in {"float_y", "float_value"}]
            elif socket_name == "Z":
                source_keys = ["float_z", "float_value"] + [key for key in source_keys if key not in {"float_z", "float_value"}]

        for source_key in source_keys:
            raw_value = self._socket_default_output_value(parent_input_socket, source_key)
            if raw_value is GROUP_INPUT_DEFAULT_MISSING:
                continue
            if output_key == "string_value" and source_key == "status":
                return str(raw_value)
            if output_key == "status" and source_key == "string_value":
                return str(raw_value)
            coerced = self._coerce_numeric_output_value(source_key, output_key, raw_value)
            if coerced is not None:
                return coerced
            if source_key == output_key:
                return _copy_runtime_state_value(raw_value)

        value = self._socket_default_output_value(parent_input_socket, output_key)
        if value is not GROUP_INPUT_DEFAULT_MISSING:
            return _copy_runtime_state_value(value)
        return GROUP_INPUT_DEFAULT_MISSING

    def _resolve_group_output_source(self, group_node, from_socket, group_path):
        group_tree = getattr(group_node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
            return None, None, []

        group_outputs = self._find_task_group_nodes(group_tree, "NodeGroupOutput")
        if len(group_outputs) != 1:
            return None, None, []
        group_output_node = group_outputs[0]

        socket_index = -1
        for index, socket in enumerate(group_node.outputs):
            if socket == from_socket:
                socket_index = index
                break
        if socket_index < 0 or socket_index >= len(group_output_node.inputs):
            return None, None, []

        group_output_input_socket = group_output_node.inputs[socket_index]
        upstream_node, upstream_socket = _find_single_from_input_socket(group_output_input_socket)
        if upstream_node is None:
            return None, None, []

        child_group_path = list(group_path or [])
        child_group_path.append(self._make_step_ref(group_node))
        return upstream_node, upstream_socket, child_group_path

    def _trace_output_source(self, from_node, from_socket, group_path=None, output_key=None):
        active_group_path = list(self.current_group_path if group_path is None else group_path)
        if from_node is None:
            return None, None, active_group_path

        if from_node.bl_idname == "NodeGroupInput":
            upstream_node, upstream_socket, parent_group_path = self._resolve_group_input_source(from_node, from_socket, active_group_path)
            if upstream_node is None:
                return from_node, from_socket, active_group_path
            return self._trace_output_source(upstream_node, upstream_socket, parent_group_path, output_key)

        if from_node.bl_idname == "AFNodeGroup":
            upstream_node, upstream_socket, child_group_path = self._resolve_group_output_source(from_node, from_socket, active_group_path)
            if upstream_node is not None:
                return self._trace_output_source(upstream_node, upstream_socket, child_group_path, output_key)

        return from_node, from_socket, active_group_path

    def _get_output_from_source(self, from_node, from_socket, output_key, group_path=None):
        resolved_node, resolved_socket, active_group_path = self._trace_output_source(from_node, from_socket, group_path, output_key)
        if resolved_node is None:
            return None

        from_node = resolved_node
        from_socket = resolved_socket

        if from_node.bl_idname == "NodeGroupInput":
            default_value = self._resolve_group_input_default_output(from_node, from_socket, output_key, active_group_path)
            if default_value is not GROUP_INPUT_DEFAULT_MISSING:
                return default_value

        value = self._resolve_output_value(from_node, from_socket, output_key, active_group_path)
        if value is not None:
            return value

        if output_key == "property_assignment":
            definition_value = self._resolve_output_value(from_node, from_socket, "property_definition", active_group_path)
            if definition_value is not None:
                return _property_definition_to_assignment(definition_value, str(getattr(from_node, "name", "") or PROPERTY_ASSIGNMENT_SOCKET_NAME))
        if output_key == "property_definition":
            assignment_value = self._resolve_output_value(from_node, from_socket, "property_assignment", active_group_path)
            if assignment_value is not None:
                return _property_assignment_to_definition_payload(assignment_value, str(getattr(from_node, "name", "") or PROPERTY_DEFINITION_SOCKET_NAME))

        if from_node.bl_idname in self.DATA_NODE_TYPES:
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(active_group_path)
            try:
                self._evaluate_data_node(from_node)
            finally:
                self.current_group_path = previous_group_path

        value = self._resolve_output_value(from_node, from_socket, output_key, active_group_path)
        if value is not None:
            return value

        if output_key == "property_assignment":
            definition_value = self._resolve_output_value(from_node, from_socket, "property_definition", active_group_path)
            if definition_value is not None:
                return _property_definition_to_assignment(definition_value, str(getattr(from_node, "name", "") or PROPERTY_ASSIGNMENT_SOCKET_NAME))
        if output_key == "property_definition":
            assignment_value = self._resolve_output_value(from_node, from_socket, "property_assignment", active_group_path)
            if assignment_value is not None:
                return _property_assignment_to_definition_payload(assignment_value, str(getattr(from_node, "name", "") or PROPERTY_DEFINITION_SOCKET_NAME))

        if output_key == "task_ref":
            direct_task_ref = self._build_direct_task_ref_output(from_node)
            if direct_task_ref is not None:
                safe_task_ref = _copy_runtime_state_value(direct_task_ref)
                self._set_output(from_node, "task_ref", safe_task_ref)
                return safe_task_ref

        if from_node.bl_idname == "AFNodeStorePropertyPackage" and output_key in {"property_package", "report"}:
            property_package, report = self._preview_store_property_package_outputs(from_node, active_group_path)
            if output_key == "property_package" and property_package is not None:
                return property_package
            if output_key == "report" and report is not None:
                return report

        return None

    def _build_direct_task_ref_output(self, node):
        if node is None:
            return None
        node_type = str(getattr(node, "bl_idname", "") or "")
        try:
            if node_type == "AFNodeAutoFlowBakeTarget":
                return _build_auto_flow_bake_task_ref_fallback(self, node)
            if node_type == "AFNodeBakeTask":
                return self._build_geometry_task_ref(node)
            if node_type in {"AFNodeRenderTarget", "AFNodeRenderTask"}:
                return self._build_render_task_ref(node)
            if node_type == "AFNodePhysicsBakeTask":
                return self._build_physics_bake_all_task_ref(node)
        except FlowExecutionError as exc:
            return self._make_invalid_task_ref_payload(node, exc)
        except Exception as exc:
            return self._make_invalid_task_ref_payload(node, exc)
        return None

    def _get_linked_output(self, node, input_name, output_key):
        input_socket = self._input_socket(node, input_name)
        if input_socket is None:
            return None
        from_node, from_socket = _find_single_from_input_socket(input_socket)
        if from_node is None:
            return None
        value = self._get_output_from_source(from_node, from_socket, output_key)
        if value is not None:
            return value
        if getattr(from_node, "bl_idname", "") == "AFNodeStorePropertyPackage" and output_key in {"property_package", "report"}:
            property_package, report = self._preview_store_property_package_outputs(from_node)
            if output_key == "property_package":
                return property_package
            return report
        return None


__all__ = ["RuntimeLinksMixin"]
