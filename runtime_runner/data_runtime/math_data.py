import math
import random
import re

from mathutils import Euler, Matrix, Quaternion, Vector

from ...runtime_core.constants import ROTATION_IDENTITY_QUATERNION
from ...runtime_flow.helpers import _socket_specific_output_key
from ...runtime_math.values import (
    _matrix_to_payload,
    _normalized_vector_or_none,
    _quaternion_to_payload,
    _rotation_align_to_vector,
    _rotation_from_axes,
)


class RuntimeMathDataMixin:
    def _evaluate_math_data_node(self, node, node_type):
        if node_type == "AFNodeFloatInput":
            self._set_scalar_vector_outputs(node, float_value=node.value)
            return True

        if node_type == "AFNodeBooleanInput":
            self._set_scalar_vector_outputs(node, bool_value=node.value)
            return True

        if node_type == "AFNodeVectorInput":
            self._set_scalar_vector_outputs(node, vector_value=Vector((node.x, node.y, node.z)))
            return True

        if node_type == "AFNodeIntegerInput":
            self._set_scalar_vector_outputs(node, int_value=node.value)
            return True

        if node_type == "AFNodeStringInput":
            self._set_output(node, "string_value", str(getattr(node, "value", "") or ""))
            return True

        if node_type == "AFNodeInputRotation":
            rotation_payload = _quaternion_to_payload(
                Euler(
                    tuple(float(value) for value in getattr(node, "rotation_euler", (0.0, 0.0, 0.0))),
                    "XYZ",
                ).to_quaternion()
            )
            self._set_output(node, "rotation_value", rotation_payload)
            return True

        if node_type == "AFNodeStatusInput":
            self._set_output(node, "status", str(getattr(node, "status_value", "DONE") or "DONE"))
            self._set_output(node, "string_value", str(getattr(node, "status_value", "DONE") or "DONE"))
            return True

        if node_type == "AFNodeConvertValue":
            mode = str(node.conversion_mode)
            if mode == "BOOL_TO_INT":
                self._set_scalar_vector_outputs(node, int_value=(1 if self._input_bool(node, "Value", False) else 0))
                return True
            if mode == "BOOL_TO_FLOAT":
                self._set_scalar_vector_outputs(node, float_value=(1.0 if self._input_bool(node, "Value", False) else 0.0))
                return True
            if mode == "BOOL_TO_VECTOR":
                scalar = 1.0 if self._input_bool(node, "Value", False) else 0.0
                self._set_scalar_vector_outputs(node, vector_value=(scalar, scalar, scalar))
                return True
            if mode == "INT_TO_BOOL":
                self._set_scalar_vector_outputs(node, bool_value=(self._input_int(node, "Value", 0) != 0))
                return True
            if mode == "INT_TO_FLOAT":
                self._set_scalar_vector_outputs(node, float_value=float(self._input_int(node, "Value", 0)))
                return True
            if mode == "INT_TO_VECTOR":
                scalar = float(self._input_int(node, "Value", 0))
                self._set_scalar_vector_outputs(node, vector_value=(scalar, scalar, scalar))
                return True
            if mode == "FLOAT_TO_BOOL":
                self._set_scalar_vector_outputs(
                    node,
                    bool_value=(abs(self._input_float(node, "Value", 0.0)) > max(1e-6, float(node.epsilon))),
                )
                return True
            if mode == "FLOAT_TO_INT":
                self._set_scalar_vector_outputs(node, int_value=int(self._input_float(node, "Value", 0.0)))
                return True
            if mode == "FLOAT_TO_VECTOR":
                scalar = float(self._input_float(node, "Value", 0.0))
                self._set_scalar_vector_outputs(node, vector_value=(scalar, scalar, scalar))
                return True
            vector_value = self._input_vector(node, "Value", (0.0, 0.0, 0.0))
            epsilon = max(1e-6, float(node.epsilon))
            if mode == "VECTOR_TO_BOOL":
                if node.vector_bool_mode == "ALL_NONZERO":
                    result = all(abs(float(component)) > epsilon for component in vector_value)
                elif node.vector_bool_mode == "LENGTH_NONZERO":
                    result = float(Vector(vector_value).length) > epsilon
                else:
                    result = any(abs(float(component)) > epsilon for component in vector_value)
                self._set_scalar_vector_outputs(node, bool_value=result)
                return True
            scalar_value = self._vector_scalar_component(vector_value, node.vector_component_mode)
            if mode == "VECTOR_TO_INT":
                self._set_scalar_vector_outputs(node, int_value=int(scalar_value))
                return True
            if mode == "VECTOR_TO_FLOAT":
                self._set_scalar_vector_outputs(node, float_value=float(scalar_value))
                return True
            return False

        if node_type == "AFNodeMath":
            op = node.operation
            unary_ops = {"ABSOLUTE", "SIGN", "FLOOR", "CEIL", "ROUND", "FRACT"}
            if op in unary_ops:
                a = self._input_float(node, "Value", 0.0)
                b = 0.0
            elif op == "WRAP":
                value_in = self._input_float(node, "Value", 0.0)
                min_v = self._input_float(node, "Min", 0.0)
                max_v = self._input_float(node, "Max", 1.0)
                span = max_v - min_v
                value = min_v if span == 0.0 else ((value_in - min_v) % span) + min_v
                self._set_scalar_vector_outputs(node, float_value=value)
                return True
            elif op == "SNAP":
                value_in = self._input_float(node, "Value", 0.0)
                increment = self._input_float(node, "Increment", 1.0)
                value = round(value_in / increment) * increment if increment != 0.0 else value_in
                self._set_scalar_vector_outputs(node, float_value=value)
                return True
            elif op == "PINGPONG":
                value_in = self._input_float(node, "Value", 0.0)
                scale = abs(self._input_float(node, "Scale", 1.0))
                if scale == 0.0:
                    value = 0.0
                else:
                    t = math.fmod(value_in, 2.0 * scale)
                    if t < 0.0:
                        t += 2.0 * scale
                    value = scale - abs(t - scale)
                self._set_scalar_vector_outputs(node, float_value=value)
                return True
            else:
                a = self._input_float(node, "A", 0.0)
                b = self._input_float(node, "B", 0.0)

            if op == "ADD":
                value = a + b
            elif op == "SUBTRACT":
                value = a - b
            elif op == "MULTIPLY":
                value = a * b
            elif op == "DIVIDE":
                value = a / b if b != 0.0 else 0.0
            elif op == "POWER":
                value = math.pow(a, b)
            elif op == "MINIMUM":
                value = min(a, b)
            elif op == "MAXIMUM":
                value = max(a, b)
            elif op == "ABSOLUTE":
                value = abs(a)
            elif op == "SIGN":
                value = 0.0 if a == 0.0 else (1.0 if a > 0.0 else -1.0)
            elif op == "FLOOR":
                value = math.floor(a)
            elif op == "CEIL":
                value = math.ceil(a)
            elif op == "ROUND":
                value = round(a)
            elif op == "FRACT":
                value = a - math.floor(a)
            elif op == "MODULO":
                value = math.fmod(a, b) if b != 0.0 else 0.0
            else:
                value = a
            self._set_scalar_vector_outputs(node, float_value=value)
            return True

        if node_type == "AFNodeIntegerMath":
            op = node.operation
            if op in {"ABSOLUTE", "SIGN"}:
                a = self._input_int(node, "Value", 0)
                b = 0
            else:
                a = self._input_int(node, "A", 0)
                b = self._input_int(node, "B", 0)

            if op == "ADD":
                value = a + b
            elif op == "SUBTRACT":
                value = a - b
            elif op == "MULTIPLY":
                value = a * b
            elif op == "DIVIDE":
                value = int(a / b) if b != 0 else 0
            elif op == "MODULO":
                value = a % b if b != 0 else 0
            elif op == "POWER":
                value = int(math.pow(a, b))
            elif op == "MINIMUM":
                value = min(a, b)
            elif op == "MAXIMUM":
                value = max(a, b)
            elif op == "ABSOLUTE":
                value = abs(a)
            elif op == "SIGN":
                value = 0 if a == 0 else (1 if a > 0 else -1)
            else:
                value = a
            self._set_scalar_vector_outputs(node, int_value=value)
            return True

        if node_type == "AFNodeBooleanMath":
            op = node.operation
            if op == "NOT":
                a = self._input_bool(node, "Boolean", False)
                b = False
            else:
                a = self._input_bool(node, "A", False)
                b = self._input_bool(node, "B", False)
            if op == "AND":
                value = a and b
            elif op == "OR":
                value = a or b
            elif op == "NOT":
                value = not a
            elif op == "XOR":
                value = bool(a) ^ bool(b)
            elif op == "NAND":
                value = not (a and b)
            elif op == "NOR":
                value = not (a or b)
            else:
                value = False
            self._set_scalar_vector_outputs(node, bool_value=value)
            return True

        if node_type == "AFNodeVectorMath":
            op = node.operation
            vec = Vector((0.0, 0.0, 0.0))
            scalar = 0.0
            if op in {"LENGTH", "NORMALIZE", "SCALE", "PROJECT", "REFLECT"}:
                a = self._input_vector(node, "Vector")
            else:
                a = self._input_vector(node, "A")

            if op in {"ADD", "SUBTRACT", "DISTANCE", "DOT_PRODUCT", "CROSS_PRODUCT"}:
                b = self._input_vector(node, "B")
            elif op == "PROJECT":
                b = self._input_vector(node, "On")
            elif op == "REFLECT":
                b = self._input_vector(node, "Normal")
            else:
                b = Vector((0.0, 0.0, 0.0))

            if op == "ADD":
                vec = a + b
            elif op == "SUBTRACT":
                vec = a - b
            elif op == "SCALE":
                scale = self._input_float(node, "Scale", 1.0)
                vec = a * scale
            elif op == "LENGTH":
                scalar = a.length
            elif op == "DISTANCE":
                scalar = (a - b).length
            elif op == "DOT_PRODUCT":
                scalar = a.dot(b)
            elif op == "CROSS_PRODUCT":
                vec = a.cross(b)
            elif op == "NORMALIZE":
                vec = a.normalized() if a.length != 0.0 else Vector((0.0, 0.0, 0.0))
            elif op == "PROJECT":
                if b.length == 0.0:
                    vec = Vector((0.0, 0.0, 0.0))
                else:
                    unit = b.normalized()
                    vec = unit * a.dot(unit)
            elif op == "REFLECT":
                if b.length == 0.0:
                    vec = a
                else:
                    normal = b.normalized()
                    vec = a - 2.0 * a.dot(normal) * normal
            self._set_scalar_vector_outputs(node, vector_value=vec, float_value=scalar)
            return True

        if node_type == "AFNodeMix":
            factor = self._input_float(node, "Factor", 0.5)
            if node.mode == "VECTOR":
                a = self._input_vector(node, "A")
                b = self._input_vector(node, "B")
                value = a.lerp(b, factor)
                self._set_scalar_vector_outputs(node, vector_value=value)
            else:
                a = self._input_float(node, "A", 0.0)
                b = self._input_float(node, "B", 0.0)
                value = (1.0 - factor) * a + factor * b
                self._set_scalar_vector_outputs(node, float_value=value)
            return True

        if node_type == "AFNodeSwitch":
            switch = self._input_bool(node, "Switch", False)
            selected_name = "True" if switch else "False"
            mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
            if mode == "VECTOR":
                value = tuple(self._input_vector(node, selected_name, (0.0, 0.0, 0.0)))
            elif mode == "BOOLEAN":
                value = bool(self._input_bool(node, selected_name, False))
            elif mode == "INTEGER":
                value = int(self._input_int(node, selected_name, 0))
            elif mode == "STRING":
                value = str(self._input_string(node, selected_name, ""))
            elif mode == "DISPLAY_TYPE":
                value = str(self._input_display_type(node, selected_name, "TEXTURED") or "TEXTURED")
            elif mode == "ROTATION_MODE":
                value = str(self._input_rotation_mode(node, selected_name, "XYZ") or "XYZ")
            elif mode == "ROTATION":
                value = _quaternion_to_payload(self._input_rotation(node, selected_name))
            elif mode == "MATRIX":
                value = _matrix_to_payload(self._input_matrix(node, selected_name))
            elif mode == "PROPERTY_ASSIGNMENT":
                value = self._get_linked_output(node, selected_name, "property_assignment")
            elif mode == "PROPERTY_PACKAGE":
                value = self._get_linked_output(node, selected_name, "property_package")
            else:
                value = float(self._input_float(node, selected_name, 0.0))
            self._set_output_socket_value(node, "Output", value)
            return True

        if node_type == "AFNodeIndexSwitch":
            value_socket_idname = {
                "BOOLEAN": "AFSocketBooleanValue",
                "FLOAT": "AFSocketFloatValue",
                "INTEGER": "AFSocketIntegerValue",
                "VECTOR": "AFSocketVectorValue",
                "STRING": "AFSocketString",
                "DISPLAY_TYPE": "AFSocketDisplayType",
                "ROTATION_MODE": "AFSocketRotationMode",
            }.get(str(getattr(node, "mode", "FLOAT") or "FLOAT"), "AFSocketFloatValue")
            value_inputs = [
                socket
                for socket in getattr(node, "inputs", [])
                if str(getattr(socket, "bl_idname", "") or "") == value_socket_idname
                and not bool(getattr(socket, "af_is_virtual", False))
            ]
            selected_index = self._input_int(node, "Index", 0)
            if not value_inputs:
                mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
                if mode == "VECTOR":
                    value = (0.0, 0.0, 0.0)
                elif mode == "BOOLEAN":
                    value = False
                elif mode == "INTEGER":
                    value = 0
                elif mode == "STRING":
                    value = ""
                elif mode == "DISPLAY_TYPE":
                    value = "TEXTURED"
                elif mode == "ROTATION_MODE":
                    value = "XYZ"
                else:
                    value = 0.0
                self._set_output_socket_value(node, "Value", value)
                return True

            clamped_index = min(max(int(selected_index), 0), len(value_inputs) - 1)
            selected_socket = value_inputs[clamped_index]
            selected_name = str(getattr(selected_socket, "name", "") or "")

            mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
            if mode == "VECTOR":
                value = tuple(
                    self._input_vector(
                        node,
                        selected_name,
                        tuple(getattr(selected_socket, "default_value", (0.0, 0.0, 0.0))),
                    )
                )
            elif mode == "BOOLEAN":
                value = bool(
                    self._input_bool(
                        node,
                        selected_name,
                        bool(getattr(selected_socket, "default_value", False)),
                    )
                )
            elif mode == "INTEGER":
                value = int(
                    self._input_int(
                        node,
                        selected_name,
                        int(getattr(selected_socket, "default_value", 0)),
                    )
                )
            elif mode == "STRING":
                value = str(
                    self._input_string(
                        node,
                        selected_name,
                        str(getattr(selected_socket, "default_value", "") or ""),
                    )
                )
            elif mode == "DISPLAY_TYPE":
                value = str(
                    self._input_display_type(
                        node,
                        selected_name,
                        str(getattr(selected_socket, "default_value", "TEXTURED") or "TEXTURED"),
                    )
                )
            elif mode == "ROTATION_MODE":
                value = str(
                    self._input_rotation_mode(
                        node,
                        selected_name,
                        str(getattr(selected_socket, "default_value", "XYZ") or "XYZ"),
                    )
                )
            else:
                value = float(
                    self._input_float(
                        node,
                        selected_name,
                        float(getattr(selected_socket, "default_value", 0.0)),
                    )
                )
            self._set_output_socket_value(node, "Value", value)
            return True

        if node_type == "AFNodeCompare":
            eps = max(0.0, float(node.epsilon))
            op = node.operation
            if node.mode == "VECTOR":
                a = self._input_vector(node, "A")
                b = self._input_vector(node, "B")
                metric = a.length if node.vector_mode == "LENGTH" else (a - b).length
                target = float(node.threshold)
                lhs = metric
                rhs = target
            else:
                lhs = self._input_float(node, "A", 0.0)
                rhs = self._input_float(node, "B", 0.0)

            if op == "EQUAL":
                value = abs(lhs - rhs) <= eps
            elif op == "NOT_EQUAL":
                value = abs(lhs - rhs) > eps
            elif op == "LESS_THAN":
                value = lhs < rhs - eps
            elif op == "LESS_EQUAL":
                value = lhs <= rhs + eps
            elif op == "GREATER_THAN":
                value = lhs > rhs + eps
            else:
                value = lhs >= rhs - eps
            self._set_scalar_vector_outputs(node, bool_value=value)
            return True

        if node_type == "AFNodeStringCompare":
            lhs = str(self._input_string_forgiving(node, "A", "") or "")
            rhs = str(self._input_string_forgiving(node, "B", "") or "")
            op = str(getattr(node, "operation", "EQUAL") or "EQUAL")
            if op == "NOT_EQUAL":
                value = lhs != rhs
            elif op == "CONTAINS":
                value = rhs in lhs
            elif op == "STARTS_WITH":
                value = lhs.startswith(rhs)
            elif op == "ENDS_WITH":
                value = lhs.endswith(rhs)
            else:
                value = lhs == rhs
            self._set_scalar_vector_outputs(node, bool_value=bool(value))
            return True

        if node_type == "AFNodeClamp":
            value = self._input_float(node, "Value", 0.0)
            min_v = self._input_float(node, "Min", 0.0)
            max_v = self._input_float(node, "Max", 1.0)
            lo = min(min_v, max_v)
            hi = max(min_v, max_v)
            self._set_scalar_vector_outputs(node, float_value=max(lo, min(hi, value)))
            return True

        if node_type == "AFNodeMapRange":
            value = self._input_float(node, "Value", 0.0)
            from_min = self._input_float(node, "From Min", 0.0)
            from_max = self._input_float(node, "From Max", 1.0)
            to_min = self._input_float(node, "To Min", 0.0)
            to_max = self._input_float(node, "To Max", 1.0)
            if from_max == from_min:
                mapped = to_min
            else:
                t = (value - from_min) / (from_max - from_min)
                mapped = to_min + t * (to_max - to_min)
            if node.clamp:
                lo = min(to_min, to_max)
                hi = max(to_min, to_max)
                mapped = max(lo, min(hi, mapped))
            self._set_scalar_vector_outputs(node, float_value=mapped)
            return True

        if node_type == "AFNodeCombineVector":
            x = self._input_float(node, "X", 0.0)
            y = self._input_float(node, "Y", 0.0)
            z = self._input_float(node, "Z", 0.0)
            self._set_scalar_vector_outputs(node, vector_value=Vector((x, y, z)))
            return True

        if node_type == "AFNodeSeparateVector":
            vec = self._input_vector(node, "Vector")
            self._set_scalar_vector_outputs(node, float_value=vec.x)
            self._set_output(node, "float_x", float(vec.x))
            self._set_output(node, "float_y", float(vec.y))
            self._set_output(node, "float_z", float(vec.z))
            return True

        if node_type == "AFNodeVectorRotate":
            vec = self._input_vector(node, "Vector")
            axis = self._input_vector(node, "Axis")
            angle = self._input_float(node, "Angle", 0.0)
            if axis.length == 0.0:
                rotated = vec
            else:
                rotated = Matrix.Rotation(angle, 3, axis.normalized()) @ vec
            self._set_scalar_vector_outputs(node, vector_value=rotated)
            return True

        if node_type == "AFNodeEulerToRotation":
            euler_value = self._input_vector(node, "Euler", (0.0, 0.0, 0.0))
            rotation_payload = _quaternion_to_payload(
                Euler((float(euler_value.x), float(euler_value.y), float(euler_value.z)), "XYZ").to_quaternion()
            )
            self._set_output(node, "rotation_value", rotation_payload)
            return True

        if node_type == "AFNodeQuaternionToRotation":
            quaternion_value = Quaternion(
                (
                    float(self._input_float(node, "W", 1.0)),
                    float(self._input_float(node, "X", 0.0)),
                    float(self._input_float(node, "Y", 0.0)),
                    float(self._input_float(node, "Z", 0.0)),
                )
            )
            self._set_output(node, "rotation_value", _quaternion_to_payload(quaternion_value))
            return True

        if node_type == "AFNodeAxisAngleToRotation":
            axis = _normalized_vector_or_none(self._input_vector(node, "Axis", (0.0, 0.0, 1.0)))
            angle = float(self._input_float(node, "Angle", 0.0))
            quaternion_value = Quaternion(axis, angle) if axis is not None else Quaternion(ROTATION_IDENTITY_QUATERNION)
            self._set_output(node, "rotation_value", _quaternion_to_payload(quaternion_value))
            return True

        if node_type == "AFNodeInvertRotation":
            rotation_value = self._input_rotation(node, "Rotation")
            self._set_output(node, "rotation_value", _quaternion_to_payload(rotation_value.inverted()))
            return True

        if node_type == "AFNodeRotateRotation":
            base_rotation = self._input_rotation(node, "Rotation")
            rotate_by = self._input_rotation(node, "Rotate By")
            if str(getattr(node, "rotation_space", "GLOBAL") or "GLOBAL") == "LOCAL":
                result_rotation = base_rotation @ rotate_by
            else:
                result_rotation = rotate_by @ base_rotation
            self._set_output(node, "rotation_value", _quaternion_to_payload(result_rotation))
            return True

        if node_type == "AFNodeRotationToEuler":
            rotation_value = self._input_rotation(node, "Rotation")
            euler_value = rotation_value.to_euler("XYZ")
            self._set_scalar_vector_outputs(
                node,
                vector_value=(float(euler_value.x), float(euler_value.y), float(euler_value.z)),
            )
            return True

        if node_type == "AFNodeRotationToQuaternion":
            quaternion_value = self._input_rotation(node, "Rotation")
            component_map = {
                "W": float(quaternion_value.w),
                "X": float(quaternion_value.x),
                "Y": float(quaternion_value.y),
                "Z": float(quaternion_value.z),
            }
            for socket in getattr(node, "outputs", []):
                socket_name = str(getattr(socket, "name", "") or "")
                output_key = _socket_specific_output_key(socket)
                if socket_name not in component_map or not output_key:
                    continue
                self._set_output(node, output_key, component_map[socket_name])
            return True

        if node_type == "AFNodeRotationToAxisAngle":
            rotation_value = self._input_rotation(node, "Rotation")
            angle = float(rotation_value.angle)
            axis = rotation_value.axis if angle > 1e-8 else Vector((0.0, 0.0, 1.0))
            self._set_scalar_vector_outputs(node, vector_value=(float(axis.x), float(axis.y), float(axis.z)))
            for socket in getattr(node, "outputs", []):
                if str(getattr(socket, "name", "") or "") != "Angle":
                    continue
                output_key = _socket_specific_output_key(socket)
                if output_key:
                    self._set_output(node, output_key, angle)
                    break
            return True

        if node_type == "AFNodeAxesToRotation":
            primary_vector = self._input_vector(node, "Primary Axis", (0.0, 0.0, 1.0))
            secondary_vector = self._input_vector(node, "Secondary Axis", (1.0, 0.0, 0.0))
            rotation_value = _rotation_from_axes(
                primary_vector,
                secondary_vector,
                getattr(node, "primary_axis", "Z"),
                getattr(node, "secondary_axis", "X"),
            )
            self._set_output(node, "rotation_value", _quaternion_to_payload(rotation_value))
            return True

        if node_type == "AFNodeAlignRotationToVector":
            base_rotation = self._input_rotation(node, "Rotation")
            factor = self._input_float(node, "Factor", 1.0)
            target_vector = self._input_vector(node, "Vector", (0.0, 0.0, 1.0))
            result_rotation = _rotation_align_to_vector(
                base_rotation,
                target_vector,
                getattr(node, "axis", "Z"),
                getattr(node, "pivot_axis", "AUTO"),
                factor,
            )
            self._set_output(node, "rotation_value", _quaternion_to_payload(result_rotation))
            return True

        if node_type == "AFNodeCombineMatrix":
            rows = [[0.0, 0.0, 0.0, 0.0] for _index in range(4)]
            for column in range(1, 5):
                for row in range(1, 5):
                    rows[row - 1][column - 1] = float(self._input_float(node, f"Column {column} Row {row}", 0.0))
            self._set_output(node, "matrix_value", _matrix_to_payload(Matrix(tuple(tuple(row) for row in rows))))
            return True

        if node_type == "AFNodeSeparateMatrix":
            matrix_value = self._input_matrix(node, "Matrix")
            for socket in getattr(node, "outputs", []):
                socket_name = str(getattr(socket, "name", "") or "")
                match = re.match(r"Column\\s+([1-4])\\s+Row\\s+([1-4])$", socket_name)
                if match is None:
                    continue
                column_index = int(match.group(1)) - 1
                row_index = int(match.group(2)) - 1
                output_key = _socket_specific_output_key(socket)
                if not output_key:
                    continue
                self._set_output(node, output_key, float(matrix_value[row_index][column_index]))
            return True

        if node_type == "AFNodeMatrixMultiply":
            matrix_a = self._input_matrix(node, "Matrix A")
            matrix_b = self._input_matrix(node, "Matrix B")
            self._set_output(node, "matrix_value", _matrix_to_payload(matrix_a @ matrix_b))
            return True

        if node_type == "AFNodeInvertMatrix":
            matrix_value = self._input_matrix(node, "Matrix")
            determinant = float(matrix_value.determinant())
            invertible = abs(determinant) > 1e-8
            result_matrix = matrix_value.inverted() if invertible else Matrix.Identity(4)
            self._set_output(node, "matrix_value", _matrix_to_payload(result_matrix))
            self._set_scalar_vector_outputs(node, bool_value=invertible)
            return True

        if node_type == "AFNodeTransposeMatrix":
            matrix_value = self._input_matrix(node, "Matrix")
            self._set_output(node, "matrix_value", _matrix_to_payload(matrix_value.transposed()))
            return True

        if node_type == "AFNodeMatrixDeterminant":
            matrix_value = self._input_matrix(node, "Matrix")
            self._set_scalar_vector_outputs(node, float_value=float(matrix_value.determinant()))
            return True

        if node_type == "AFNodeCombineTransform":
            translation_value = self._input_vector(node, "Translation", (0.0, 0.0, 0.0))
            rotation_value = self._input_rotation(node, "Rotation")
            scale_value = self._input_vector(node, "Scale", (1.0, 1.0, 1.0))
            matrix_value = Matrix.LocRotScale(
                Vector((float(translation_value.x), float(translation_value.y), float(translation_value.z))),
                rotation_value,
                Vector((float(scale_value.x), float(scale_value.y), float(scale_value.z))),
            )
            self._set_output(node, "matrix_value", _matrix_to_payload(matrix_value))
            return True

        if node_type == "AFNodeSeparateTransform":
            matrix_value = self._input_matrix(node, "Matrix")
            translation_value, rotation_value, scale_value = matrix_value.decompose()
            self._set_output_socket_value(
                node,
                "Translation",
                (float(translation_value.x), float(translation_value.y), float(translation_value.z)),
            )
            self._set_output_socket_value(node, "Rotation", _quaternion_to_payload(rotation_value))
            self._set_output_socket_value(
                node,
                "Scale",
                (float(scale_value.x), float(scale_value.y), float(scale_value.z)),
            )
            return True

        if node_type == "AFNodeTransformPoint":
            point_value = self._input_vector(node, "Point", (0.0, 0.0, 0.0))
            matrix_value = self._input_matrix(node, "Matrix")
            point4 = Vector((float(point_value.x), float(point_value.y), float(point_value.z), 1.0))
            transformed = matrix_value @ point4
            self._set_output_socket_value(
                node,
                "Point",
                (float(transformed.x), float(transformed.y), float(transformed.z)),
            )
            return True

        if node_type == "AFNodeTransformDirection":
            direction_value = self._input_vector(node, "Direction", (0.0, 0.0, 0.0))
            matrix_value = self._input_matrix(node, "Matrix")
            transformed = matrix_value.to_3x3() @ Vector(
                (float(direction_value.x), float(direction_value.y), float(direction_value.z))
            )
            self._set_output_socket_value(
                node,
                "Direction",
                (float(transformed.x), float(transformed.y), float(transformed.z)),
            )
            return True

        if node_type == "AFNodeProjectPoint":
            point_value = self._input_vector(node, "Point", (0.0, 0.0, 0.0))
            matrix_value = self._input_matrix(node, "Matrix")
            projected = matrix_value @ Vector((float(point_value.x), float(point_value.y), float(point_value.z), 1.0))
            if abs(float(projected.w)) > 1e-8:
                projected_xyz = projected.xyz / float(projected.w)
            else:
                projected_xyz = projected.xyz
            self._set_output_socket_value(
                node,
                "Point",
                (float(projected_xyz.x), float(projected_xyz.y), float(projected_xyz.z)),
            )
            return True

        if node_type == "AFNodeSmoothstep":
            value = self._input_float(node, "Value", 0.0)
            edge0 = self._input_float(node, "Edge0", 0.0)
            edge1 = self._input_float(node, "Edge1", 1.0)
            if edge1 == edge0:
                t = 0.0
            else:
                t = (value - edge0) / (edge1 - edge0)
            t = max(0.0, min(1.0, t))
            result = t * t * (3.0 - 2.0 * t)
            self._set_scalar_vector_outputs(node, float_value=result)
            return True

        if node_type == "AFNodeRandomValue":
            seed = self._input_int(node, "Seed", 0)
            rnd = random.Random(seed)
            if node.value_type == "VECTOR":
                min_v = self._input_vector(node, "Min")
                max_v = self._input_vector(node, "Max")
                vector_value = Vector(
                    (
                        rnd.uniform(min(min_v.x, max_v.x), max(min_v.x, max_v.x)),
                        rnd.uniform(min(min_v.y, max_v.y), max(min_v.y, max_v.y)),
                        rnd.uniform(min(min_v.z, max_v.z), max(min_v.z, max_v.z)),
                    )
                )
                self._set_scalar_vector_outputs(node, vector_value=vector_value)
            elif node.value_type == "BOOLEAN":
                bool_value = rnd.random() >= 0.5
                self._set_scalar_vector_outputs(node, bool_value=bool_value)
            else:
                min_f = self._input_float(node, "Min", 0.0)
                max_f = self._input_float(node, "Max", 1.0)
                float_value = rnd.uniform(min(min_f, max_f), max(min_f, max_f))
                self._set_scalar_vector_outputs(node, float_value=float_value)
            return True

        return False


__all__ = ["RuntimeMathDataMixin"]
