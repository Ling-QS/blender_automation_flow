FLOW_MENU_REGULAR_NODES = (
    ("AFNodeStart", "Start"),
    ("AFNodeEnd", "End"),
    ("AFNodeRunTaskPlan", "Run Task"),
    ("AFNodeRunBackgroundTaskPlan", "Run Background Task"),
    ("AFNodeWaitForTask", "Wait For Task"),
    ("AFNodeDelayWait", "Delay Wait"),
    ("AFNodeReloadAfterTask", "Reload After Task"),
    ("AFNodeFlowTrigger", "Flow Trigger"),
    ("AFNodeFlowToggle", "FlowToggle"),
    ("AFNodeTaskStatusOverride", "Task Status Override"),
)

FLOW_MENU_PAIRED_NODES = (
    ("AFNodeRepeatStart", "Repeat Start"),
    ("AFNodeRepeatEnd", "Repeat End"),
    ("AFNodeSubflowStart", "Subflow Start"),
    ("AFNodeSubflowJoin", "Subflow Join"),
    ("AFNodeBranchStart", "Branch Start"),
    ("AFNodeBranchEnd", "Branch End"),
)

FLOW_MENU_TRIGGER_NODES = (
    ("AFNodePlaybackState", "Playback State"),
    ("AFNodeFlowTriggerState", "Flow Trigger State"),
    ("AFNodeObjectInteractionState", "Object Interaction State"),
    ("AFNodeViewportShadingState", "Viewport Shading State"),
    ("AFNodeBooleanEdge", "Boolean Edge"),
    ("AFNodeBooleanLatch", "Boolean Latch"),
    ("AFNodeBooleanToggle", "Boolean Toggle"),
)

FLOW_PROCESS_MENU_LABEL = "Process"
FLOW_STRUCTURES_MENU_LABEL = "Structures"
FLOW_TRIGGER_MENU_LABEL = "Trigger"

PROPERTY_CONTEXT_DATA_MENU_NODES = (
    ("AFNodePropertyContext", "Prop Context"),
    ("AFNodeExtractPropertyAssignments", "Extract Prop Assigns"),
    ("AFNodeSampleContextData", "Sample Context Data"),
    ("AFNodeReduceContextValue", "Reduce Context Value"),
    ("AFNodeReadGeometryAttribute", "Read Geometry Attribute"),
    ("AFNodeSetGeometryAttribute", "Set Geometry Attribute"),
    ("AFNodePublishGeometryAttribute", "Publish Geometry Attribute"),
    ("AFNodeModifierPropertyData", "Modifier Data"),
    ("AFNodeObjectDisplayPropertyData", "Object Display Property Data"),
    ("AFNodeObjectTransformPropertyData", "Transform Data"),
    ("AFNodeMergePropertyAssignments", "Merge Prop Assigns"),
)

PROPERTY_PACKAGE_MENU_NODES = (
    ("AFNodeCreatePropertyPackage", "Create Prop Pack"),
    ("AFNodeRefreshPropertyPackage", "Refresh Prop Pack"),
    ("AFNodeStorePropertyPackage", "Store Prop Pack"),
    ("AFNodeReadPropertyPackage", "Read Prop Pack"),
    ("AFNodeApplyObjectProperties", "Apply Object Properties"),
    ("AFNodeApplyPropertyPackage", "Apply Prop Pack"),
    ("AFNodeRecordPropertyPackage", "Record Prop Pack"),
    ("AFNodeParsePropertyPackage", "Parse Prop Pack"),
    ("AFNodeFilterPropertyPackage", "Filter Prop Pack"),
    ("AFNodeMergePropertyPackages", "Merge Prop Packs"),
)

NODE_MENU_GROUPS = (
    (
        "Task Building",
        (
            ("AFNodeTaskStart", "Task Start"),
            ("AFNodeTaskOutput", "Task Output"),
            ("AFNodeResolveTaskRef", "Resolve Task Ref"),
            ("AFNodeTaskStep", "Task Step"),
            ("AFNodeEvaluateTaskDependencies", "Evaluate Object Dependencies"),
        ),
    ),
    (
        "Task Targets",
        (
            ("AFNodeBakeTask", "GN Bake Target"),
            ("AFNodePropertyPackageBakeTarget", "Property Package Bake Target"),
            ("AFNodePhysicsBakeSettings", "Physics Bake Settings"),
            ("AFNodePhysicsBakeTask", "Physics Bake Target"),
            ("AFNodeRenderTarget", "Render Target"),
        ),
    ),
    (
        "Scene Actions",
        (
            ("AFNodeSetActiveCamera", "Set Active Camera"),
        ),
    ),
    (
        "Collection & Object",
        (
            ("AFNodeCollectionList", "Collection List"),
            ("AFNodeCollectionExpand", "Collection Expand"),
            ("AFNodeObjectList", "Object List"),
            ("AFNodeSceneObjectList", "Scene Object List"),
            ("AFNodeObjectInfo", "Object Info"),
            ("AFNodeCreateCollection", "Create Collection"),
            ("AFNodeAddToCollection", "Add To Collection"),
            ("AFNodeCreateObject", "Create Object"),
            ("AFNodeDuplicateObject", "Duplicate Object"),
            ("AFNodeDeleteObject", "Delete Object"),
        ),
    ),
    (
        "Inputs",
        (
            ("AFNodeSceneTime", "Scene Time"),
            ("AFNodeStatusInput", "Status Input"),
            ("AFNodeFloatInput", "Float"),
            ("AFNodeIntegerInput", "Integer"),
            ("AFNodeBooleanInput", "Boolean"),
            ("AFNodeVectorInput", "Vector"),
            ("AFNodeStringInput", "String"),
            ("AFNodeInputRotation", "Rotation"),
        ),
    ),
    (
        "Math",
        (
            ("AFNodeMath", "Math"),
            ("AFNodeIntegerMath", "Integer Math"),
            ("AFNodeBooleanMath", "Boolean Math"),
            ("AFNodeCompare", "Compare"),
            ("AFNodeClamp", "Clamp"),
            ("AFNodeMapRange", "Map Range"),
            ("AFNodeSmoothstep", "Smoothstep"),
        ),
    ),
    (
        "Utilities",
        (
            ("AFNodeMix", "Mix"),
            ("AFNodeSwitch", "Switch"),
            ("AFNodeIndexSwitch", "Index Switch"),
            ("AFNodeConvertValue", "Convert"),
            ("AFNodeRandomValue", "Random Value"),
            ("AFNodePreviewData", "Preview Data"),
            ("AFNodeGroup", "Group"),
        ),
    ),
    (
        "Vector",
        (
            ("AFNodeVectorMath", "Vector Math"),
            ("AFNodeCombineVector", "Combine Vector"),
            ("AFNodeSeparateVector", "Separate Vector"),
            ("AFNodeVectorRotate", "Vector Rotate"),
        ),
    ),
    (
        "Rotation",
        (
            ("AFNodeRotateVector", "Rotate Vector"),
            ("AFNodeEulerToRotation", "Euler to Rotation"),
            ("AFNodeQuaternionToRotation", "Quaternion to Rotation"),
            ("AFNodeAxisAngleToRotation", "Axis Angle to Rotation"),
            ("AFNodeInvertRotation", "Invert Rotation"),
            ("AFNodeRotateRotation", "Rotate Rotation"),
            ("AFNodeRotationToEuler", "Rotation to Euler"),
            ("AFNodeRotationToQuaternion", "Rotation to Quaternion"),
            ("AFNodeRotationToAxisAngle", "Rotation to Axis Angle"),
            ("AFNodeAxesToRotation", "Axes to Rotation"),
            ("AFNodeAlignRotationToVector", "Align Rotation to Vector"),
        ),
    ),
    (
        "Matrix",
        (
            ("AFNodeCombineMatrix", "Combine Matrix"),
            ("AFNodeSeparateMatrix", "Separate Matrix"),
            ("AFNodeCombineTransform", "Combine Transform"),
            ("AFNodeSeparateTransform", "Separate Transform"),
            ("AFNodeMatrixMultiply", "Multiply Matrices"),
            ("AFNodeInvertMatrix", "Invert Matrix"),
            ("AFNodeTransposeMatrix", "Transpose Matrix"),
            ("AFNodeMatrixDeterminant", "Matrix Determinant"),
            ("AFNodeTransformPoint", "Transform Point"),
            ("AFNodeTransformDirection", "Transform Direction"),
            ("AFNodeProjectPoint", "Project Point"),
        ),
    ),
)

GROUP_ASSET_MENU_TITLE = "Assets"
GROUP_ASSET_MENU_ENTRIES = (
    ("Task Isolation", "TASK_ISOLATION"),
    ("Create Task", "CREATE_TASK"),
)

NODE_MENU_SECTIONS = (
    ("Task", ("Task Building", "Task Targets")),
    ("Scene", ("Scene Actions", "Collection & Object")),
    ("Math", ("Math", "Utilities", "Vector", "Rotation", "Matrix")),
)
