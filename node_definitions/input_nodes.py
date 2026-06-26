import json

import bpy
from bpy.app.translations import pgettext_iface as iface_


def build_input_node_classes(
    *,
    AFBaseNode,
    OBJECT_INTERACTION_MODE_ITEMS,
    STATUS_VALUE_ITEMS,
    SCENE_TIME_OUTPUT_SOCKET_SPECS,
    VIEWPORT_SHADING_MODE_ITEMS,
    _hide_default_auxiliary_outputs,
    _set_node_color,
    _status_value_display_label,
    _ui_group_path,
    _ui_runner_for_node,
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

    def _ensure_named_input_socket(node, socket_idname, socket_name):
        inputs = getattr(node, "inputs", None)
        socket = getattr(inputs, "get", lambda _name: None)(socket_name) if inputs is not None else None
        created = False
        if socket is None and inputs is not None:
            try:
                socket = inputs.new(socket_idname, socket_name)
                created = True
            except Exception:
                socket = getattr(inputs, "get", lambda _name: None)(socket_name)
        if socket is not None and str(getattr(socket, "name", "") or "") != socket_name:
            try:
                socket.name = socket_name
            except Exception:
                pass
        return socket, created

    def _ensure_legacy_menu_input_socket(node, socket_idname, socket_name, legacy_attr, fallback):
        socket, created = _ensure_named_input_socket(node, socket_idname, socket_name)
        if socket is None or not created:
            return socket
        try:
            socket.default_value = str(getattr(node, legacy_attr, fallback) or fallback)
        except Exception:
            pass
        return socket

    def _encoded_ui_group_path(node, context):
        try:
            return json.dumps(list(_ui_group_path(node, context) or []), ensure_ascii=True, separators=(",", ":"))
        except Exception:
            return "[]"

    def _ui_boolean_toggle_state_value(node, context):
        try:
            runner = _ui_runner_for_node(node, context)
            if runner is not None:
                return bool(runner._read_boolean_toggle_state(node, getattr(runner, "current_group_path", None)))
        except Exception:
            pass
        return bool(getattr(node, "default_value", False))

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
            items=OBJECT_INTERACTION_MODE_ITEMS,
            default="OBJECT",
        )

        def _ensure_mode_socket(self):
            return _ensure_legacy_menu_input_socket(
                self,
                "AFSocketObjectInteractionMode",
                "Mode",
                "target_interaction_mode",
                "OBJECT",
            )

        def init(self, context):
            del context
            self._ensure_mode_socket()
            self.outputs.new("NodeSocketBool", "Active")
            _set_node_color(self, "INPUT")

        def update(self):
            self._ensure_mode_socket()
            _ensure_output_socket_name(self, "Active", "Triggered")

        def draw_buttons(self, context, layout):
            del context, layout
            self._ensure_mode_socket()
            _ensure_output_socket_name(self, "Active", "Triggered")

    class AFNodeViewportShadingState(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeViewportShadingState"
        bl_label = "Viewport Shading State"
        bl_icon = "BLANK1"

        target_shading_mode: bpy.props.EnumProperty(
            name="Shading",
            items=VIEWPORT_SHADING_MODE_ITEMS,
            default="SOLID",
        )

        def _ensure_shading_socket(self):
            return _ensure_legacy_menu_input_socket(
                self,
                "AFSocketViewportShadingMode",
                "Shading",
                "target_shading_mode",
                "SOLID",
            )

        def init(self, context):
            del context
            self._ensure_shading_socket()
            self.outputs.new("NodeSocketBool", "Active")
            _set_node_color(self, "INPUT")

        def update(self):
            self._ensure_shading_socket()
            _ensure_output_socket_name(self, "Active", "Triggered")

        def draw_buttons(self, context, layout):
            del context, layout
            self._ensure_shading_socket()
            _ensure_output_socket_name(self, "Active", "Triggered")

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

    class AFNodeBooleanToggle(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBooleanToggle"
        bl_label = "Boolean Toggle"
        bl_icon = "BLANK1"

        default_value: bpy.props.BoolProperty(
            name="Initial State",
            default=False,
        )

        def init(self, context):
            del context
            value_socket = self.inputs.new("NodeSocketBool", "Value")
            value_socket.default_value = False
            self.outputs.new("NodeSocketBool", "State")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            row = layout.row(align=True)
            row.prop(self, "default_value", text=iface_("Initial"), toggle=True)
            current_value = bool(_ui_boolean_toggle_state_value(self, context))
            current_op = row.operator(
                "af.toggle_boolean_state",
                text=iface_("Current"),
                depress=current_value,
            )
            if current_op is not None:
                current_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                current_op.node_name = self.name
                current_op.group_path_json = _encoded_ui_group_path(self, context)

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
            self.outputs.new("AFSocketString", "String")
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            string_socket = getattr(getattr(self, "outputs", None), "get", lambda _name: None)("String")
            if string_socket is not None and str(getattr(string_socket, "bl_idname", "") or "") == "AFSocketString":
                return
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
        "AFNodeBooleanToggle": AFNodeBooleanToggle,
        "AFNodeSceneTime": AFNodeSceneTime,
        "AFNodeFloatInput": AFNodeFloatInput,
        "AFNodeBooleanInput": AFNodeBooleanInput,
        "AFNodeVectorInput": AFNodeVectorInput,
        "AFNodeIntegerInput": AFNodeIntegerInput,
        "AFNodeStringInput": AFNodeStringInput,
        "AFNodeInputRotation": AFNodeInputRotation,
        "AFNodeStatusInput": AFNodeStatusInput,
    }
