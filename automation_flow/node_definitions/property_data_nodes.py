import bpy
from bpy.app.translations import pgettext_iface as iface_


def _zh_ui():
    try:
        language = str(getattr(getattr(bpy.context, "preferences", None), "view", None).language or "")
    except Exception:
        language = ""
    return language.startswith("zh")


def build_property_data_node_classes(
    *,
    AFBaseNode,
    MODIFIER_NAME_MATCH_MODE_ITEMS,
    MODIFIER_TYPE_FILTER_ITEMS,
    OBJECT_DISPLAY_TYPE_ITEMS,
    OBJECT_ROTATION_MODE_ITEMS,
    PROPERTY_DATA_OUTPUT_MODE_ITEMS,
    PROPERTY_VALUE_SOURCE_ITEMS,
    _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS,
    _apply_property_data_socket_visibility,
    _draw_modifier_property_assignment_fields,
    _draw_object_display_property_assignment_fields,
    _draw_object_transform_property_assignment_fields,
    _hide_default_auxiliary_outputs,
    _initialize_object_transform_property_input_defaults,
    _persist_property_data_manual_hidden_keys,
    _property_data_output_specs,
    _property_data_update_socket_layout,
    _refresh_property_data_socket_visibility,
    _resolve_property_data_manual_hidden_keys,
    _set_default_node_width,
    _sync_object_transform_property_data_sockets,
    _sync_property_data_node_sockets,
):
    class AFNodeModifierPropertyData(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeModifierPropertyData"
        bl_label = "Modifier Property Data"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Modifier Data")

        output_mode: bpy.props.EnumProperty(name="Output Mode", items=PROPERTY_DATA_OUTPUT_MODE_ITEMS, default="ASSIGNMENT", update=_property_data_update_socket_layout)
        capture_show_viewport: bpy.props.BoolProperty(name="Show Viewport", default=True, update=_property_data_update_socket_layout)
        capture_show_render: bpy.props.BoolProperty(name="Show Render", default=False, update=_property_data_update_socket_layout)
        capture_show_in_editmode: bpy.props.BoolProperty(name="Show In Edit Mode", default=False, update=_property_data_update_socket_layout)
        source_show_viewport: bpy.props.EnumProperty(name="Show Viewport Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_show_render: bpy.props.EnumProperty(name="Show Render Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_show_in_editmode: bpy.props.EnumProperty(name="Show In Edit Mode Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        filter_by_type: bpy.props.BoolProperty(name="Type", default=False, update=_property_data_update_socket_layout)
        filter_by_name: bpy.props.BoolProperty(name="Name", default=False, update=_property_data_update_socket_layout)
        filter_by_context: bpy.props.BoolProperty(name="Context", default=False, update=_property_data_update_socket_layout)
        modifier_type_filter: bpy.props.EnumProperty(name="Modifier Filter", items=MODIFIER_TYPE_FILTER_ITEMS, default="ALL")
        modifier_name_match_mode: bpy.props.EnumProperty(name="Name Match", items=MODIFIER_NAME_MATCH_MODE_ITEMS, default="EXACT")

        def init(self, context):
            del context
            _sync_property_data_node_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            _persist_property_data_manual_hidden_keys(self)
            _refresh_property_data_socket_visibility(self)
            layout.prop(self, "output_mode", expand=True)
            _draw_modifier_property_assignment_fields(layout, self, "Property Fields")

        def update(self):
            manual_hidden_keys = _resolve_property_data_manual_hidden_keys(self)
            _sync_property_data_node_sockets(self, manual_hidden_keys=manual_hidden_keys)

    class AFNodeObjectDisplayPropertyData(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeObjectDisplayPropertyData"
        bl_label = "Object Display Property Data"
        bl_icon = "BLANK1"

        def draw_label(self):
            if _zh_ui():
                return iface_("Object Display Property Data")
            return iface_("Display Data")

        output_mode: bpy.props.EnumProperty(name="Output Mode", items=PROPERTY_DATA_OUTPUT_MODE_ITEMS, default="ASSIGNMENT", update=_property_data_update_socket_layout)
        capture_hide_viewport: bpy.props.BoolProperty(name="Hide Viewport", default=True, update=_property_data_update_socket_layout)
        capture_hide_render: bpy.props.BoolProperty(name="Hide Render", default=False, update=_property_data_update_socket_layout)
        capture_show_in_front: bpy.props.BoolProperty(name="Show In Front", default=False, update=_property_data_update_socket_layout)
        capture_show_name: bpy.props.BoolProperty(name="Show Name", default=False, update=_property_data_update_socket_layout)
        capture_show_axis: bpy.props.BoolProperty(name="Show Axis", default=False, update=_property_data_update_socket_layout)
        capture_display_type: bpy.props.BoolProperty(name="Display Type", default=False)
        source_hide_viewport: bpy.props.EnumProperty(name="Hide Viewport Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_hide_render: bpy.props.EnumProperty(name="Hide Render Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_show_in_front: bpy.props.EnumProperty(name="Show In Front Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_show_name: bpy.props.EnumProperty(name="Show Name Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_show_axis: bpy.props.EnumProperty(name="Show Axis Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_display_type: bpy.props.EnumProperty(name="Display Type Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        target_display_type: bpy.props.EnumProperty(name="Target Display Type", items=OBJECT_DISPLAY_TYPE_ITEMS, default="TEXTURED")

        def init(self, context):
            del context
            _sync_property_data_node_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            _persist_property_data_manual_hidden_keys(self)
            _refresh_property_data_socket_visibility(self)
            layout.prop(self, "output_mode", expand=True)
            _draw_object_display_property_assignment_fields(layout, self, "Property Fields")

        def update(self):
            manual_hidden_keys = _resolve_property_data_manual_hidden_keys(self)
            _sync_property_data_node_sockets(self, manual_hidden_keys=manual_hidden_keys)

    class AFNodeObjectTransformPropertyData(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeObjectTransformPropertyData"
        bl_label = "Object Transform Property Data"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Transform Data")

        output_mode: bpy.props.EnumProperty(name="Output Mode", items=PROPERTY_DATA_OUTPUT_MODE_ITEMS, default="ASSIGNMENT", update=_property_data_update_socket_layout)
        capture_location: bpy.props.BoolProperty(name="Location", default=True, update=_property_data_update_socket_layout)
        capture_rotation: bpy.props.BoolProperty(name="Rotation", default=False, update=_property_data_update_socket_layout)
        capture_scale: bpy.props.BoolProperty(name="Scale", default=False, update=_property_data_update_socket_layout)
        capture_rotation_mode: bpy.props.BoolProperty(name="Rotation Mode", default=False, update=_property_data_update_socket_layout)
        source_location: bpy.props.EnumProperty(name="Location Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_rotation: bpy.props.EnumProperty(name="Rotation Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_scale: bpy.props.EnumProperty(name="Scale Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        source_rotation_mode: bpy.props.EnumProperty(name="Rotation Mode Source", items=PROPERTY_VALUE_SOURCE_ITEMS, default="VALUE")
        target_location: bpy.props.FloatVectorProperty(name="Target Location", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")
        target_rotation_mode: bpy.props.EnumProperty(name="Target Rotation Mode", items=OBJECT_ROTATION_MODE_ITEMS, default="XYZ")
        target_rotation_euler: bpy.props.FloatVectorProperty(name="Target Rotation", size=3, default=(0.0, 0.0, 0.0), subtype="EULER")
        target_rotation_quaternion: bpy.props.FloatVectorProperty(name="Target Quaternion", size=4, default=(1.0, 0.0, 0.0, 0.0))
        target_rotation_axis_angle: bpy.props.FloatVectorProperty(name="Target Axis Angle", size=4, default=(0.0, 0.0, 0.0, 1.0))
        target_scale: bpy.props.FloatVectorProperty(name="Target Scale", size=3, default=(1.0, 1.0, 1.0), subtype="XYZ")
        transform_inputs_initialized: bpy.props.BoolProperty(name="Transform Inputs Initialized", default=False, options={"HIDDEN"})

        def init(self, context):
            del context
            for socket_idname, socket_name in _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS:
                self.inputs.new(socket_idname, socket_name)
            for socket_idname, socket_name in _property_data_output_specs(self):
                self.outputs.new(socket_idname, socket_name)
            _initialize_object_transform_property_input_defaults(self)
            _apply_property_data_socket_visibility(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            _persist_property_data_manual_hidden_keys(self)
            _refresh_property_data_socket_visibility(self)
            layout.prop(self, "output_mode", expand=True)
            _draw_object_transform_property_assignment_fields(layout, self, "Property Fields")

        def update(self):
            manual_hidden_keys = _resolve_property_data_manual_hidden_keys(self)
            _sync_object_transform_property_data_sockets(self, manual_hidden_keys=manual_hidden_keys)

    return {
        "AFNodeModifierPropertyData": AFNodeModifierPropertyData,
        "AFNodeObjectDisplayPropertyData": AFNodeObjectDisplayPropertyData,
        "AFNodeObjectTransformPropertyData": AFNodeObjectTransformPropertyData,
    }
