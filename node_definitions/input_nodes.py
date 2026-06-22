import bpy


def build_input_node_classes(
    *,
    AFBaseNode,
    STATUS_VALUE_ITEMS,
    SCENE_TIME_OUTPUT_SOCKET_SPECS,
    _hide_default_auxiliary_outputs,
    _set_node_color,
    _status_value_display_label,
):
    def _ensure_output_socket_name(node, expected_name, *legacy_names):
        outputs = getattr(node, "outputs", None)
        socket = getattr(outputs, "get", lambda _name: None)(expected_name) if outputs is not None else None
        if socket is None and outputs is not None:
            for legacy_name in legacy_names:
                socket = getattr(outputs, "get", lambda _name: None)(legacy_name)
                if socket is not None:
                    break
        if socket is not None and str(getattr(socket, "name", "") or "") != expected_name:
            try:
                socket.name = expected_name
            except Exception:
                pass
        return socket

    object_interaction_mode_items = (
        ("OBJECT", "Object", "Stay true while Object Mode is active"),
        ("EDIT", "Edit", "Stay true while Edit Mode is active"),
        ("SCULPT", "Sculpt", "Stay true while Sculpt Mode is active"),
        ("POSE", "Pose", "Stay true while Pose Mode is active"),
        ("WEIGHT_PAINT", "Weight Paint", "Stay true while Weight Paint Mode is active"),
        ("VERTEX_PAINT", "Vertex Paint", "Stay true while Vertex Paint Mode is active"),
        ("TEXTURE_PAINT", "Texture Paint", "Stay true while Texture Paint Mode is active"),
    )
    viewport_shading_mode_items = (
        ("WIREFRAME", "Wireframe", "Stay true while Wireframe shading is active"),
        ("SOLID", "Solid", "Stay true while Solid shading is active"),
        ("MATERIAL", "Material Preview", "Stay true while Material Preview shading is active"),
        ("RENDERED", "Rendered", "Stay true while Rendered shading is active"),
    )

    class AFNodePlaybackState(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePlaybackState"
        bl_label = "Playback State"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.outputs.new("NodeSocketBool", "Playing")
            self.outputs.new("NodeSocketBool", "On Play")
            self.outputs.new("NodeSocketBool", "On Pause")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

    class AFNodeFlowTriggerState(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeFlowTriggerState"
        bl_label = "Flow Trigger State"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.outputs.new("NodeSocketBool", "Manual")
            self.outputs.new("NodeSocketBool", "Scene Updating")
            self.outputs.new("NodeSocketBool", "On Scene Update Start")
            self.outputs.new("NodeSocketBool", "On Scene Update End")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

    class AFNodeObjectInteractionState(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeObjectInteractionState"
        bl_label = "Object Interaction State"
        bl_icon = "BLANK1"

        target_interaction_mode: bpy.props.EnumProperty(
            name="Mode",
            items=object_interaction_mode_items,
            default="OBJECT",
        )

        def init(self, context):
            del context
            self.outputs.new("NodeSocketBool", "Active")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            _ensure_output_socket_name(self, "Active", "Triggered")
            layout.prop(self, "target_interaction_mode", text="")

    class AFNodeViewportShadingState(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeViewportShadingState"
        bl_label = "Viewport Shading State"
        bl_icon = "BLANK1"

        target_shading_mode: bpy.props.EnumProperty(
            name="Shading",
            items=viewport_shading_mode_items,
            default="SOLID",
        )

        def init(self, context):
            del context
            self.outputs.new("NodeSocketBool", "Active")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            _ensure_output_socket_name(self, "Active", "Triggered")
            layout.prop(self, "target_shading_mode", text="")

    class AFNodeBooleanEdge(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBooleanEdge"
        bl_label = "Boolean Edge"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            value_socket = self.inputs.new("NodeSocketBool", "Value")
            value_socket.default_value = False
            self.outputs.new("NodeSocketBool", "On True")
            self.outputs.new("NodeSocketBool", "On False")
            _set_node_color(self, "INPUT")

    class AFNodeBooleanLatch(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBooleanLatch"
        bl_label = "Boolean Latch"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            set_socket = self.inputs.new("NodeSocketBool", "Set")
            set_socket.default_value = False
            reset_socket = self.inputs.new("NodeSocketBool", "Reset")
            reset_socket.default_value = False
            self.outputs.new("NodeSocketBool", "State")
            _set_node_color(self, "INPUT")

    class AFNodeSceneTime(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSceneTime"
        bl_label = "Scene Time"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            for socket_idname, socket_name in SCENE_TIME_OUTPUT_SOCKET_SPECS:
                self.outputs.new(socket_idname, socket_name)
            _set_node_color(self, "INPUT")

    class AFNodeFloatInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeFloatInput"
        bl_label = "Float"
        bl_icon = "BLANK1"

        value: bpy.props.FloatProperty(name="Value", default=0.0)

        def init(self, context):
            self.outputs.new("NodeSocketFloat", "Value")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "value", text="")

    class AFNodeBooleanInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBooleanInput"
        bl_label = "Boolean"
        bl_icon = "BLANK1"

        value: bpy.props.BoolProperty(name="Value", default=False)

        def init(self, context):
            self.outputs.new("NodeSocketBool", "Value")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "value", text="")

    class AFNodeVectorInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeVectorInput"
        bl_label = "Vector"
        bl_icon = "BLANK1"

        x: bpy.props.FloatProperty(name="X", default=0.0)
        y: bpy.props.FloatProperty(name="Y", default=0.0)
        z: bpy.props.FloatProperty(name="Z", default=0.0)

        def init(self, context):
            self.outputs.new("NodeSocketVector", "Vector")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            col = layout.column(align=True)
            col.prop(self, "x", text="X")
            col.prop(self, "y", text="Y")
            col.prop(self, "z", text="Z")

    class AFNodeIntegerInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeIntegerInput"
        bl_label = "Integer"
        bl_icon = "BLANK1"

        value: bpy.props.IntProperty(name="Value", default=0)

        def init(self, context):
            self.outputs.new("NodeSocketInt", "Value")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "value", text="")

    class AFNodeStringInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeStringInput"
        bl_label = "String"
        bl_icon = "BLANK1"

        value: bpy.props.StringProperty(name="Value", default="")

        def init(self, context):
            self.outputs.new("NodeSocketString", "String")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "value", text="")

    class AFNodeInputRotation(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeInputRotation"
        bl_label = "Rotation"
        bl_icon = "BLANK1"

        rotation_euler: bpy.props.FloatVectorProperty(name="Rotation", size=3, default=(0.0, 0.0, 0.0), subtype="EULER")

        def init(self, context):
            del context
            self.outputs.new("NodeSocketRotation", "Rotation")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            col = layout.column(align=True)
            col.prop(self, "rotation_euler", index=0, text="X")
            col.prop(self, "rotation_euler", index=1, text="Y")
            col.prop(self, "rotation_euler", index=2, text="Z")

    class AFNodeStatusInput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeStatusInput"
        bl_label = "Status Input"
        bl_icon = "BLANK1"

        status_value: bpy.props.EnumProperty(name="Status", items=STATUS_VALUE_ITEMS, default="DONE")

        def init(self, context):
            del context
            self.outputs.new("NodeSocketString", "Status")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            try:
                context_pointer_set = getattr(layout, "context_pointer_set", None)
                if callable(context_pointer_set):
                    context_pointer_set("af_status_node", self)
            except Exception:
                pass
            try:
                layout.menu("AF_MT_status_value_menu", text=_status_value_display_label(getattr(self, "status_value", "")))
            except Exception:
                layout.prop(self, "status_value", text="")

        def draw_label(self):
            return _status_value_display_label(getattr(self, "status_value", ""))

    return {
        "AFNodePlaybackState": AFNodePlaybackState,
        "AFNodeFlowTriggerState": AFNodeFlowTriggerState,
        "AFNodeObjectInteractionState": AFNodeObjectInteractionState,
        "AFNodeViewportShadingState": AFNodeViewportShadingState,
        "AFNodeBooleanEdge": AFNodeBooleanEdge,
        "AFNodeBooleanLatch": AFNodeBooleanLatch,
        "AFNodeSceneTime": AFNodeSceneTime,
        "AFNodeFloatInput": AFNodeFloatInput,
        "AFNodeBooleanInput": AFNodeBooleanInput,
        "AFNodeVectorInput": AFNodeVectorInput,
        "AFNodeIntegerInput": AFNodeIntegerInput,
        "AFNodeStringInput": AFNodeStringInput,
        "AFNodeInputRotation": AFNodeInputRotation,
        "AFNodeStatusInput": AFNodeStatusInput,
    }
