import copy

STATUS_IDLE = "IDLE"
STATUS_PRECHECK = "PRECHECK"
STATUS_RUNNING = "RUNNING"
STATUS_WAITING = "WAITING"
STATUS_RELOADING = "RELOADING"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"

FLOW_OK = "DONE"
FLOW_WAIT = "WAITING"
FLOW_YIELD = "YIELD"
BAKE_JOB_TYPE = "OBJECT_BAKE"

TASK_KIND_GEOMETRY = "GEOMETRY_NODES"
TASK_KIND_PHYSICS = "PHYSICS"
TASK_KIND_PHYSICS_BAKE_ALL = "PHYSICS_BAKE_ALL"
TASK_KIND_RENDER = "RENDER"
TASK_KIND_PROPERTY_PACKAGE_BAKE = "PROPERTY_PACKAGE_BAKE"
PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE = "SOURCE"
PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_TARGET = "TARGET"
PHYSICS_SUPPORTED_MODIFIER_TYPES = {
    "CLOTH": "Cloth",
    "SOFT_BODY": "Soft Body",
    "DYNAMIC_PAINT": "Dynamic Paint",
}
PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES = {
    "CLOTH": "Cloth",
    "SOFT_BODY": "Soft Body",
}

PROPERTY_DEFINITION_KIND_MODIFIER = "MODIFIER"
PROPERTY_DEFINITION_KIND_OBJECT_DISPLAY = "OBJECT_DISPLAY"
PROPERTY_DEFINITION_KIND_OBJECT_TRANSFORM = "OBJECT_TRANSFORM"
PROPERTY_DEFINITION_KIND_COMPOSITE = "COMPOSITE"
PROPERTY_ASSIGNMENT_KIND_MODIFIER = "MODIFIER"
PROPERTY_ASSIGNMENT_KIND_OBJECT_DISPLAY = "OBJECT_DISPLAY"
PROPERTY_ASSIGNMENT_KIND_OBJECT_TRANSFORM = "OBJECT_TRANSFORM"
PROPERTY_ASSIGNMENT_KIND_COMPOSITE = "COMPOSITE"
PROPERTY_SOURCE_VALUE = "VALUE"
PROPERTY_SOURCE_CURRENT = "CURRENT"
PROPERTY_PACKAGE_ROLE_SNAPSHOT = "SNAPSHOT"
PROPERTY_PACKAGE_ROLE_TARGET = "TARGET"
PROPERTY_PACKAGE_ROLE_SETTINGS = "SETTINGS"
PROPERTY_PACKAGE_ROLE_COMPOSITE = "COMPOSITE"
PROPERTY_SCOPE_KIND_MIXED = "MIXED"
PROPERTY_PACKAGE_SCOPE_OBJECT = "OBJECT"
PROPERTY_PACKAGE_SCOPE_MODIFIER = "MODIFIER"
PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE = "PHYSICS_BAKE"
PROPERTY_PACKAGE_SCOPE_GN_BAKE = "GN_BAKE"
STORED_PROPERTY_PACKAGE_PROP_PREFIX = "af_stored_property_package::"
GN_PACKED_CACHE_STATE_PROP = "af_gn_packed_cache_state"
GN_LAST_BAKE_STATE_PROP = "af_gn_last_bake_state"
STATUS_REPORT_CACHE_PROP = "af_status_report_cache_json"
FLOW_TOGGLE_CACHE_PROP = "af_flow_toggle_cache_json"
OBJECT_PERSISTENT_UUID_PROP = "af_object_uuid"
TASK_PLAN_KIND = "COMPILED_TASK_PLAN"
RELOAD_RESUME_CHECKPOINT_VERSION = 1
RELOAD_RESUME_CONTINUE_DELAY_SECONDS = 0.3
REPEAT_START_NODE_TYPES = {"AFNodeRepeatStart"}
REPEAT_END_NODE_TYPES = {"AFNodeRepeatEnd"}
BRANCH_START_NODE_TYPES = {"AFNodeBranchStart"}
BRANCH_END_NODE_TYPES = {"AFNodeBranchEnd"}
PROPERTY_PACKAGE_BAKE_ACTION_NAME_PREFIX = "AF_PropertyPackageBake::"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_BAKE_ASSET_ID = "af_property_package_bake_asset_id"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_TASK_KIND = "af_property_package_bake_task_kind"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_TREE_NAME = "af_property_package_bake_tree_name"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_NODE_NAME = "af_property_package_bake_node_name"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_TREE_NAME = "af_property_package_bake_start_tree_name"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_START_NODE_NAME = "af_property_package_bake_start_node_name"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_START = "af_property_package_bake_frame_start"
PROPERTY_PACKAGE_BAKE_ACTION_PROP_FRAME_END = "af_property_package_bake_frame_end"
NUMERIC_SOCKET_FAMILY_BY_IDNAME = {
    "NodeSocketBool": "NodeSocketBool",
    "NodeSocketInt": "NodeSocketInt",
    "NodeSocketFloat": "NodeSocketFloat",
    "NodeSocketVector": "NodeSocketVector",
    "AFSocketBooleanValue": "NodeSocketBool",
    "AFSocketIntegerValue": "NodeSocketInt",
    "AFSocketFloatValue": "NodeSocketFloat",
    "AFSocketVectorValue": "NodeSocketVector",
}

ROTATION_IDENTITY_QUATERNION = (1.0, 0.0, 0.0, 0.0)
GROUP_INPUT_DEFAULT_MISSING = object()
PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES = {
    "AFNodePropertyContext",
    "AFNodeReduceContextValue",
    "AFNodeModifierPropertyData",
    "AFNodeObjectDisplayPropertyData",
    "AFNodeObjectTransformPropertyData",
    "AFNodeCreatePropertyPackage",
}
PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES = {
    "AFNodeFloatInput",
    "AFNodeBooleanInput",
    "AFNodeVectorInput",
    "AFNodeIntegerInput",
    "AFNodeStringInput",
    "AFNodeInputRotation",
    "AFNodeStatusInput",
    "AFNodePlaybackState",
    "AFNodeSceneTime",
    "AFNodeSceneObjectList",
    "AFNodeObjectInfo",
    "AFNodeTaskOutput",
}


class FlowExecutionError(Exception):
    def __init__(self, code, message, node_name="", node_tree_name="", group_path=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.node_name = node_name
        self.node_tree_name = str(node_tree_name or "")
        self.group_path = copy.deepcopy(list(group_path or []))


def _enrich_flow_error_context(exc, node=None, node_tree_name="", group_path=None):
    if not isinstance(exc, FlowExecutionError):
        return exc
    if node is not None:
        if not str(getattr(exc, "node_name", "") or ""):
            exc.node_name = str(getattr(node, "name", "") or "")
        if not str(getattr(exc, "node_tree_name", "") or ""):
            tree = getattr(node, "id_data", None)
            exc.node_tree_name = str(getattr(tree, "name", "") or "")
    if node_tree_name and not str(getattr(exc, "node_tree_name", "") or ""):
        exc.node_tree_name = str(node_tree_name or "")
    if group_path is not None and not list(getattr(exc, "group_path", []) or []):
        exc.group_path = copy.deepcopy(list(group_path or []))
    return exc
