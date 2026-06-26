import math

from mathutils import Euler, Matrix, Quaternion, Vector


ROTATION_IDENTITY_QUATERNION = (1.0, 0.0, 0.0, 0.0)
SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE = {
    "BOOLEAN": "bool_value",
    "FLOAT": "float_value",
    "INTEGER": "int_value",
    "VECTOR": "vector_value",
    "ROTATION": "rotation_value",
    "MATRIX": "matrix_value",
    "PROPERTY_ASSIGNMENT": "property_assignment",
}
CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE = {
    "FLOAT": "float_value",
    "INTEGER": "int_value",
    "VECTOR": "vector_value",
}


def _identity_rotation_payload():
    return {
        "__af_rotation__": True,
        "quaternion": [float(component) for component in ROTATION_IDENTITY_QUATERNION],
    }


def _identity_matrix_payload():
    return {
        "__af_matrix__": True,
        "rows": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def _is_rotation_payload(value):
    return isinstance(value, dict) and bool(value.get("__af_rotation__"))


def _is_matrix_payload(value):
    return isinstance(value, dict) and bool(value.get("__af_matrix__"))


def _quaternion_magnitude(quaternion):
    quat = Quaternion(quaternion) if not isinstance(quaternion, Quaternion) else quaternion
    return math.sqrt(
        float(quat.w) * float(quat.w)
        + float(quat.x) * float(quat.x)
        + float(quat.y) * float(quat.y)
        + float(quat.z) * float(quat.z)
    )


def _quaternion_to_payload(quaternion):
    if isinstance(quaternion, Quaternion):
        quat = quaternion.copy()
    else:
        quat = Quaternion(tuple(float(component) for component in tuple(quaternion)[:4]))
    if _quaternion_magnitude(quat) <= 1e-8:
        quat = Quaternion(ROTATION_IDENTITY_QUATERNION)
    else:
        quat.normalize()
    return {
        "__af_rotation__": True,
        "quaternion": [float(quat.w), float(quat.x), float(quat.y), float(quat.z)],
    }


def _rotation_mode_values_to_quaternion(rotation_mode, rotation_values):
    resolved_mode = str(rotation_mode or "XYZ")
    values = [float(component) for component in list(rotation_values or [])]
    if resolved_mode == "QUATERNION" and len(values) >= 4:
        quat = Quaternion(tuple(values[:4]))
    elif resolved_mode == "AXIS_ANGLE" and len(values) >= 4:
        axis = Vector(tuple(values[1:4]))
        if axis.length <= 1e-8:
            quat = Quaternion(ROTATION_IDENTITY_QUATERNION)
        else:
            quat = Quaternion(axis.normalized(), float(values[0]))
    elif len(values) >= 3:
        euler_mode = resolved_mode if resolved_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"} else "XYZ"
        quat = Euler(tuple(values[:3]), euler_mode).to_quaternion()
    else:
        quat = Quaternion(ROTATION_IDENTITY_QUATERNION)
    if _quaternion_magnitude(quat) <= 1e-8:
        return Quaternion(ROTATION_IDENTITY_QUATERNION)
    quat.normalize()
    return quat


def _rotation_mode_values_to_payload(rotation_mode, rotation_values):
    return _quaternion_to_payload(_rotation_mode_values_to_quaternion(rotation_mode, rotation_values))


def _payload_to_quaternion(value):
    if isinstance(value, Quaternion):
        quat = value.copy()
    elif isinstance(value, Euler):
        quat = value.to_quaternion()
    elif _is_rotation_payload(value):
        quaternion_values = list(value.get("quaternion", []))
        if len(quaternion_values) >= 4:
            quat = Quaternion(tuple(float(component) for component in quaternion_values[:4]))
        else:
            quat = Quaternion(ROTATION_IDENTITY_QUATERNION)
    elif isinstance(value, (list, tuple)) and len(value) >= 4:
        quat = Quaternion(tuple(float(component) for component in value[:4]))
    else:
        quat = Quaternion(ROTATION_IDENTITY_QUATERNION)
    if _quaternion_magnitude(quat) <= 1e-8:
        return Quaternion(ROTATION_IDENTITY_QUATERNION)
    quat.normalize()
    return quat


def _matrix_to_payload(matrix_value):
    if isinstance(matrix_value, Matrix):
        matrix = matrix_value.copy()
    else:
        matrix = Matrix(matrix_value)
    if len(matrix.col) == 3:
        matrix = matrix.to_4x4()
    rows = []
    for row_index in range(4):
        rows.append([float(matrix[row_index][column_index]) for column_index in range(4)])
    return {
        "__af_matrix__": True,
        "rows": rows,
    }


def _payload_to_matrix(value):
    if isinstance(value, Matrix):
        matrix = value.copy()
    elif _is_matrix_payload(value):
        rows = value.get("rows", [])
        matrix = Matrix(tuple(tuple(float(component) for component in list(row)[:4]) for row in list(rows)[:4]))
    elif isinstance(value, (list, tuple)):
        components = list(value)
        if len(components) == 16:
            matrix = Matrix(
                tuple(
                    tuple(float(components[row_index * 4 + column_index]) for column_index in range(4))
                    for row_index in range(4)
                )
            )
        else:
            matrix = Matrix(value)
    else:
        matrix = Matrix.Identity(4)
    if len(matrix.col) == 3:
        matrix = matrix.to_4x4()
    row_count = len(matrix)
    col_count = len(matrix[0]) if row_count else 0
    if col_count != 4 or row_count != 4:
        matrix = matrix.to_4x4()
    return matrix


def _axis_vector_from_enum(identifier):
    identifier = str(identifier or "Z")
    if identifier == "X":
        return Vector((1.0, 0.0, 0.0))
    if identifier == "Y":
        return Vector((0.0, 1.0, 0.0))
    return Vector((0.0, 0.0, 1.0))


def _normalized_vector_or_none(value):
    vector = Vector(value)
    if float(vector.length) <= 1e-8:
        return None
    return vector.normalized()


def _rotation_from_axes(primary_vector, secondary_vector, primary_axis, secondary_axis):
    primary = _normalized_vector_or_none(primary_vector)
    secondary_source = _normalized_vector_or_none(secondary_vector)
    if primary is None:
        return Quaternion(ROTATION_IDENTITY_QUATERNION)
    if secondary_source is None or str(primary_axis or "Z") == str(secondary_axis or "X"):
        secondary_source = Vector((1.0, 0.0, 0.0)) if abs(primary.dot(Vector((1.0, 0.0, 0.0)))) < 0.999 else Vector((0.0, 1.0, 0.0))

    secondary = secondary_source - primary * primary.dot(secondary_source)
    if float(secondary.length) <= 1e-8:
        fallback = Vector((1.0, 0.0, 0.0)) if abs(primary.dot(Vector((1.0, 0.0, 0.0)))) < 0.999 else Vector((0.0, 1.0, 0.0))
        secondary = fallback - primary * primary.dot(fallback)
    if float(secondary.length) <= 1e-8:
        return Quaternion(ROTATION_IDENTITY_QUATERNION)
    secondary.normalize()

    axes = {
        str(primary_axis or "Z"): primary,
        str(secondary_axis or "X"): secondary,
    }
    if "X" in axes and "Y" in axes and "Z" not in axes:
        axes["Z"] = axes["X"].cross(axes["Y"])
    elif "Y" in axes and "Z" in axes and "X" not in axes:
        axes["X"] = axes["Y"].cross(axes["Z"])
    elif "Z" in axes and "X" in axes and "Y" not in axes:
        axes["Y"] = axes["Z"].cross(axes["X"])

    x_axis = _normalized_vector_or_none(axes.get("X", Vector((1.0, 0.0, 0.0)))) or Vector((1.0, 0.0, 0.0))
    y_axis = _normalized_vector_or_none(axes.get("Y", Vector((0.0, 1.0, 0.0)))) or Vector((0.0, 1.0, 0.0))
    z_axis = _normalized_vector_or_none(axes.get("Z", Vector((0.0, 0.0, 1.0)))) or Vector((0.0, 0.0, 1.0))

    basis_matrix = Matrix((x_axis, y_axis, z_axis)).transposed()
    if float(basis_matrix.determinant()) < 0.0:
        if str(primary_axis or "Z") != "X":
            x_axis = -x_axis
        elif str(primary_axis or "Z") != "Y":
            y_axis = -y_axis
        else:
            z_axis = -z_axis
        basis_matrix = Matrix((x_axis, y_axis, z_axis)).transposed()
    return basis_matrix.to_quaternion()


def _rotation_align_to_vector(rotation_value, target_vector, axis, pivot_axis, factor):
    base_quaternion = _payload_to_quaternion(rotation_value)
    target = _normalized_vector_or_none(target_vector)
    if target is None:
        return base_quaternion
    amount = max(0.0, min(1.0, float(factor)))
    if amount <= 0.0:
        return base_quaternion

    current_axis = base_quaternion @ _axis_vector_from_enum(axis)
    current_axis = _normalized_vector_or_none(current_axis) or _axis_vector_from_enum(axis)

    if str(pivot_axis or "AUTO") == "AUTO":
        delta = current_axis.rotation_difference(target)
    else:
        pivot_world = base_quaternion @ _axis_vector_from_enum(pivot_axis)
        pivot_world = _normalized_vector_or_none(pivot_world)
        if pivot_world is None:
            return base_quaternion
        current_projected = current_axis - pivot_world * current_axis.dot(pivot_world)
        target_projected = target - pivot_world * target.dot(pivot_world)
        current_projected = _normalized_vector_or_none(current_projected)
        target_projected = _normalized_vector_or_none(target_projected)
        if current_projected is None or target_projected is None:
            return base_quaternion
        angle = current_projected.angle(target_projected, 0.0)
        cross = current_projected.cross(target_projected)
        if cross.dot(pivot_world) < 0.0:
            angle *= -1.0
        delta = Quaternion(pivot_world, angle)

    if float(delta.angle) <= 1e-8:
        return base_quaternion
    blended_delta = Quaternion(delta.axis, float(delta.angle) * amount)
    result = blended_delta @ base_quaternion
    if _quaternion_magnitude(result) <= 1e-8:
        return Quaternion(ROTATION_IDENTITY_QUATERNION)
    result.normalize()
    return result


def _sample_object_index_output_key_for_mode(mode):
    return SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE.get(str(mode or "FLOAT"), "float_value")


def _context_reduce_output_key_for_type(value_type):
    return CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE.get(str(value_type or "FLOAT"), "float_value")


def _median_numeric(values):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) * 0.5)


def _population_variance(values):
    ordered = [float(value) for value in values]
    if not ordered:
        return 0.0
    mean_value = sum(ordered) / float(len(ordered))
    return float(sum((value - mean_value) * (value - mean_value) for value in ordered) / float(len(ordered)))

