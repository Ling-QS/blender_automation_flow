from ..node_system.socket_aliases import (
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)

MODIFIER_TYPE_FILTER_ITEMS = (
    ("ALL", "All Modifiers", "Apply to all modifiers"),
    ("GEOMETRY_NODES", "Geometry Nodes", "Apply to geometry nodes modifiers only"),
)

MODIFIER_NAME_MATCH_MODE_ITEMS = (
    ("EXACT", "Exact", "Match the modifier name exactly"),
    ("CONTAINS", "Contains", "Match when the modifier name contains the filter text"),
    ("STARTS_WITH", "Starts With", "Match when the modifier name starts with the filter text"),
)

BAKE_TASK_BAKE_MODE_ITEMS = (
    ("ANIMATION", "Animation", "Bake a frame range"),
    ("STILL", "Still", "Bake a single frame"),
)

BAKE_TASK_BAKE_TARGET_ITEMS = (
    ("INHERIT", "Inherit", "Use modifier-level bake target"),
    ("PACKED", "Packed", "Pack baked data into .blend"),
    ("DISK", "Disk", "Store baked data on disk"),
)

MISSING_POLICY_ITEMS = (
    ("WARN_AND_SKIP", "Warn & Skip", "Warn on missing objects/modifiers and continue"),
    ("FAIL", "Fail", "Fail flow if object/modifier missing while restoring"),
)

REFRESH_PROPERTY_PACKAGE_RANGE_MODE_ITEMS = (
    ("IN_SCOPE", "In Scope", "Refresh only the selected Object List and Property Definition range"),
    ("OUT_OF_SCOPE", "Out of Scope", "Refresh everything outside the selected Object List and Property Definition range"),
)

PROPERTY_PACKAGE_STORE_MODE_ITEMS = (
    ("STORE_AND_OUTPUT", "Store", "Store the incoming Property Package on this node and output it"),
    ("OUTPUT_ONLY", "Output", "Ignore the incoming Property Package and output the previously stored one"),
)

APPLY_OBJECT_PROPERTIES_MODE_ITEMS = (
    ("PACKAGE", "Package", "Apply properties from a Property Package"),
    ("ASSIGNMENT", "Assignment", "Apply properties directly from Property Assignment inputs"),
)

PROPERTY_SOURCE_VALUE = "VALUE"
PROPERTY_SOURCE_CURRENT = "CURRENT"

PROPERTY_VALUE_SOURCE_ITEMS = (
    ("VALUE", "Value", "Use the explicit value for this property field"),
    ("CURRENT", "Current", "Read the current value from the object or modifier"),
)

PROPERTY_DATA_OUTPUT_MODE_ITEMS = (
    ("ASSIGNMENT", "Assignment", "Output Property Assignment data"),
    ("CONTEXT", "Context", "Output current property context values"),
)

PREVIEW_DATA_MODE_ITEMS = (
    ("OBJECT", "Object", "Preview an Object value"),
    ("OBJECT_LIST", "Object List", "Preview an Object List"),
    ("STRING", "String", "Preview a String value"),
    ("BOOLEAN", "Boolean", "Preview a Boolean value"),
    ("INTEGER", "Integer", "Preview an Integer value"),
    ("FLOAT", "Float", "Preview a Float value"),
    ("VECTOR", "Vector", "Preview a Vector value"),
    ("ROTATION", "Rotation", "Preview a Rotation value"),
    ("MATRIX", "Matrix", "Preview a Matrix value"),
    ("DISPLAY_TYPE", "Display Type", "Preview a Display Type value"),
    ("ROTATION_MODE", "Rotation Mode", "Preview a Rotation Mode value"),
    ("PROPERTY_DEFINITION", "Prop Def", "Preview a Prop Def"),
    ("PROPERTY_ASSIGNMENT", "Prop Assign", "Preview a Prop Assign"),
    ("PROPERTY_PACKAGE", "Prop Pack", "Preview a Prop Pack"),
    ("TASK_REF", "Task Ref", "Preview a Task Ref"),
    ("TASK_PLAN", "Task Plan", "Preview a Task Plan"),
    ("REPORT", "Report", "Preview a Report payload"),
)

SCENE_TIME_OUTPUT_SOCKET_SPECS = (
    ("NodeSocketFloat", "Seconds"),
    ("NodeSocketFloat", "Frame"),
)

PREVIEW_PROPERTY_PACKAGE_VIEW_MODE_ITEMS = (
    ("SUMMARY", "Summary", "Preview Prop Pack summary"),
    ("ENTRIES", "Entries", "Preview composite Prop Pack entries"),
    ("ITEMS", "Items", "Preview flattened Prop Pack items"),
)

PREVIEW_PROPERTY_DEFINITION_VIEW_MODE_ITEMS = (
    ("SUMMARY", "Summary", "Preview Prop Def summary"),
    ("ENTRIES", "Entries", "Preview composite Prop Def entries"),
    ("FIELDS", "Fields", "Preview Prop Def fields"),
)

PREVIEW_TASK_PLAN_VIEW_MODE_ITEMS = (
    ("SUMMARY", "Summary", "Preview Task Plan summary"),
    ("STEPS", "Steps", "Preview Task Plan steps"),
    ("STRUCTURE", "Structure", "Preview Task Plan step paths"),
)

GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS = (
    ("BOOLEAN", "Boolean", "Read the attribute as a Boolean value"),
    ("FLOAT", "Float", "Read the attribute as a Float value"),
    ("INTEGER", "Integer", "Read the attribute as an Integer value"),
    ("VECTOR", "Vector", "Read the attribute as a Vector value"),
    ("ROTATION", "Rotation", "Read the attribute as a Rotation value"),
    ("MATRIX", "Matrix", "Read the attribute as a Matrix value"),
)

SAMPLE_OBJECT_INDEX_MODE_ITEMS = (
    ("BOOLEAN", "Boolean", "Sample a Boolean value from the indexed object context"),
    ("FLOAT", "Float", "Sample a Float value from the indexed object context"),
    ("INTEGER", "Integer", "Sample an Integer value from the indexed object context"),
    ("VECTOR", "Vector", "Sample a Vector value from the indexed object context"),
    ("ROTATION", "Rotation", "Sample a Rotation value from the indexed object context"),
    ("MATRIX", "Matrix", "Sample a Matrix value from the indexed object context"),
    ("PROPERTY_ASSIGNMENT", "Prop Assign", "Sample a Prop Assign value from the indexed object context"),
)

CONTEXT_REDUCE_VALUE_TYPE_ITEMS = (
    ("FLOAT", "Float", "Reduce Float values across the current object context"),
    ("INTEGER", "Integer", "Reduce Integer values across the current object context"),
    ("VECTOR", "Vector", "Reduce Vector values across the current object context"),
)

CONTEXT_REDUCE_OPERATION_ITEMS = (
    ("MINIMUM", "Minimum", "Compute the minimum value"),
    ("MAXIMUM", "Maximum", "Compute the maximum value"),
    ("AVERAGE", "Average", "Compute the average value"),
    ("MEDIAN", "Median", "Compute the median value"),
    ("VARIANCE", "Variance", "Compute the variance"),
    ("STANDARD_DEVIATION", "Standard Deviation", "Compute the standard deviation"),
)

CONTEXT_REDUCE_VECTOR_MODE_ITEMS = (
    ("COMPONENTS", "Per Component", "Reduce vector components independently"),
    ("LENGTH", "Length", "Compare vectors by length and return the matched vector"),
)

GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE = {
    "BOOLEAN": "NodeSocketBool",
    "FLOAT": "NodeSocketFloat",
    "INTEGER": "NodeSocketInt",
    "VECTOR": "NodeSocketVector",
    "ROTATION": "NodeSocketRotation",
    "MATRIX": "NodeSocketMatrix",
}

SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE = {
    "BOOLEAN": "NodeSocketBool",
    "FLOAT": "NodeSocketFloat",
    "INTEGER": "NodeSocketInt",
    "VECTOR": "NodeSocketVector",
    "ROTATION": "NodeSocketRotation",
    "MATRIX": "NodeSocketMatrix",
    "PROPERTY_ASSIGNMENT": "AFSocketPropertyAssignment",
}

CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE = {
    "FLOAT": "NodeSocketFloat",
    "INTEGER": "NodeSocketInt",
    "VECTOR": "NodeSocketVector",
}

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

PREVIEW_DATA_MODE_SPECS = {
    "OBJECT": ("AFSocketObjectList", "Object", "object_list"),
    "OBJECT_LIST": ("AFSocketObjectList", "Object List", "object_list"),
    "STRING": ("NodeSocketString", "String", "string_value"),
    "BOOLEAN": ("NodeSocketBool", "Boolean", "bool_value"),
    "INTEGER": ("NodeSocketInt", "Integer", "int_value"),
    "FLOAT": ("NodeSocketFloat", "Float", "float_value"),
    "VECTOR": ("NodeSocketVector", "Vector", "vector_value"),
    "ROTATION": ("NodeSocketRotation", "Rotation", "rotation_value"),
    "MATRIX": ("NodeSocketMatrix", "Matrix", "matrix_value"),
    "DISPLAY_TYPE": ("AFSocketDisplayType", "Display Type", "display_type_value"),
    "ROTATION_MODE": ("AFSocketRotationMode", "Rotation Mode", "rotation_mode_value"),
    "PROPERTY_DEFINITION": ("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME, "property_definition"),
    "PROPERTY_ASSIGNMENT": ("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME, "property_assignment"),
    "PROPERTY_PACKAGE": ("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME, "property_package"),
    "TASK_REF": ("AFSocketTaskRef", "Task Ref", "task_ref"),
    "TASK_PLAN": ("AFSocketTaskPlan", "Task Plan", "task_plan"),
    "REPORT": ("AFSocketReport", "Report", "report"),
}

PREVIEW_DATA_MODE_BY_SOCKET_IDNAME = {
    socket_id: mode for mode, (socket_id, _socket_name, _output_key) in PREVIEW_DATA_MODE_SPECS.items()
}
PREVIEW_DATA_MODE_BY_SOCKET_IDNAME.update(
    {
        "AFSocketString": "STRING",
        "AFSocketBooleanValue": "BOOLEAN",
        "AFSocketDisplayType": "DISPLAY_TYPE",
        "AFSocketIntegerValue": "INTEGER",
        "AFSocketFloatValue": "FLOAT",
        "AFSocketRotationMode": "ROTATION_MODE",
        "AFSocketVectorValue": "VECTOR",
    }
)

PREVIEW_DATA_VIRTUAL_LABEL = "Preview"

DEPENDENCY_SCOPE_ITEMS = (
    ("DIRECT", "Direct Only", "Only include direct object references and dependencies"),
    ("FULL_CLOSURE", "Full Closure", "Include transitive dependency closure"),
)

DEPENDENCY_STRATEGY_ITEMS = (
    ("STATIC", "Static References", "Use static scan of GN and modifier references"),
    ("STATIC_PLUS_DEPSGRAPH", "Static + Depsgraph", "Union static references with depsgraph upstream dependencies"),
)

OBJECT_TYPE_FILTER_ITEMS = (
    ("ALL", "All Types", "Include all object types"),
    ("MESH", "Mesh", "Include mesh objects only"),
    ("CURVE", "Curve", "Include curve objects only"),
    ("EMPTY", "Empty", "Include empty objects only"),
)

COLLECTION_LINK_MODE_ITEMS = (
    ("LINK_ONLY", "Link Only", "Link objects to the target collections without removing existing collection links"),
    ("MOVE_TO_ONLY", "Move To Only", "Ensure objects are linked only to the target collections"),
)

DUPLICATE_DATA_MODE_ITEMS = (
    ("LINKED_DATA", "Linked Data", "Duplicate objects while reusing their object data"),
    ("SINGLE_USER_DATA", "Single User Data", "Duplicate objects and make their object data single user"),
)

CREATE_OBJECT_TYPE_ITEMS = (
    ("EMPTY", "Empty", "Create an Empty object"),
    ("MESH", "Mesh", "Create an object with a new empty Mesh datablock"),
    ("CAMERA", "Camera", "Create a Camera object"),
    ("LIGHT", "Light", "Create a Light object"),
)

LIGHT_TYPE_ITEMS = (
    ("POINT", "Point", "Create a Point light"),
    ("SUN", "Sun", "Create a Sun light"),
    ("SPOT", "Spot", "Create a Spot light"),
    ("AREA", "Area", "Create an Area light"),
)
