import math
import random
import re

from mathutils import Euler, Matrix, Quaternion, Vector

from ...runtime_core.constants import ROTATION_IDENTITY_QUATERNION
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_flow.helpers import _socket_specific_output_key
from ...runtime_math.values import (
    _matrix_to_payload,
    _normalized_vector_or_none,
    _quaternion_to_payload,
    _rotation_align_to_vector,
    _rotation_from_axes,
)


class RuntimeMathDataMixin:
    _FLOAT32_EPSILON = 1.1920928955078125e-07

    @staticmethod
    def _matrix_is_identity(matrix_value, epsilon=1e-8):
        try:
            identity = Matrix.Identity(4)
            for row_index in range(4):
                for column_index in range(4):
                    if abs(float(matrix_value[row_index][column_index]) - float(identity[row_index][column_index])) > float(epsilon):
                        return False
            return True
        except Exception:
            return False

    def _matrix_input_has_no_effective_source(self, node, input_name):
        input_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)(input_name)
        if input_socket is None:
            return True
        if not bool(getattr(input_socket, "is_linked", False)):
            return True
        from_node, from_socket = _find_single_from_input_socket(input_socket)
        if from_node is None or from_socket is None:
            return True
        if str(getattr(from_node, "bl_idname", "") or "") != "NodeGroupInput":
            return False
        upstream_node, _upstream_socket, parent_group_path = self._resolve_group_input_source(
            from_node,
            from_socket,
            self.current_group_path,
        )
        if upstream_node is not None:
            return False
        del parent_group_path
        return True

    @staticmethod
    def _compare_numeric_values(lhs, rhs, op, epsilon):
        if op == "EQUAL":
            return abs(lhs - rhs) <= epsilon
        if op == "NOT_EQUAL":
            return abs(lhs - rhs) > epsilon
        if op == "LESS_THAN":
            return lhs < rhs - epsilon
        if op == "LESS_EQUAL":
            return lhs <= rhs + epsilon
        if op == "GREATER_THAN":
            return lhs > rhs + epsilon
        return lhs >= rhs - epsilon

    @staticmethod
    def _safe_math_power(base, exponent):
        if exponent == 0.0:
            return 1.0
        if base == 0.0:
            return 0.0
        if base < 0.0 and not float(exponent).is_integer():
            return 0.0
        return math.pow(base, exponent)

    @staticmethod
    def _safe_math_logarithm(value, base):
        if value <= 0.0 or base <= 0.0:
            return 0.0
        denominator = math.log(base)
        return math.log(value) / denominator if denominator != 0.0 else 0.0

    @staticmethod
    def _safe_math_sqrt(value):
        return math.sqrt(max(float(value), 0.0))

    @staticmethod
    def _safe_math_inverse_sqrt(value):
        return 1.0 / math.sqrt(value) if value > 0.0 else 0.0

    @staticmethod
    def _safe_math_asin(value):
        return math.asin(max(-1.0, min(1.0, float(value))))

    @staticmethod
    def _safe_math_acos(value):
        return math.acos(max(-1.0, min(1.0, float(value))))

    @staticmethod
    def _safe_math_wrap(value, minimum, maximum):
        span = maximum - minimum
        return value - (span * math.floor((value - minimum) / span)) if span != 0.0 else minimum

    @staticmethod
    def _safe_math_pingpong(value, scale):
        if scale == 0.0:
            return 0.0
        cycle = scale * 2.0
        return abs((value - scale) - math.floor((value - scale) / cycle) * cycle - scale)

    @staticmethod
    def _safe_math_smooth_min(a, b, distance):
        if distance != 0.0:
            h = max(distance - abs(a - b), 0.0) / distance
            return min(a, b) - h * h * h * distance * (1.0 / 6.0)
        return min(a, b)

    @staticmethod
    def _safe_math_atan2(y, x):
        return 0.0 if x == 0.0 and y == 0.0 else math.atan2(y, x)

    @staticmethod
    def _clamp_math_result(value, enabled):
        if not bool(enabled):
            return value
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _safe_math_exp(value):
        try:
            return math.exp(value)
        except OverflowError:
            return math.inf

    @staticmethod
    def _safe_math_sinh(value):
        try:
            return math.sinh(value)
        except OverflowError:
            return math.inf if value >= 0.0 else -math.inf

    @staticmethod
    def _safe_math_cosh(value):
        try:
            return math.cosh(value)
        except OverflowError:
            return math.inf

    @staticmethod
    def _safe_float_divide(a, b):
        return a / b if b != 0.0 else 0.0

    @staticmethod
    def _safe_float_modulo(a, b):
        return math.fmod(a, b) if b != 0.0 else 0.0

    @staticmethod
    def _safe_float_floored_modulo(a, b):
        return a - math.floor(a / b) * b if b != 0.0 else 0.0

    @staticmethod
    def _safe_math_sign(value):
        if value == 0.0:
            return 0.0
        return 1.0 if value > 0.0 else -1.0

    @staticmethod
    def _round_half_away_from_zero(value):
        if value >= 0.0:
            return math.floor(value + 0.5)
        return math.ceil(value - 0.5)

    @staticmethod
    def _safe_int_divide(a, b):
        return int(a / b) if b != 0 else 0

    @staticmethod
    def _safe_int_divide_round(a, b):
        if b == 0:
            return 0
        return int(RuntimeMathDataMixin._round_half_away_from_zero(a / b))

    @staticmethod
    def _safe_int_divide_floor(a, b):
        return int(math.floor(a / b)) if b != 0 else 0

    @staticmethod
    def _safe_int_divide_ceil(a, b):
        return int(math.ceil(a / b)) if b != 0 else 0

    @staticmethod
    def _safe_int_modulo(a, b):
        return a - int(a / b) * b if b != 0 else 0

    @staticmethod
    def _safe_int_floored_modulo(a, b):
        return a - math.floor(a / b) * b if b != 0 else 0

    @staticmethod
    def _safe_int_power(a, b):
        try:
            return int(math.pow(a, b))
        except Exception:
            return 0

    @staticmethod
    def _safe_int_gcd(a, b):
        return math.gcd(int(a), int(b))

    @staticmethod
    def _safe_int_lcm(a, b):
        a = int(a)
        b = int(b)
        if a == 0 or b == 0:
            return 0
        return abs(a * b) // math.gcd(a, b)

    @staticmethod
    def _vector_unary(vector_value, fn):
        return Vector(tuple(float(fn(float(component))) for component in tuple(vector_value)[:3]))

    @staticmethod
    def _vector_binary(lhs, rhs, fn):
        lhs_values = tuple(lhs)[:3]
        rhs_values = tuple(rhs)[:3]
        return Vector(tuple(float(fn(float(a), float(b))) for a, b in zip(lhs_values, rhs_values)))

    @staticmethod
    def _safe_vector_divide(lhs, rhs):
        return RuntimeMathDataMixin._vector_binary(lhs, rhs, RuntimeMathDataMixin._safe_float_divide)

    @staticmethod
    def _safe_vector_modulo(lhs, rhs):
        return RuntimeMathDataMixin._vector_binary(lhs, rhs, RuntimeMathDataMixin._safe_float_modulo)

    @staticmethod
    def _safe_vector_power(lhs, rhs):
        return RuntimeMathDataMixin._vector_binary(lhs, rhs, RuntimeMathDataMixin._safe_math_power)

    @staticmethod
    def _safe_vector_sign(vector_value):
        return RuntimeMathDataMixin._vector_unary(vector_value, RuntimeMathDataMixin._safe_math_sign)

    @staticmethod
    def _safe_vector_wrap(value, minimum, maximum):
        return Vector(
            tuple(
                float(RuntimeMathDataMixin._safe_math_wrap(float(component), float(minimum_component), float(maximum_component)))
                for component, minimum_component, maximum_component in zip(tuple(value)[:3], tuple(minimum)[:3], tuple(maximum)[:3])
            )
        )

    @staticmethod
    def _safe_vector_snap(lhs, rhs):
        return RuntimeMathDataMixin._vector_binary(
            lhs,
            rhs,
            lambda a, b: math.floor(RuntimeMathDataMixin._safe_float_divide(a, b)) * b,
        )

    @staticmethod
    def _safe_vector_refract(incident, normal, ior):
        incident = Vector(tuple(float(component) for component in tuple(incident)[:3]))
        if Vector(normal).length == 0.0:
            unit_normal = Vector((0.0, 0.0, 0.0))
        else:
            unit_normal = Vector(normal).normalized()
        dot_value = float(unit_normal.dot(incident))
        k = 1.0 - ior * ior * (1.0 - dot_value * dot_value)
        if k < 0.0:
            return Vector((0.0, 0.0, 0.0))
        return (ior * incident) - ((ior * dot_value + math.sqrt(k)) * unit_normal)

    @staticmethod
    def _safe_vector_faceforward(vector_value, incident, reference):
        vector_value = Vector(tuple(float(component) for component in tuple(vector_value)[:3]))
        incident = Vector(tuple(float(component) for component in tuple(incident)[:3]))
        reference = Vector(tuple(float(component) for component in tuple(reference)[:3]))
        return vector_value if float(reference.dot(incident)) < 0.0 else -vector_value

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
            string_socket = getattr(getattr(node, "outputs", None), "get", lambda _name: None)("String")
            if string_socket is not None and str(getattr(string_socket, "bl_idname", "") or "") == "AFSocketString":
                value = str(getattr(string_socket, "default_value", "") or "")
            else:
                value = str(getattr(node, "value", "") or "")
            self._set_output(node, "string_value", value)
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
            use_clamp = bool(getattr(node, "use_clamp", False))
            unary_ops = {
                "SQRT",
                "INVERSE_SQRT",
                "ABSOLUTE",
                "EXPONENT",
                "SIGN",
                "ROUND",
                "FLOOR",
                "CEIL",
                "TRUNC",
                "FRACT",
                "SINE",
                "COSINE",
                "TANGENT",
                "ARCSINE",
                "ARCCOSINE",
                "ARCTANGENT",
                "SINH",
                "COSH",
                "TANH",
                "RADIANS",
                "DEGREES",
            }
            if op in unary_ops:
                a = self._input_float(node, "Value", 0.0)
                b = 0.0
                c = 0.0
            elif op == "MULTIPLY_ADD":
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Multiplier", 0.0)
                c = self._input_float(node, "Addend", 0.0)
            elif op == "POWER":
                a = self._input_float(node, "Base", 0.0)
                b = self._input_float(node, "Exponent", 0.0)
                c = 0.0
            elif op == "LOGARITHM":
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Base", 10.0)
                c = 0.0
            elif op == "COMPARE":
                a = self._input_float(node, "A", 0.0)
                b = self._input_float(node, "B", 0.0)
                c = self._input_float(node, "Epsilon", 1e-6)
            elif op in {"SMOOTH_MIN", "SMOOTH_MAX"}:
                a = self._input_float(node, "A", 0.0)
                b = self._input_float(node, "B", 0.0)
                c = self._input_float(node, "Distance", 0.0)
            elif op == "WRAP":
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Min", 0.0)
                c = self._input_float(node, "Max", 1.0)
            elif op == "SNAP":
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Increment", 0.0)
                c = 0.0
            elif op == "PINGPONG":
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Scale", 1.0)
                c = 0.0
            elif op in {"LESS_THAN", "GREATER_THAN"}:
                a = self._input_float(node, "Value", 0.0)
                b = self._input_float(node, "Threshold", 0.0)
                c = 0.0
            else:
                a = self._input_float(node, "A", 0.0)
                b = self._input_float(node, "B", 0.0)
                c = 0.0

            if op == "ADD":
                value = a + b
            elif op == "SUBTRACT":
                value = a - b
            elif op == "MULTIPLY":
                value = a * b
            elif op == "DIVIDE":
                value = a / b if b != 0.0 else 0.0
            elif op == "MULTIPLY_ADD":
                value = a * b + c
            elif op == "POWER":
                value = self._safe_math_power(a, b)
            elif op == "LOGARITHM":
                value = self._safe_math_logarithm(a, b)
            elif op == "SQRT":
                value = self._safe_math_sqrt(a)
            elif op == "INVERSE_SQRT":
                value = self._safe_math_inverse_sqrt(a)
            elif op == "MINIMUM":
                value = min(a, b)
            elif op == "MAXIMUM":
                value = max(a, b)
            elif op == "ABSOLUTE":
                value = abs(a)
            elif op == "EXPONENT":
                value = self._safe_math_exp(a)
            elif op == "LESS_THAN":
                value = 1.0 if a < b else 0.0
            elif op == "GREATER_THAN":
                value = 1.0 if a > b else 0.0
            elif op == "SIGN":
                value = 0.0 if a == 0.0 else (1.0 if a > 0.0 else -1.0)
            elif op == "COMPARE":
                tolerance = max(float(c), self._FLOAT32_EPSILON)
                value = 1.0 if (a == b or abs(a - b) <= tolerance) else 0.0
            elif op == "SMOOTH_MIN":
                value = self._safe_math_smooth_min(a, b, c)
            elif op == "SMOOTH_MAX":
                value = -self._safe_math_smooth_min(-a, -b, c)
            elif op == "FLOOR":
                value = math.floor(a)
            elif op == "CEIL":
                value = math.ceil(a)
            elif op == "ROUND":
                value = math.floor(a + 0.5)
            elif op == "TRUNC":
                value = math.floor(a) if a >= 0.0 else math.ceil(a)
            elif op == "FRACT":
                value = a - math.floor(a)
            elif op == "MODULO":
                value = math.fmod(a, b) if b != 0.0 else 0.0
            elif op == "FLOORED_MODULO":
                value = a - math.floor(a / b) * b if b != 0.0 else 0.0
            elif op == "WRAP":
                value = self._safe_math_wrap(a, b, c)
            elif op == "SNAP":
                value = math.floor((a / b) if b != 0.0 else 0.0) * b
            elif op == "PINGPONG":
                value = self._safe_math_pingpong(a, b)
            elif op == "SINE":
                value = math.sin(a)
            elif op == "COSINE":
                value = math.cos(a)
            elif op == "TANGENT":
                value = math.tan(a)
            elif op == "ARCSINE":
                value = self._safe_math_asin(a)
            elif op == "ARCCOSINE":
                value = self._safe_math_acos(a)
            elif op == "ARCTANGENT":
                value = math.atan(a)
            elif op == "ARCTAN2":
                value = self._safe_math_atan2(a, b)
            elif op == "SINH":
                value = self._safe_math_sinh(a)
            elif op == "COSH":
                value = self._safe_math_cosh(a)
            elif op == "TANH":
                value = math.tanh(a)
            elif op == "RADIANS":
                value = a * (math.pi / 180.0)
            elif op == "DEGREES":
                value = a * (180.0 / math.pi)
            else:
                value = a
            value = self._clamp_math_result(value, use_clamp)
            self._set_scalar_vector_outputs(node, float_value=value)
            return True

        if node_type == "AFNodeIntegerMath":
            op = node.operation
            if op in {"ABSOLUTE", "NEGATE", "SIGN"}:
                a = self._input_int(node, "Value", 0)
                b = 0
                c = 0
            elif op == "MULTIPLY_ADD":
                a = self._input_int(node, "Value", 0)
                b = self._input_int(node, "Multiplier", 0)
                c = self._input_int(node, "Addend", 0)
            elif op == "POWER":
                a = self._input_int(node, "Base", 0)
                b = self._input_int(node, "Exponent", 0)
                c = 0
            else:
                a = self._input_int(node, "A", 0)
                b = self._input_int(node, "B", 0)
                c = 0

            if op == "ADD":
                value = a + b
            elif op == "SUBTRACT":
                value = a - b
            elif op == "MULTIPLY":
                value = a * b
            elif op == "MULTIPLY_ADD":
                value = a * b + c
            elif op == "DIVIDE":
                value = self._safe_int_divide(a, b)
            elif op == "DIVIDE_ROUND":
                value = self._safe_int_divide_round(a, b)
            elif op == "DIVIDE_FLOOR":
                value = self._safe_int_divide_floor(a, b)
            elif op == "DIVIDE_CEIL":
                value = self._safe_int_divide_ceil(a, b)
            elif op == "MODULO":
                value = self._safe_int_modulo(a, b)
            elif op == "FLOORED_MODULO":
                value = self._safe_int_floored_modulo(a, b)
            elif op == "POWER":
                value = self._safe_int_power(a, b)
            elif op == "MINIMUM":
                value = min(a, b)
            elif op == "MAXIMUM":
                value = max(a, b)
            elif op == "ABSOLUTE":
                value = abs(a)
            elif op == "NEGATE":
                value = -a
            elif op == "SIGN":
                value = 0 if a == 0 else (1 if a > 0 else -1)
            elif op == "GCD":
                value = self._safe_int_gcd(a, b)
            elif op == "LCM":
                value = self._safe_int_lcm(a, b)
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
            elif op == "XNOR":
                value = bool(a) == bool(b)
            elif op == "IMPLY":
                value = (not bool(a)) or bool(b)
            elif op == "NIMPLY":
                value = bool(a) and (not bool(b))
            else:
                value = False
            self._set_scalar_vector_outputs(node, bool_value=value)
            return True

        if node_type == "AFNodeVectorMath":
            op = node.operation
            vec = Vector((0.0, 0.0, 0.0))
            scalar = 0.0
            if op in {
                "LENGTH",
                "NORMALIZE",
                "SCALE",
                "PROJECT",
                "REFLECT",
                "REFRACT",
                "FACEFORWARD",
                "ABSOLUTE",
                "SIGN",
                "ROUND",
                "FLOOR",
                "CEIL",
                "FRACTION",
                "SINE",
                "COSINE",
                "TANGENT",
                "WRAP",
                "SNAP",
                "MULTIPLY_ADD",
            }:
                a = self._input_vector(node, "Vector")
            elif op == "POWER":
                a = self._input_vector(node, "Base")
            else:
                a = self._input_vector(node, "A")

            if op in {
                "ADD",
                "SUBTRACT",
                "MULTIPLY",
                "DIVIDE",
                "DISTANCE",
                "DOT_PRODUCT",
                "CROSS_PRODUCT",
                "MINIMUM",
                "MAXIMUM",
                "MODULO",
            }:
                b = self._input_vector(node, "B")
            elif op == "PROJECT":
                b = self._input_vector(node, "On")
            elif op == "REFLECT":
                b = self._input_vector(node, "Normal")
            elif op == "REFRACT":
                b = self._input_vector(node, "Normal")
            elif op == "FACEFORWARD":
                b = self._input_vector(node, "Incident")
            elif op == "MULTIPLY_ADD":
                b = self._input_vector(node, "Multiplier")
            elif op == "POWER":
                b = self._input_vector(node, "Exponent")
            elif op == "WRAP":
                b = self._input_vector(node, "Min")
            elif op == "SNAP":
                b = self._input_vector(node, "Increment")
            else:
                b = Vector((0.0, 0.0, 0.0))

            if op == "FACEFORWARD":
                c = self._input_vector(node, "Reference")
            elif op == "MULTIPLY_ADD":
                c = self._input_vector(node, "Addend")
            elif op == "WRAP":
                c = self._input_vector(node, "Max")
            else:
                c = Vector((0.0, 0.0, 0.0))

            if op == "ADD":
                vec = a + b
            elif op == "SUBTRACT":
                vec = a - b
            elif op == "MULTIPLY":
                vec = Vector((float(a.x) * float(b.x), float(a.y) * float(b.y), float(a.z) * float(b.z)))
            elif op == "DIVIDE":
                vec = self._safe_vector_divide(a, b)
            elif op == "MULTIPLY_ADD":
                vec = Vector(
                    (
                        float(a.x) * float(b.x) + float(c.x),
                        float(a.y) * float(b.y) + float(c.y),
                        float(a.z) * float(b.z) + float(c.z),
                    )
                )
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
            elif op == "ABSOLUTE":
                vec = self._vector_unary(a, abs)
            elif op == "POWER":
                vec = self._safe_vector_power(a, b)
            elif op == "SIGN":
                vec = self._safe_vector_sign(a)
            elif op == "MINIMUM":
                vec = self._vector_binary(a, b, min)
            elif op == "MAXIMUM":
                vec = self._vector_binary(a, b, max)
            elif op == "ROUND":
                vec = self._vector_unary(a, lambda component: math.floor(component + 0.5))
            elif op == "FLOOR":
                vec = self._vector_unary(a, math.floor)
            elif op == "CEIL":
                vec = self._vector_unary(a, math.ceil)
            elif op == "FRACTION":
                vec = self._vector_unary(a, lambda component: component - math.floor(component))
            elif op == "MODULO":
                vec = self._safe_vector_modulo(a, b)
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
            elif op == "REFRACT":
                vec = self._safe_vector_refract(a, b, self._input_float(node, "IOR", 1.0))
            elif op == "FACEFORWARD":
                vec = self._safe_vector_faceforward(a, b, c)
            elif op == "WRAP":
                vec = self._safe_vector_wrap(a, b, c)
            elif op == "SNAP":
                vec = self._safe_vector_snap(a, b)
            elif op == "SINE":
                vec = self._vector_unary(a, math.sin)
            elif op == "COSINE":
                vec = self._vector_unary(a, math.cos)
            elif op == "TANGENT":
                vec = self._vector_unary(a, math.tan)
            self._set_scalar_vector_outputs(node, vector_value=vec, float_value=scalar)
            return True

        if node_type == "AFNodeMix":
            factor = self._input_float(node, "Factor", 0.5)
            if bool(getattr(node, "clamp_factor", True)):
                factor = max(0.0, min(1.0, float(factor)))
            if node.mode == "VECTOR":
                a = self._input_vector(node, "A")
                b = self._input_vector(node, "B")
                value = a.lerp(b, factor)
                self._set_scalar_vector_outputs(node, vector_value=value)
            elif node.mode == "ROTATION":
                a = self._input_rotation(node, "A")
                b = self._input_rotation(node, "B")
                try:
                    value = a.slerp(b, float(factor))
                except Exception:
                    value = a.copy()
                self._set_output(node, "rotation_value", _quaternion_to_payload(value))
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
                "ROTATION": "AFSocketRotationValue",
                "MATRIX": "AFSocketMatrixValue",
                "PROPERTY_ASSIGNMENT": "AFSocketPropertyAssignment",
                "PROPERTY_PACKAGE": "AFSocketPropertyPackage",
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
                elif mode == "ROTATION":
                    value = self._typed_empty_output_value("rotation_value", node)
                elif mode == "MATRIX":
                    value = self._typed_empty_output_value("matrix_value", node)
                elif mode == "PROPERTY_ASSIGNMENT":
                    value = self._typed_empty_output_value("property_assignment", node)
                elif mode == "PROPERTY_PACKAGE":
                    value = self._typed_empty_output_value("property_package", node)
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
            elif mode == "ROTATION":
                value = _quaternion_to_payload(
                    self._input_rotation(
                        node,
                        selected_name,
                        tuple(getattr(selected_socket, "default_value", (1.0, 0.0, 0.0, 0.0))),
                    )
                )
            elif mode == "MATRIX":
                value = _matrix_to_payload(
                    self._input_matrix(
                        node,
                        selected_name,
                        tuple(getattr(selected_socket, "default_value", ())),
                    )
                )
            elif mode == "PROPERTY_ASSIGNMENT":
                value = self._get_linked_output(node, selected_name, "property_assignment")
            elif mode == "PROPERTY_PACKAGE":
                value = self._get_linked_output(node, selected_name, "property_package")
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
            mode = str(getattr(node, "mode", "FLOAT") or "FLOAT")
            if mode == "STRING":
                lhs = str(self._input_string_forgiving(node, "A", "") or "")
                rhs = str(self._input_string_forgiving(node, "B", "") or "")
                op = str(getattr(node, "string_operation", "EQUAL") or "EQUAL")
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

            op = node.operation
            if mode == "VECTOR":
                a = self._input_vector(node, "A")
                b = self._input_vector(node, "B")
                eps = max(0.0, float(self._input_float(node, "Epsilon", 1e-6)))
                vector_mode = str(getattr(node, "vector_mode", "ELEMENT") or "ELEMENT")
                if vector_mode == "ELEMENT":
                    value = all(
                        self._compare_numeric_values(float(lhs_component), float(rhs_component), op, eps)
                        for lhs_component, rhs_component in zip(tuple(a)[:3], tuple(b)[:3])
                    )
                    self._set_scalar_vector_outputs(node, bool_value=bool(value))
                    return True
                if vector_mode == "LENGTH":
                    lhs = float(a.length)
                    rhs = float(b.length)
                elif vector_mode == "AVERAGE":
                    lhs = (float(a.x) + float(a.y) + float(a.z)) / 3.0
                    rhs = (float(b.x) + float(b.y) + float(b.z)) / 3.0
                elif vector_mode == "DOT_PRODUCT":
                    lhs = float(a.dot(b))
                    rhs = self._input_float(node, "C", 0.0)
                elif vector_mode == "DIRECTION":
                    lhs_direction = _normalized_vector_or_none(a)
                    rhs_direction = _normalized_vector_or_none(b)
                    if lhs_direction is None or rhs_direction is None:
                        lhs = 0.0
                    else:
                        dot = max(-1.0, min(1.0, float(lhs_direction.dot(rhs_direction))))
                        lhs = float(math.acos(dot))
                    rhs = self._input_float(node, "Angle", 0.0)
                else:
                    lhs = float(a.length)
                    rhs = float(b.length)
            elif mode == "INTEGER":
                lhs = self._input_int(node, "A", 0)
                rhs = self._input_int(node, "B", 0)
                eps = 0.0
            else:
                lhs = self._input_float(node, "A", 0.0)
                rhs = self._input_float(node, "B", 0.0)
                if op in {"EQUAL", "NOT_EQUAL"}:
                    eps = max(0.0, float(self._input_float(node, "Epsilon", 1e-6)))
                else:
                    eps = 0.0

            value = self._compare_numeric_values(lhs, rhs, op, eps)
            self._set_scalar_vector_outputs(node, bool_value=value)
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
            if str(getattr(node, "mode", "FLOAT") or "FLOAT") == "VECTOR":
                value = self._input_vector(node, "Value", (0.0, 0.0, 0.0))
                from_min = self._input_vector(node, "From Min", (0.0, 0.0, 0.0))
                from_max = self._input_vector(node, "From Max", (1.0, 1.0, 1.0))
                to_min = self._input_vector(node, "To Min", (0.0, 0.0, 0.0))
                to_max = self._input_vector(node, "To Max", (1.0, 1.0, 1.0))
                components = []
                for component_value, component_from_min, component_from_max, component_to_min, component_to_max in zip(tuple(value)[:3], tuple(from_min)[:3], tuple(from_max)[:3], tuple(to_min)[:3], tuple(to_max)[:3]):
                    if float(component_from_max) == float(component_from_min):
                        mapped_component = float(component_to_min)
                    else:
                        t = (float(component_value) - float(component_from_min)) / (float(component_from_max) - float(component_from_min))
                        mapped_component = float(component_to_min) + t * (float(component_to_max) - float(component_to_min))
                    if bool(getattr(node, "clamp", True)):
                        lo = min(float(component_to_min), float(component_to_max))
                        hi = max(float(component_to_min), float(component_to_max))
                        mapped_component = max(lo, min(hi, mapped_component))
                    components.append(mapped_component)
                self._set_scalar_vector_outputs(node, vector_value=Vector(tuple(components)))
                return True
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
            if bool(getattr(node, "clamp", True)):
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

        if node_type == "AFNodeRotateVector":
            vec = self._input_vector(node, "Vector")
            rotation = self._input_rotation(node, "Rotation")
            rotated = rotation @ vec
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
            matrix_a_missing = self._matrix_input_has_no_effective_source(node, "Matrix A")
            matrix_b_missing = self._matrix_input_has_no_effective_source(node, "Matrix B")
            if matrix_b_missing and not matrix_a_missing:
                linked_value = self._get_linked_output(node, "Matrix A", "matrix_value")
                if linked_value is not None:
                    self._set_output(node, "matrix_value", linked_value)
                    return True
            if matrix_a_missing and not matrix_b_missing:
                linked_value = self._get_linked_output(node, "Matrix B", "matrix_value")
                if linked_value is not None:
                    self._set_output(node, "matrix_value", linked_value)
                    return True
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
