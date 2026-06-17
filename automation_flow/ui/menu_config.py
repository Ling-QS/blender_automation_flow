FLOW_MENU_REGULAR_NODES = (
    ("AFNodeStart", "Start"),
    ("AFNodeFlowToggle", "FlowToggle"),
    ("AFNodeEnd", "End"),
    ("AFNodeRunTaskPlan", "Run Task"),
    ("AFNodeRunBackgroundTaskPlan", "Run Background Task"),
    ("AFNodeWaitForTask", "Delay Wait"),
    ("AFNodeReloadAfterTask", "Reload After Task"),
    ("AFNodeGroup", "Group"),
)

FLOW_MENU_PAIRED_NODES = (
    ("AFNodeRepeatStart", "Repeat Start"),
    ("AFNodeRepeatEnd", "Repeat End"),
    ("AFNodeSubflowStart", "Subflow Start"),
    ("AFNodeSubflowJoin", "Subflow Join"),
    ("AFNodeBranchStart", "Branch Start"),
    ("AFNodeBranchEnd", "Branch End"),
)

FLOW_PROCESS_MENU_LABEL = "Process"
FLOW_STRUCTURES_MENU_LABEL = "Structures"

PROPERTY_CONTEXT_DATA_MENU_NODES = (
    ("AFNodePropertyContext", "Prop Context"),
    ("AFNodeSampleObjectIndex", "Sample Object Index"),
    ("AFNodeReduceContextValue", "Reduce Context Value"),
    ("AFNodeReadGeometryAttribute", "Read Geometry Attribute"),
    ("AFNodeModifierPropertyData", "Modifier Data"),
    ("AFNodeObjectDisplayPropertyData", "Object Display Property Data"),
    ("AFNodeObjectTransformPropertyData", "Transform Data"),
)

PROPERTY_PACKAGE_MENU_NODES = (
    ("AFNodeMergePropertyAssignments", "Merge Prop Assigns"),
    ("AFNodeCreatePropertyPackage", "Create Prop Pack"),
    ("AFNodeStorePropertyPackage", "Store Prop Pack"),
    ("AFNodeApplyObjectProperties", "Apply Object Properties"),
    ("AFNodeApplyPropertyPackage", "Apply Prop Pack"),
    ("AFNodeRecordPropertyPackage", "Record Prop Pack"),
    ("AFNodeParsePropertyPackage", "Parse Prop Pack"),
    ("AFNodeFilterPropertyPackage", "Filter Prop Pack"),
    ("AFNodeMergePropertyPackages", "Merge Prop Packs"),
)

NODE_MENU_GROUPS = (
    (
        "Task",
        (
            ("AFNodeTaskStart", "Task Start"),
            ("AFNodeTaskOutput", "Task Output"),
            ("AFNodeBakeTask", "GN Bake Target"),
            ("AFNodeAutoFlowBakeTarget", "Auto Flow Bake Target"),
            ("AFNodePhysicsBakeSettings", "Physics Bake Settings"),
            ("AFNodePhysicsBakeTask", "Physics Bake Target"),
            ("AFNodeRenderTarget", "Render Target"),
            ("AFNodeResolveTaskRef", "Resolve Task Ref"),
            ("AFNodeTaskStep", "Task Step"),
        ),
    ),
    (
        "Task Analysis",
        (
            ("AFNodeEvaluateTaskDependencies", "Evaluate Object Dependencies"),
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
            ("AFNodePlaybackState", "Playback State"),
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
            ("AFNodeStringCompare", "String Compare"),
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
)

NODE_MENU_SECTIONS = (
    ("Task", ("Task", "Task Analysis")),
    ("Scene", ("Scene Actions", "Collection & Object")),
    ("Math", ("Math", "Utilities", "Vector", "Rotation", "Matrix")),
)
