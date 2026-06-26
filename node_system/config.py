from .socket_aliases import (
    PROPERTY_ASSIGNMENT_INPUT_PREFIX,
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)

SORT_MODE_ITEMS = (
    ("NAME_ASC", "Name A-Z", "Sort names ascending"),
    ("NAME_DESC", "Name Z-A", "Sort names descending"),
)

PROPERTY_PACKAGE_FILTER_MODE_ITEMS = (
    ("KEEP_MATCHED", "Keep Matched", "Keep items whose objects are in the Object List"),
    ("REMOVE_MATCHED", "Remove Matched", "Remove items whose objects are in the Object List"),
)

PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS = (
    ("LAST_WINS", "Last Wins", "Use Add Package values when properties conflict"),
    ("FIRST_WINS", "First Wins", "Keep Base Package values when properties conflict"),
    ("ERROR", "Error", "Fail if a property conflict is found"),
)

OBJECT_DISPLAY_TYPE_ITEMS = (
    ("TEXTURED", "Textured", "Display the object with textured shading"),
    ("SOLID", "Solid", "Display the object with solid shading"),
    ("WIRE", "Wire", "Display the object as wireframe"),
    ("BOUNDS", "Bounds", "Display the object bounds only"),
)

OBJECT_ROTATION_MODE_ITEMS = (
    ("XYZ", "XYZ Euler", "Use XYZ Euler rotation"),
    ("XZY", "XZY Euler", "Use XZY Euler rotation"),
    ("YXZ", "YXZ Euler", "Use YXZ Euler rotation"),
    ("YZX", "YZX Euler", "Use YZX Euler rotation"),
    ("ZXY", "ZXY Euler", "Use ZXY Euler rotation"),
    ("ZYX", "ZYX Euler", "Use ZYX Euler rotation"),
    ("QUATERNION", "Quaternion", "Use Quaternion rotation"),
    ("AXIS_ANGLE", "Axis Angle", "Use Axis Angle rotation"),
)

OBJECT_INTERACTION_MODE_ITEMS = (
    ("OBJECT", "Object Mode", "Stay true while Object Mode is active"),
    ("EDIT", "Edit Mode", "Stay true while Edit Mode is active"),
    ("SCULPT", "Sculpt Mode", "Stay true while Sculpt Mode is active"),
    ("POSE", "Pose Mode", "Stay true while Pose Mode is active"),
    ("WEIGHT_PAINT", "Weight Paint", "Stay true while Weight Paint Mode is active"),
    ("VERTEX_PAINT", "Vertex Paint", "Stay true while Vertex Paint Mode is active"),
    ("TEXTURE_PAINT", "Texture Paint", "Stay true while Texture Paint Mode is active"),
)

VIEWPORT_SHADING_MODE_ITEMS = (
    ("WIREFRAME", "Wireframe", "Stay true while Wireframe shading is active"),
    ("SOLID", "Solid", "Stay true while Solid shading is active"),
    ("MATERIAL", "Material Preview", "Stay true while Material Preview shading is active"),
    ("RENDERED", "Rendered", "Stay true while Rendered shading is active"),
)

ROTATION_AXIS_ITEMS = (
    ("X", "X", "Use the X axis"),
    ("Y", "Y", "Use the Y axis"),
    ("Z", "Z", "Use the Z axis"),
)

ROTATION_PIVOT_AXIS_ITEMS = (
    ("AUTO", "Auto", "Choose the pivot axis automatically"),
    ("X", "X", "Use the X axis as the pivot"),
    ("Y", "Y", "Use the Y axis as the pivot"),
    ("Z", "Z", "Use the Z axis as the pivot"),
)

ROTATION_SPACE_ITEMS = (
    ("GLOBAL", "Global", "Apply the extra rotation in global space"),
    ("LOCAL", "Local", "Apply the extra rotation in local space"),
)

FLOAT_MATH_OPERATION_ITEMS = (
    ("ADD", "Add", "A + B"),
    ("SUBTRACT", "Subtract", "A - B"),
    ("MULTIPLY", "Multiply", "A * B"),
    ("DIVIDE", "Divide", "A / B"),
    ("MULTIPLY_ADD", "Multiply Add", "A * B + C"),
    ("POWER", "Raise to Power", "A power B"),
    ("LOGARITHM", "Logarithm", "Logarithm A base B"),
    ("SQRT", "Square Root", "Square root of A"),
    ("INVERSE_SQRT", "Inverse Square Root", "1 / Square root of A"),
    ("ABSOLUTE", "Absolute", "Magnitude of A"),
    ("EXPONENT", "Exponent", "exp(A)"),
    ("MINIMUM", "Minimum", "The minimum from A and B"),
    ("MAXIMUM", "Maximum", "The maximum from A and B"),
    ("LESS_THAN", "Less Than", "1 if A < B else 0"),
    ("GREATER_THAN", "Greater Than", "1 if A > B else 0"),
    ("SIGN", "Sign", "Returns the sign of A"),
    ("COMPARE", "Compare", "1 if (A == B) within tolerance C else 0"),
    ("SMOOTH_MIN", "Smooth Minimum", "The minimum from A and B with smoothing C"),
    ("SMOOTH_MAX", "Smooth Maximum", "The maximum from A and B with smoothing C"),
    ("ROUND", "Round", "Round A to the nearest integer. Round upward if the fraction part is 0.5"),
    ("FLOOR", "Floor", "The largest integer smaller than or equal A"),
    ("CEIL", "Ceil", "The smallest integer greater than or equal A"),
    ("TRUNC", "Truncate", "The integer part of A, removing fractional digits"),
    ("FRACT", "Fraction", "The fraction part of A"),
    ("MODULO", "Truncated Modulo", "The remainder of truncated division using fmod(A,B)"),
    ("FLOORED_MODULO", "Floored Modulo", "The remainder of floored division"),
    ("WRAP", "Wrap", "Wrap value to range"),
    ("SNAP", "Snap", "Snap to increment, snap(A,B)"),
    ("PINGPONG", "Ping-Pong", "Wraps a value and reverses every other cycle (A,B)"),
    ("SINE", "Sine", "sin(A)"),
    ("COSINE", "Cosine", "cos(A)"),
    ("TANGENT", "Tangent", "tan(A)"),
    ("ARCSINE", "Arcsine", "arcsin(A)"),
    ("ARCCOSINE", "Arccosine", "arccos(A)"),
    ("ARCTANGENT", "Arctangent", "arctan(A)"),
    ("ARCTAN2", "Arctan2", "The signed angle arctan(A / B)"),
    ("SINH", "Hyperbolic Sine", "sinh(A)"),
    ("COSH", "Hyperbolic Cosine", "cosh(A)"),
    ("TANH", "Hyperbolic Tangent", "tanh(A)"),
    ("RADIANS", "To Radians", "Convert from degrees to radians"),
    ("DEGREES", "To Degrees", "Convert from radians to degrees"),
)

INTEGER_MATH_OPERATION_ITEMS = (
    ("ADD", "Add", "A + B"),
    ("SUBTRACT", "Subtract", "A - B"),
    ("MULTIPLY", "Multiply", "A * B"),
    ("DIVIDE", "Divide", "A / B"),
    ("MULTIPLY_ADD", "Multiply Add", "A * B + C"),
    ("ABSOLUTE", "Absolute", "Non-negative value of A, abs(A)"),
    ("NEGATE", "Negate", "-A"),
    ("POWER", "Raise to Power", "A power B, pow(A,B)"),
    ("MINIMUM", "Minimum", "The minimum value from A and B, min(A,B)"),
    ("MAXIMUM", "Maximum", "The maximum value from A and B, max(A,B)"),
    ("SIGN", "Sign", "Return the sign of A, sign(A)"),
    ("DIVIDE_ROUND", "Divide Round", "Divide and round result to the nearest integer"),
    ("DIVIDE_FLOOR", "Divide Floor", "Divide and floor result, the largest integer smaller than or equal A / B"),
    ("DIVIDE_CEIL", "Divide Ceiling", "Divide and ceil result, the smallest integer greater than or equal A / B"),
    ("FLOORED_MODULO", "Floored Modulo", "Modulo that is periodic for both negative and positive operands"),
    ("MODULO", "Modulo", "Modulo which is the remainder of A / B"),
    ("GCD", "Greatest Common Divisor", "The largest positive integer that divides into each of the values A and B"),
    ("LCM", "Least Common Multiple", "The smallest positive integer that is divisible by both A and B"),
)

BOOLEAN_MATH_OPERATION_ITEMS = (
    ("AND", "And", "True when both inputs are true"),
    ("OR", "Or", "True when at least one input is true"),
    ("NOT", "Not", "Opposite of the input"),
    ("NAND", "Not And", "True when at least one input is false"),
    ("NOR", "Nor", "True when both inputs are false"),
    ("XNOR", "Equal", "True when both inputs are equal (exclusive nor)"),
    ("XOR", "Not Equal", "True when both inputs are different (exclusive or)"),
    ("IMPLY", "Imply", "True unless the first input is true and the second is false"),
    ("NIMPLY", "Subtract", "True when the first input is true and the second is false (not imply)"),
)

VECTOR_MATH_OPERATION_ITEMS = (
    ("ADD", "Add", "A + B"),
    ("SUBTRACT", "Subtract", "A - B"),
    ("MULTIPLY", "Multiply", "Entry-wise multiply"),
    ("DIVIDE", "Divide", "Entry-wise divide"),
    ("MULTIPLY_ADD", "Multiply Add", "A * B + C"),
    ("CROSS_PRODUCT", "Cross Product", "A cross B"),
    ("PROJECT", "Project", "Project A onto B"),
    ("REFLECT", "Reflect", "Reflect A around the normal B. B does not need to be normalized."),
    ("REFRACT", "Refract", "Return the refraction vector for incident A, normal B, and IOR ratio"),
    ("FACEFORWARD", "Faceforward", "Orient vector A away from surface B using reference normal C"),
    ("DOT_PRODUCT", "Dot Product", "A dot B"),
    ("DISTANCE", "Distance", "Distance between A and B"),
    ("LENGTH", "Length", "Length of A"),
    ("SCALE", "Scale", "A multiplied by Scale"),
    ("NORMALIZE", "Normalize", "Normalize A"),
    ("ABSOLUTE", "Absolute", "Entry-wise absolute"),
    ("POWER", "Raise to Power", "Entry-wise power"),
    ("SIGN", "Sign", "Entry-wise sign"),
    ("MINIMUM", "Minimum", "Entry-wise minimum"),
    ("MAXIMUM", "Maximum", "Entry-wise maximum"),
    ("ROUND", "Round", "Entry-wise round to the nearest integer. Round upward if the fraction part is 0.5"),
    ("FLOOR", "Floor", "Entry-wise floor"),
    ("CEIL", "Ceil", "Entry-wise ceil"),
    ("FRACTION", "Fraction", "The fraction part of A entry-wise"),
    ("MODULO", "Modulo", "Entry-wise modulo using fmod(A,B)"),
    ("WRAP", "Wrap", "Entry-wise wrap(A,B,C)"),
    ("SNAP", "Snap", "Round A to the largest integer multiple of B less than or equal A"),
    ("SINE", "Sine", "Entry-wise sin(A)"),
    ("COSINE", "Cosine", "Entry-wise cos(A)"),
    ("TANGENT", "Tangent", "Entry-wise tan(A)"),
)

COMPARE_OPERATION_ITEMS = (
    ("EQUAL", "Equal", ""),
    ("NOT_EQUAL", "Not Equal", ""),
    ("LESS_THAN", "Less Than", ""),
    ("LESS_EQUAL", "Less Equal", ""),
    ("GREATER_THAN", "Greater Than", ""),
    ("GREATER_EQUAL", "Greater Equal", ""),
)

STRING_COMPARE_OPERATION_ITEMS = (
    ("EQUAL", "Equal", ""),
    ("NOT_EQUAL", "Not Equal", ""),
    ("CONTAINS", "Contains", ""),
    ("STARTS_WITH", "Starts With", ""),
    ("ENDS_WITH", "Ends With", ""),
)

COMPARE_VECTOR_MODE_ITEMS = (
    ("ELEMENT", "Element-Wise", ""),
    ("LENGTH", "Length", ""),
    ("AVERAGE", "Average", ""),
    ("DOT_PRODUCT", "Dot Product", ""),
    ("DIRECTION", "Direction", ""),
)

RANDOM_TYPE_ITEMS = (
    ("FLOAT", "Float", ""),
    ("BOOLEAN", "Boolean", ""),
    ("VECTOR", "Vector", ""),
)

MIX_MODE_ITEMS = (
    ("FLOAT", "Float", ""),
    ("VECTOR", "Vector", ""),
    ("ROTATION", "Rotation", ""),
)

MAP_RANGE_MODE_ITEMS = (
    ("FLOAT", "Float", ""),
    ("VECTOR", "Vector", ""),
)

SWITCH_MODE_ITEMS = (
    ("BOOLEAN", "Boolean", ""),
    ("FLOAT", "Float", ""),
    ("INTEGER", "Integer", ""),
    ("STRING", "String", ""),
    ("VECTOR", "Vector", ""),
    ("ROTATION", "Rotation", ""),
    ("MATRIX", "Matrix", ""),
    ("PROPERTY_ASSIGNMENT", PROPERTY_ASSIGNMENT_SOCKET_NAME, ""),
    ("PROPERTY_PACKAGE", PROPERTY_PACKAGE_SOCKET_NAME, ""),
    ("DISPLAY_TYPE", "Display Type", ""),
    ("ROTATION_MODE", "Rotation Mode", ""),
)

INDEX_SWITCH_MODE_ITEMS = (
    ("BOOLEAN", "Boolean", ""),
    ("FLOAT", "Float", ""),
    ("INTEGER", "Integer", ""),
    ("VECTOR", "Vector", ""),
    ("ROTATION", "Rotation", ""),
    ("MATRIX", "Matrix", ""),
    ("PROPERTY_ASSIGNMENT", PROPERTY_ASSIGNMENT_SOCKET_NAME, ""),
    ("PROPERTY_PACKAGE", PROPERTY_PACKAGE_SOCKET_NAME, ""),
    ("STRING", "String", ""),
    ("DISPLAY_TYPE", "Display Type", ""),
    ("ROTATION_MODE", "Rotation Mode", ""),
)

COMPARE_MODE_ITEMS = (
    ("FLOAT", "Float", ""),
    ("INTEGER", "Integer", ""),
    ("STRING", "String", ""),
    ("VECTOR", "Vector", ""),
)

CONVERSION_MODE_ITEMS = (
    ("BOOL_TO_INT", "Boolean to Integer", ""),
    ("BOOL_TO_FLOAT", "Boolean to Float", ""),
    ("BOOL_TO_VECTOR", "Boolean to Vector", ""),
    ("INT_TO_BOOL", "Integer to Boolean", ""),
    ("INT_TO_FLOAT", "Integer to Float", ""),
    ("INT_TO_VECTOR", "Integer to Vector", ""),
    ("FLOAT_TO_BOOL", "Float to Boolean", ""),
    ("FLOAT_TO_INT", "Float to Integer", ""),
    ("FLOAT_TO_VECTOR", "Float to Vector", ""),
    ("VECTOR_TO_BOOL", "Vector to Boolean", ""),
    ("VECTOR_TO_INT", "Vector to Integer", ""),
    ("VECTOR_TO_FLOAT", "Vector to Float", ""),
)

VECTOR_COMPONENT_MODE_ITEMS = (
    ("X", "X", ""),
    ("Y", "Y", ""),
    ("Z", "Z", ""),
    ("LENGTH", "Length", ""),
    ("AVERAGE", "Average", ""),
)

VECTOR_BOOL_MODE_ITEMS = (
    ("ANY_NONZERO", "Any Non-Zero", ""),
    ("ALL_NONZERO", "All Non-Zero", ""),
    ("LENGTH_NONZERO", "Length Non-Zero", ""),
)

RENDER_MODE_ITEMS = (
    ("STILL", "Still", "Render a single frame"),
    ("ANIMATION", "Animation", "Render a frame range"),
)

RUN_TASK_PLAN_FAILURE_POLICY_ITEMS = (
    ("STOP_ON_FAILURE", "Stop On Failure", "Stop when any enabled Task Plan fails"),
    ("CONTINUE_ON_FAILURE", "Continue On Failure", "Continue running later enabled Task Plans after a failure"),
)

STATUS_VALUE_ITEMS = (
    ("READY", "Ready", "", 0, 0),
    ("DONE", "Done", "", 0, 1),
    ("FAILED", "Failed", "", 0, 2),
    ("SKIPPED", "Skipped", "", 0, 3),
    ("INVALID", "Invalid", "", 0, 4),
    ("WARNING", "Warning", "", 0, 5),
    ("CANCELLED", "Cancelled", "", 0, 6),
    ("RUNNING", "Running", "", 0, 7),
    ("WAITING", "Waiting", "", 0, 8),
    ("IDLE", "Idle", "", 0, 9),
)

CONVERSION_SOCKET_MAP = {
    "BOOL_TO_INT": ("NodeSocketBool", "NodeSocketInt"),
    "BOOL_TO_FLOAT": ("NodeSocketBool", "NodeSocketFloat"),
    "BOOL_TO_VECTOR": ("NodeSocketBool", "NodeSocketVector"),
    "INT_TO_BOOL": ("NodeSocketInt", "NodeSocketBool"),
    "INT_TO_FLOAT": ("NodeSocketInt", "NodeSocketFloat"),
    "INT_TO_VECTOR": ("NodeSocketInt", "NodeSocketVector"),
    "FLOAT_TO_BOOL": ("NodeSocketFloat", "NodeSocketBool"),
    "FLOAT_TO_INT": ("NodeSocketFloat", "NodeSocketInt"),
    "FLOAT_TO_VECTOR": ("NodeSocketFloat", "NodeSocketVector"),
    "VECTOR_TO_BOOL": ("NodeSocketVector", "NodeSocketBool"),
    "VECTOR_TO_INT": ("NodeSocketVector", "NodeSocketInt"),
    "VECTOR_TO_FLOAT": ("NodeSocketVector", "NodeSocketFloat"),
}

PROPERTY_DATA_FIELD_SPECS = {
    "AFNodeModifierPropertyData": (
        {
            "key": "show_viewport",
            "label": "Show Viewport",
            "input_socket": "Show Viewport",
            "output_socket": "Show Viewport",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_viewport",
            "source_attr": "source_show_viewport",
            "supports_context": True,
        },
        {
            "key": "show_render",
            "label": "Show Render",
            "input_socket": "Show Render",
            "output_socket": "Show Render",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_render",
            "source_attr": "source_show_render",
            "supports_context": True,
        },
        {
            "key": "show_in_editmode",
            "label": "Show In Edit Mode",
            "input_socket": "Show In Edit Mode",
            "output_socket": "Show In Edit Mode",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_in_editmode",
            "source_attr": "source_show_in_editmode",
            "supports_context": True,
        },
    ),
    "AFNodeObjectDisplayPropertyData": (
        {
            "key": "hide_viewport",
            "label": "Hide Viewport",
            "input_socket": "Hide Viewport",
            "output_socket": "Hide Viewport",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_hide_viewport",
            "source_attr": "source_hide_viewport",
            "supports_context": True,
        },
        {
            "key": "hide_render",
            "label": "Hide Render",
            "input_socket": "Hide Render",
            "output_socket": "Hide Render",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_hide_render",
            "source_attr": "source_hide_render",
            "supports_context": True,
        },
        {
            "key": "show_in_front",
            "label": "Show In Front",
            "input_socket": "Show In Front",
            "output_socket": "Show In Front",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_in_front",
            "source_attr": "source_show_in_front",
            "supports_context": True,
        },
        {
            "key": "show_name",
            "label": "Show Name",
            "input_socket": "Show Name",
            "output_socket": "Show Name",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_name",
            "source_attr": "source_show_name",
            "supports_context": True,
        },
        {
            "key": "show_axis",
            "label": "Show Axis",
            "input_socket": "Show Axis",
            "output_socket": "Show Axis",
            "socket_idname": "AFSocketBooleanValue",
            "capture_attr": "capture_show_axis",
            "source_attr": "source_show_axis",
            "supports_context": True,
        },
        {
            "key": "display_type",
            "label": "Display Type",
            "input_socket": "Display Type",
            "output_socket": "Display Type",
            "socket_idname": "AFSocketDisplayType",
            "capture_attr": "capture_display_type",
            "source_attr": "source_display_type",
            "target_attr": "target_display_type",
            "supports_context": True,
        },
    ),
    "AFNodeObjectTransformPropertyData": (
        {
            "key": "location",
            "label": "Location",
            "input_socket": "Location",
            "output_socket": "Location",
            "socket_idname": "AFSocketVectorValue",
            "capture_attr": "capture_location",
            "source_attr": "source_location",
            "supports_context": True,
        },
        {
            "key": "rotation",
            "label": "Rotation",
            "input_socket": "Rotation",
            "output_socket": "Rotation",
            "socket_idname": "AFSocketRotationValue",
            "capture_attr": "capture_rotation",
            "source_attr": "source_rotation",
            "supports_context": True,
        },
        {
            "key": "scale",
            "label": "Scale",
            "input_socket": "Scale",
            "output_socket": "Scale",
            "socket_idname": "AFSocketVectorValue",
            "capture_attr": "capture_scale",
            "source_attr": "source_scale",
            "target_attr": "target_scale",
            "supports_context": True,
        },
        {
            "key": "rotation_mode",
            "label": "Rotation Mode",
            "input_socket": "Rotation Mode",
            "output_socket": "Rotation Mode",
            "socket_idname": "AFSocketRotationMode",
            "capture_attr": "capture_rotation_mode",
            "source_attr": "source_rotation_mode",
            "target_attr": "target_rotation_mode",
            "supports_context": True,
        },
    ),
}

PHYSICS_BAKE_TASK_INPUT_PREFIX = "Settings "
PHYSICS_BAKE_TASK_SOCKET_IDNAME = "AFSocketPropertyPackage"
PHYSICS_BAKE_TASK_VIRTUAL_LABEL = " "
RUN_TASK_PLAN_INPUT_PREFIX = "Task Plan "
RUN_TASK_PLAN_VIRTUAL_LABEL = " "
PROPERTY_ASSIGNMENT_VIRTUAL_LABEL = " "
INDEX_SWITCH_VIRTUAL_LABEL = " "

CUSTOM_NUMERIC_SOCKET_IDNAMES = {
    "AFSocketBooleanValue",
    "AFSocketFloatValue",
    "AFSocketIntegerValue",
    "AFSocketVectorValue",
}

CUSTOM_MENU_SOCKET_IDNAMES = {
    "AFSocketDisplayType",
    "AFSocketObjectInteractionMode",
    "AFSocketRotationMode",
    "AFSocketViewportShadingMode",
}

NUMERIC_COMPATIBLE_SOCKET_IDNAMES = {
    "NodeSocketBool",
    "NodeSocketFloat",
    "NodeSocketInt",
    "NodeSocketVector",
    *CUSTOM_NUMERIC_SOCKET_IDNAMES,
}

INDEX_SWITCH_SOCKET_IDNAME_BY_MODE = {
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
}

SWITCH_SOCKET_IDNAME_BY_MODE = {
    "BOOLEAN": "NodeSocketBool",
    "FLOAT": "NodeSocketFloat",
    "INTEGER": "NodeSocketInt",
    "STRING": "AFSocketString",
    "VECTOR": "NodeSocketVector",
    "ROTATION": "NodeSocketRotation",
    "MATRIX": "NodeSocketMatrix",
    "PROPERTY_ASSIGNMENT": "AFSocketPropertyAssignment",
    "PROPERTY_PACKAGE": "AFSocketPropertyPackage",
    "DISPLAY_TYPE": "AFSocketDisplayType",
    "ROTATION_MODE": "AFSocketRotationMode",
}

GROUP_SUPPORTED_SOCKET_IDNAMES = {
    "AFSocketFlow",
    "AFSocketCollectionList",
    "AFSocketString",
    "NodeSocketString",
    "AFSocketObjectList",
    "AFSocketPropertyPackage",
    "AFSocketPropertyDefinition",
    "AFSocketPropertyAssignment",
    "AFSocketTaskRef",
    "AFSocketTaskPlan",
    "AFSocketTaskHandle",
    "AFSocketReport",
    "AFSocketBooleanValue",
    "AFSocketFloatValue",
    "AFSocketIntegerValue",
    "AFSocketVectorValue",
    "AFSocketDisplayType",
    "AFSocketObjectInteractionMode",
    "AFSocketRotationMode",
    "AFSocketViewportShadingMode",
    "NodeSocketInt",
    "NodeSocketFloat",
    "NodeSocketBool",
    "NodeSocketVector",
    "NodeSocketRotation",
    "NodeSocketMatrix",
}

GROUP_NODE_INPUT_IDENTIFIERS_KEY = "af_group_input_identifiers"
GROUP_NODE_OUTPUT_IDENTIFIERS_KEY = "af_group_output_identifiers"

GROUP_RESERVED_SOCKET_TYPES = {
    ("INPUT", "Flow In"): "AFSocketFlow",
    ("OUTPUT", "Flow Out"): "AFSocketFlow",
    ("INPUT", "Task Ref"): "AFSocketTaskRef",
    ("OUTPUT", "Task Plan"): "AFSocketTaskPlan",
    ("OUTPUT", "Status"): "NodeSocketString",
    ("OUTPUT", "Report"): "AFSocketReport",
}

PAIR_NODE_TYPE_MAP = {
    "AFNodeStart": ("EXECUTION", "START", "AFNodeEnd"),
    "AFNodeEnd": ("EXECUTION", "END", "AFNodeStart"),
    "AFNodeTaskStart": ("TASK", "START", "AFNodeTaskOutput"),
    "AFNodeTaskOutput": ("TASK", "END", "AFNodeTaskStart"),
    "AFNodeRepeatStart": ("REPEAT", "START", "AFNodeRepeatEnd"),
    "AFNodeRepeatEnd": ("REPEAT", "END", "AFNodeRepeatStart"),
    "AFNodeSubflowStart": ("SUBFLOW", "START", "AFNodeSubflowJoin"),
    "AFNodeSubflowJoin": ("SUBFLOW", "END", "AFNodeSubflowStart"),
    "AFNodeBranchStart": ("BRANCH", "START", "AFNodeBranchEnd"),
    "AFNodeBranchEnd": ("BRANCH", "END", "AFNodeBranchStart"),
}

PAIR_KIND_START_TYPE = {
    "EXECUTION": "AFNodeStart",
    "TASK": "AFNodeTaskStart",
    "REPEAT": "AFNodeRepeatStart",
    "SUBFLOW": "AFNodeSubflowStart",
    "BRANCH": "AFNodeBranchStart",
}

PAIR_KIND_END_TYPE = {
    "EXECUTION": "AFNodeEnd",
    "TASK": "AFNodeTaskOutput",
    "REPEAT": "AFNodeRepeatEnd",
    "SUBFLOW": "AFNodeSubflowJoin",
    "BRANCH": "AFNodeBranchEnd",
}

PAIR_KIND_END_INPUT_SOCKET = {
    "EXECUTION": "Flow In",
    "TASK": "Flow In",
    "REPEAT": "Flow In",
    "SUBFLOW": "Subflow",
    "BRANCH": "Branch Flow",
}

PAIR_KIND_START_OUTPUT_SOCKET = {
    "EXECUTION": "Flow Out",
    "TASK": "Flow Out",
    "REPEAT": "Flow Out",
    "SUBFLOW": "Subflow",
    "BRANCH": "Branch Flow",
}

PAIR_NODE_HORIZONTAL_OFFSET = 260.0
PAIR_NODE_PLACEMENT_GAP = 48.0
PAIR_NODE_FALLBACK_WIDTH = 160.0

TASK_STEP_INPUT_SPECS = (
    ("AFSocketFlow", "Flow In"),
    ("AFSocketTaskRef", "Task Ref"),
)

TASK_STEP_OUTPUT_SPECS = (
    ("AFSocketFlow", "Flow Out"),
    ("NodeSocketString", "Status"),
    ("AFSocketReport", "Report"),
)

__all__ = [
    "BOOLEAN_MATH_OPERATION_ITEMS",
    "COMPARE_MODE_ITEMS",
    "COMPARE_OPERATION_ITEMS",
    "COMPARE_VECTOR_MODE_ITEMS",
    "CONVERSION_MODE_ITEMS",
    "CONVERSION_SOCKET_MAP",
    "CUSTOM_MENU_SOCKET_IDNAMES",
    "CUSTOM_NUMERIC_SOCKET_IDNAMES",
    "FLOAT_MATH_OPERATION_ITEMS",
    "GROUP_NODE_INPUT_IDENTIFIERS_KEY",
    "GROUP_NODE_OUTPUT_IDENTIFIERS_KEY",
    "GROUP_RESERVED_SOCKET_TYPES",
    "GROUP_SUPPORTED_SOCKET_IDNAMES",
    "INDEX_SWITCH_MODE_ITEMS",
    "INDEX_SWITCH_SOCKET_IDNAME_BY_MODE",
    "INDEX_SWITCH_VIRTUAL_LABEL",
    "INTEGER_MATH_OPERATION_ITEMS",
    "MIX_MODE_ITEMS",
    "MAP_RANGE_MODE_ITEMS",
    "NUMERIC_COMPATIBLE_SOCKET_IDNAMES",
    "OBJECT_DISPLAY_TYPE_ITEMS",
    "OBJECT_INTERACTION_MODE_ITEMS",
    "OBJECT_ROTATION_MODE_ITEMS",
    "PAIR_KIND_END_INPUT_SOCKET",
    "PAIR_KIND_END_TYPE",
    "PAIR_KIND_START_OUTPUT_SOCKET",
    "PAIR_KIND_START_TYPE",
    "PAIR_NODE_FALLBACK_WIDTH",
    "PAIR_NODE_HORIZONTAL_OFFSET",
    "PAIR_NODE_PLACEMENT_GAP",
    "PAIR_NODE_TYPE_MAP",
    "PHYSICS_BAKE_TASK_INPUT_PREFIX",
    "PHYSICS_BAKE_TASK_SOCKET_IDNAME",
    "PHYSICS_BAKE_TASK_VIRTUAL_LABEL",
    "PROPERTY_ASSIGNMENT_INPUT_PREFIX",
    "PROPERTY_ASSIGNMENT_VIRTUAL_LABEL",
    "PROPERTY_DATA_FIELD_SPECS",
    "PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS",
    "PROPERTY_PACKAGE_FILTER_MODE_ITEMS",
    "RANDOM_TYPE_ITEMS",
    "RENDER_MODE_ITEMS",
    "ROTATION_AXIS_ITEMS",
    "ROTATION_PIVOT_AXIS_ITEMS",
    "ROTATION_SPACE_ITEMS",
    "RUN_TASK_PLAN_FAILURE_POLICY_ITEMS",
    "RUN_TASK_PLAN_INPUT_PREFIX",
    "RUN_TASK_PLAN_VIRTUAL_LABEL",
    "SORT_MODE_ITEMS",
    "STATUS_VALUE_ITEMS",
    "STRING_COMPARE_OPERATION_ITEMS",
    "SWITCH_MODE_ITEMS",
    "SWITCH_SOCKET_IDNAME_BY_MODE",
    "TASK_STEP_INPUT_SPECS",
    "TASK_STEP_OUTPUT_SPECS",
    "VECTOR_BOOL_MODE_ITEMS",
    "VECTOR_COMPONENT_MODE_ITEMS",
    "VECTOR_MATH_OPERATION_ITEMS",
    "VIEWPORT_SHADING_MODE_ITEMS",
]
