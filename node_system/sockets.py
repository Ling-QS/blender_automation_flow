import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..i18n import af_iface
from .config import (
    OBJECT_INTERACTION_MODE_ITEMS,
    VIEWPORT_SHADING_MODE_ITEMS,
)
from ..runtime_core.registration import safe_register_class, safe_unregister_class
from .socket_aliases import (
    PROPERTY_ASSIGNMENT_INPUT_PREFIX,
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)

MENU_SOCKET_COLOR = (0.4, 0.4, 0.4, 1.0)
_FLOW_SOCKET_IDNAMES = {"AFSocketFlow", "AFInterfaceSocketFlow"}
_IDENTITY_ROTATION_DEFAULT = (1.0, 0.0, 0.0, 0.0)
_IDENTITY_MATRIX_DEFAULT = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)

DISPLAY_TYPE_MENU_ITEMS = (
    ("TEXTURED", "Textured", "Display the object with textured shading"),
    ("SOLID", "Solid", "Display the object with solid shading"),
    ("WIRE", "Wire", "Display the object as wireframe"),
    ("BOUNDS", "Bounds", "Display the object bounds only"),
)


ROTATION_MODE_MENU_ITEMS = (
    ("XYZ", "XYZ Euler", "Use XYZ Euler rotation"),
    ("XZY", "XZY Euler", "Use XZY Euler rotation"),
    ("YXZ", "YXZ Euler", "Use YXZ Euler rotation"),
    ("YZX", "YZX Euler", "Use YZX Euler rotation"),
    ("ZXY", "ZXY Euler", "Use ZXY Euler rotation"),
    ("ZYX", "ZYX Euler", "Use ZYX Euler rotation"),
    ("QUATERNION", "Quaternion", "Use Quaternion rotation"),
    ("AXIS_ANGLE", "Axis Angle", "Use Axis Angle rotation"),
)


def _virtual_socket_color():
    return (0.29, 0.29, 0.29, 1.0)


def is_flow_socket_idname(socket_idname):
    return str(socket_idname or "") in _FLOW_SOCKET_IDNAMES


def is_flow_socket(socket):
    if socket is None:
        return False
    socket_idname = str(getattr(socket, "bl_idname", "") or "")
    if is_flow_socket_idname(socket_idname):
        return True
    socket_type = str(getattr(socket, "socket_type", "") or "")
    if is_flow_socket_idname(socket_type):
        return True
    interface_socket_idname = str(getattr(socket, "bl_socket_idname", "") or "")
    if is_flow_socket_idname(interface_socket_idname):
        return True
    return False


def _socket_is_virtual(node, socket):
    if bool(getattr(socket, "af_is_virtual", False)):
        return True
    if getattr(node, "bl_idname", "") == "AFNodePhysicsBakeTask":
        return (
            not bool(getattr(socket, "is_output", False))
            and getattr(socket, "bl_idname", "") == "AFSocketPropertyPackage"
            and not bool(getattr(socket, "is_linked", False))
            and not str(getattr(socket, "name", "") or "").strip()
        )
    return False


def _draw_virtual_socket_button_row(layout, node, add_operator_idname, remove_operator_idname, remove_enabled):
    row = layout.row(align=True)
    add_operator = row.operator(add_operator_idname, text="", icon="ADD", emboss=False)
    add_operator.node_tree_name = getattr(getattr(node, "id_data", None), "name", "")
    add_operator.node_name = getattr(node, "name", "")
    remove_row = row.row(align=True)
    remove_row.enabled = bool(remove_enabled)
    remove_operator = remove_row.operator(remove_operator_idname, text="", icon="REMOVE", emboss=False)
    remove_operator.node_tree_name = getattr(getattr(node, "id_data", None), "name", "")
    remove_operator.node_name = getattr(node, "name", "")


def _translated_indexed_socket_label(text):
    raw_text = str(text or "")
    for prefix in (
        PROPERTY_ASSIGNMENT_INPUT_PREFIX,
        "Task Plan ",
        "Settings ",
    ):
        if not raw_text.startswith(prefix):
            continue
        suffix = raw_text[len(prefix):]
        if suffix.isdigit():
            return f"{af_iface(prefix.strip(), compact=True)} {suffix}"
    return af_iface(raw_text, compact=True) if raw_text else raw_text


class AFBaseInterfaceSocket(bpy.types.NodeTreeInterfaceSocket):
    bl_socket_idname = ""
    bl_label = "Automation Flow Socket"
    bl_icon = "NODE"

    def draw(self, context, layout):
        del context
        display_text = af_iface(self.name if self.name else self.bl_label, compact=True)
        layout.label(text=display_text, translate=False)

    def init_socket(self, node, socket, data_path):
        del node, socket, data_path

    def from_socket(self, node, socket):
        del node, socket


class AFBaseSocket(bpy.types.NodeSocket):
    bl_icon = "NODE"
    SOCKET_COLOR = (0.8, 0.8, 0.8, 1.0)

    def draw(self, context, layout, node, text):
        del context, node
        layout.label(text=text if text else self.bl_label)

    def draw_color(self, context, node):
        del context
        if _socket_is_virtual(node, self):
            return _virtual_socket_color()
        return self.SOCKET_COLOR

    @classmethod
    def draw_color_simple(cls):
        return cls.SOCKET_COLOR


class AFBaseNumericSocket(AFBaseSocket):
    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)

    def _draw_default_value(self, layout, text):
        layout.prop(self, "default_value", text=text if text else self.bl_label)

    def draw(self, context, layout, node, text):
        del context
        try:
            from ..nodes import _draw_property_data_input_socket

            if _draw_property_data_input_socket(self, layout, node, text):
                return
        except Exception:
            pass

        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeIndexSwitch" and bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_index_switch_real_inputs

                real_input_count = len(_iter_index_switch_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_index_switch_input",
                "af.remove_last_index_switch_input",
                real_input_count > 1,
            )
            return

        if bool(getattr(self, "is_output", False)):
            layout.label(text=text if text else self.bl_label)
            return

        if not bool(getattr(self, "is_linked", False)):
            self._draw_default_value(layout, text)
            return
        layout.label(text=text if text else self.bl_label)


class AFBaseMenuSocket(AFBaseSocket):
    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)
    HIDE_DEFAULT_LABEL = False

    def _draw_default_value(self, layout, text):
        if bool(getattr(self, "HIDE_DEFAULT_LABEL", False)):
            layout.prop(self, "default_value", text="")
            return
        layout.prop(self, "default_value", text=text if text else self.bl_label)

    def draw(self, context, layout, node, text):
        del context
        try:
            from ..nodes import _draw_property_data_input_socket

            if _draw_property_data_input_socket(self, layout, node, text):
                return
        except Exception:
            pass

        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeIndexSwitch" and bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_index_switch_real_inputs

                real_input_count = len(_iter_index_switch_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_index_switch_input",
                "af.remove_last_index_switch_input",
                real_input_count > 1,
            )
            return

        if bool(getattr(self, "is_output", False)):
            layout.label(text=text if text else self.bl_label)
            return

        if not bool(getattr(self, "is_linked", False)):
            self._draw_default_value(layout, text)
            return
        layout.label(text=text if text else self.bl_label)


class AFBaseStringSocket(AFBaseSocket):
    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)
    HIDE_DEFAULT_LABEL = False

    def _draw_default_value(self, layout, text):
        if bool(getattr(self, "HIDE_DEFAULT_LABEL", False)):
            layout.prop(self, "default_value", text="")
            return
        layout.prop(self, "default_value", text=text if text else self.bl_label)

    def draw(self, context, layout, node, text):
        del context
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeIndexSwitch" and bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_index_switch_real_inputs

                real_input_count = len(_iter_index_switch_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_index_switch_input",
                "af.remove_last_index_switch_input",
                real_input_count > 1,
            )
            return
        if bool(getattr(self, "is_output", False)):
            if node_type == "AFNodeStringInput" and str(getattr(self, "bl_idname", "") or "") == "AFSocketString":
                self._draw_default_value(layout, text)
                return
            layout.label(text=text if text else self.bl_label)
            return
        if not bool(getattr(self, "is_linked", False)):
            self._draw_default_value(layout, text)
            return
        layout.label(text=text if text else self.bl_label)


_PREVIEW_BUILTIN_SOCKET_COLOR_BY_IDNAME = {
    "NodeSocketBool": (0.8, 0.65, 0.84, 1.0),
    "NodeSocketInt": (0.35, 0.55, 0.36, 1.0),
    "NodeSocketFloat": (0.63, 0.63, 0.63, 1.0),
    "NodeSocketString": (0.44, 0.70, 1.0, 1.0),
    "NodeSocketVector": (0.39, 0.39, 0.78, 1.0),
    "NodeSocketRotation": (0.65, 0.39, 0.78, 1.0),
    "NodeSocketMatrix": (0.72, 0.20, 0.52, 1.0),
}

_PREVIEW_CUSTOM_SOCKET_CLASS_BY_IDNAME = {
    "AFSocketObjectList": "AFSocketObjectList",
    "AFSocketString": "AFSocketString",
    "AFSocketDisplayType": "AFSocketDisplayType",
    "AFSocketObjectInteractionMode": "AFSocketObjectInteractionMode",
    "AFSocketRotationMode": "AFSocketRotationMode",
    "AFSocketViewportShadingMode": "AFSocketViewportShadingMode",
    "AFSocketPropertyDefinition": "AFSocketPropertyDefinition",
    "AFSocketPropertyAssignment": "AFSocketPropertyAssignment",
    "AFSocketPropertyPackage": "AFSocketPropertyPackage",
    "AFSocketTaskRef": "AFSocketTaskRef",
    "AFSocketTaskPlan": "AFSocketTaskPlan",
    "AFSocketTaskHandle": "AFSocketTaskHandle",
    "AFSocketReport": "AFSocketReport",
    "AFSocketMatrixValue": "AFSocketMatrixValue",
}


def _preview_mode_socket_idname(mode):
    try:
        from .tree import _PREVIEW_DYNAMIC_MODE_TO_SOCKET

        return str(_PREVIEW_DYNAMIC_MODE_TO_SOCKET.get(str(mode or ""), "") or "")
    except Exception:
        return ""


def _preview_socket_color_for_mode(mode, fallback):
    socket_idname = _preview_mode_socket_idname(mode)
    if not socket_idname:
        return fallback
    builtin_color = _PREVIEW_BUILTIN_SOCKET_COLOR_BY_IDNAME.get(socket_idname)
    if builtin_color is not None:
        return builtin_color
    builtin_socket_type = getattr(bpy.types, str(socket_idname or ""), None)
    if builtin_socket_type is not None:
        try:
            return builtin_socket_type.draw_color_simple()
        except Exception:
            pass
    socket_class_name = _PREVIEW_CUSTOM_SOCKET_CLASS_BY_IDNAME.get(socket_idname, "")
    socket_class = globals().get(socket_class_name)
    if socket_class is None:
        return fallback
    return getattr(socket_class, "SOCKET_COLOR", fallback)


class AFSocketFlow(AFBaseSocket):
    bl_idname = "AFSocketFlow"
    bl_label = "Flow"
    bl_icon = "SORTTIME"
    SOCKET_COLOR = (0.10, 0.42, 0.98, 1.0)


class AFSocketObjectList(AFBaseSocket):
    bl_idname = "AFSocketObjectList"
    bl_label = "Object List"
    bl_icon = "OUTLINER_OB_GROUP_INSTANCE"
    SOCKET_COLOR = (0.45, 0.85, 0.95, 1.0)

class AFSocketCollectionList(AFBaseSocket):
    bl_idname = "AFSocketCollectionList"
    bl_label = "Collection List"
    bl_icon = "OUTLINER_COLLECTION"
    SOCKET_COLOR = (0.55, 0.75, 0.95, 1.0)


class AFSocketString(AFBaseStringSocket):
    bl_idname = "AFSocketString"
    bl_label = "String"
    bl_icon = "SORTALPHA"
    SOCKET_COLOR = (0.44, 0.70, 1.0, 1.0)
    HIDE_DEFAULT_LABEL = True

    default_value: bpy.props.StringProperty(name="Value", default="")


class AFSocketPropertyPackage(AFBaseSocket):
    bl_idname = "AFSocketPropertyPackage"
    bl_label = PROPERTY_PACKAGE_SOCKET_NAME
    bl_icon = "NODE_COMPOSITING"
    SOCKET_COLOR = (0.55, 0.90, 0.55, 1.0)

    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)

    def draw(self, context, layout, node, text):
        del context
        if getattr(node, "bl_idname", "") == "AFNodeIndexSwitch" and bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_index_switch_real_inputs

                real_input_count = len(_iter_index_switch_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_index_switch_input",
                "af.remove_last_index_switch_input",
                real_input_count > 1,
            )
            return
        display_text = _translated_indexed_socket_label(text if text else self.bl_label)
        layout.label(text=display_text, translate=False)


class AFSocketPropertyDefinition(AFBaseSocket):
    bl_idname = "AFSocketPropertyDefinition"
    bl_label = PROPERTY_DEFINITION_SOCKET_NAME
    bl_icon = "PREFERENCES"
    SOCKET_COLOR = (0.46, 0.30, 0.14, 1.0)

    def draw(self, context, layout, node, text):
        del context, node
        layout.label(text=af_iface(text if text else self.bl_label, compact=True), translate=False)


class AFSocketPropertyAssignment(AFBaseSocket):
    bl_idname = "AFSocketPropertyAssignment"
    bl_label = PROPERTY_ASSIGNMENT_SOCKET_NAME
    bl_icon = "SETTINGS"
    SOCKET_COLOR = (0.58, 0.20, 0.12, 1.0)

    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)

    def draw(self, context, layout, node, text):
        del context
        if getattr(node, "bl_idname", "") == "AFNodeIndexSwitch" and bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_index_switch_real_inputs

                real_input_count = len(_iter_index_switch_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_index_switch_input",
                "af.remove_last_index_switch_input",
                real_input_count > 1,
            )
            return
        display_text = _translated_indexed_socket_label(text if text else self.bl_label)
        layout.label(text=display_text, translate=False)


class AFSocketTaskRef(AFBaseSocket):
    bl_idname = "AFSocketTaskRef"
    bl_label = "Task Ref"
    bl_icon = "PLAY"
    SOCKET_COLOR = (0.95, 0.75, 0.25, 1.0)


class AFSocketTaskPlan(AFBaseSocket):
    bl_idname = "AFSocketTaskPlan"
    bl_label = "Task Plan"
    bl_icon = "PLAY"
    SOCKET_COLOR = (0.95, 0.55, 0.20, 1.0)

    af_enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    af_display_title: bpy.props.StringProperty(name="Title", default="")
    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=False)

    def draw(self, context, layout, node, text):
        del context
        if getattr(node, "bl_idname", "") != "AFNodeRunTaskPlan" or bool(getattr(self, "is_output", False)):
            layout.label(text=text if text else self.bl_label)
            return

        if bool(getattr(self, "af_is_virtual", False)):
            try:
                from ..nodes import _iter_run_task_plan_real_inputs

                real_input_count = len(_iter_run_task_plan_real_inputs(node))
            except Exception:
                real_input_count = 0
            _draw_virtual_socket_button_row(
                layout,
                node,
                "af.add_task_plan_input",
                "af.remove_last_task_plan_input",
                real_input_count > 1,
            )
            return

        row = layout.row(align=True)
        row.prop(self, "af_display_title", text="")
        toggle = row.row(align=True)
        toggle.prop(self, "af_enabled", text="")


class AFSocketTaskHandle(AFBaseSocket):
    bl_idname = "AFSocketTaskHandle"
    bl_label = "Task Handle"
    bl_icon = "DECORATE_OVERRIDE"
    SOCKET_COLOR = (0.20, 0.72, 0.66, 1.0)


class AFSocketPreviewData(AFBaseSocket):
    bl_idname = "AFSocketPreviewData"
    bl_label = "Preview"
    bl_icon = "INFO"
    SOCKET_COLOR = (0.55, 0.55, 0.55, 1.0)

    af_is_virtual: bpy.props.BoolProperty(name="Virtual", default=True)

    def draw(self, context, layout, node, text):
        del context
        if bool(getattr(self, "is_output", False)):
            layout.label(text=text if text else self.bl_label)
            return
        if bool(getattr(self, "af_is_virtual", False)):
            if getattr(node, "bl_idname", "") == "AFNodeSampleContextData":
                layout.label(text="")
                return
            layout.label(text=text if text else self.bl_label)
            return
        layout.label(text=text if text else self.bl_label)

    def draw_color(self, context, node):
        if bool(getattr(self, "af_is_virtual", False)):
            return _virtual_socket_color()
        try:
            from ..nodes import _find_single_from_input_socket

            upstream_node, upstream_socket = _find_single_from_input_socket(self)
        except Exception:
            upstream_node, upstream_socket = None, None
        if upstream_socket is not None and upstream_node is not None:
            try:
                return upstream_socket.draw_color(context, upstream_node)
            except Exception:
                pass
        mode = str(getattr(node, "preview_mode", "OBJECT_LIST") or "OBJECT_LIST")
        return _preview_socket_color_for_mode(mode, self.SOCKET_COLOR)


class AFSocketFloatValue(AFBaseNumericSocket):
    bl_idname = "AFSocketFloatValue"
    bl_label = "Float"
    bl_icon = "RNDCURVE"
    SOCKET_COLOR = (0.63, 0.63, 0.63, 1.0)

    default_value: bpy.props.FloatProperty(name="Value", default=0.0)


class AFSocketIntegerValue(AFBaseNumericSocket):
    bl_idname = "AFSocketIntegerValue"
    bl_label = "Integer"
    bl_icon = "SORTBYEXT"
    SOCKET_COLOR = (0.35, 0.55, 0.36, 1.0)

    default_value: bpy.props.IntProperty(name="Value", default=0)


class AFSocketBooleanValue(AFBaseNumericSocket):
    bl_idname = "AFSocketBooleanValue"
    bl_label = "Boolean"
    bl_icon = "CHECKBOX_HLT"
    SOCKET_COLOR = (0.8, 0.65, 0.84, 1.0)

    default_value: bpy.props.BoolProperty(name="Value", default=False)


class AFSocketVectorValue(AFBaseNumericSocket):
    bl_idname = "AFSocketVectorValue"
    bl_label = "Vector"
    bl_icon = "EMPTY_AXIS"
    SOCKET_COLOR = (0.39, 0.39, 0.78, 1.0)

    default_value: bpy.props.FloatVectorProperty(name="Value", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")

    def _draw_default_value(self, layout, text):
        root_col = layout.column(align=True)
        if text:
            root_col.label(text=text)
        value_col = root_col.column(align=True)
        value_col.prop(self, "default_value", index=0, text="X")
        value_col.prop(self, "default_value", index=1, text="Y")
        value_col.prop(self, "default_value", index=2, text="Z")


class AFSocketRotationValue(AFBaseNumericSocket):
    bl_idname = "AFSocketRotationValue"
    bl_label = "Rotation"
    bl_icon = "DRIVER_ROTATIONAL_DIFFERENCE"
    SOCKET_COLOR = (0.65, 0.39, 0.78, 1.0)

    default_value: bpy.props.FloatVectorProperty(name="Value", size=4, default=_IDENTITY_ROTATION_DEFAULT)

    def _draw_default_value(self, layout, text):
        root_col = layout.column(align=True)
        if text:
            root_col.label(text=text)
        value_col = root_col.column(align=True)
        value_col.prop(self, "default_value", index=0, text="W")
        value_col.prop(self, "default_value", index=1, text="X")
        value_col.prop(self, "default_value", index=2, text="Y")
        value_col.prop(self, "default_value", index=3, text="Z")


class AFSocketMatrixValue(AFBaseNumericSocket):
    bl_idname = "AFSocketMatrixValue"
    bl_label = "Matrix"
    bl_icon = "SNAP_VOLUME"
    SOCKET_COLOR = (0.72, 0.20, 0.52, 1.0)

    default_value: bpy.props.FloatVectorProperty(name="Value", size=16, default=_IDENTITY_MATRIX_DEFAULT)

    def _draw_default_value(self, layout, text):
        root_col = layout.column(align=True)
        if text:
            root_col.label(text=text)
        value_col = root_col.column(align=True)
        for row_index in range(4):
            row = value_col.row(align=True)
            for column_index in range(4):
                flat_index = row_index * 4 + column_index
                row.prop(self, "default_value", index=flat_index, text="")


class AFSocketDisplayType(AFBaseMenuSocket):
    bl_idname = "AFSocketDisplayType"
    bl_label = "Display Type"
    bl_icon = "DOWNARROW_HLT"
    SOCKET_COLOR = MENU_SOCKET_COLOR
    HIDE_DEFAULT_LABEL = True

    default_value: bpy.props.EnumProperty(name="Display Type", items=DISPLAY_TYPE_MENU_ITEMS, default="TEXTURED")


class AFSocketRotationMode(AFBaseMenuSocket):
    bl_idname = "AFSocketRotationMode"
    bl_label = "Rotation Mode"
    bl_icon = "DOWNARROW_HLT"
    SOCKET_COLOR = MENU_SOCKET_COLOR
    HIDE_DEFAULT_LABEL = True

    default_value: bpy.props.EnumProperty(name="Rotation Mode", items=ROTATION_MODE_MENU_ITEMS, default="XYZ")


class AFSocketObjectInteractionMode(AFBaseMenuSocket):
    bl_idname = "AFSocketObjectInteractionMode"
    bl_label = "Object Interaction Mode"
    bl_icon = "DOWNARROW_HLT"
    SOCKET_COLOR = MENU_SOCKET_COLOR
    HIDE_DEFAULT_LABEL = True

    default_value: bpy.props.EnumProperty(name="Object Interaction Mode", items=OBJECT_INTERACTION_MODE_ITEMS, default="OBJECT")


class AFSocketViewportShadingMode(AFBaseMenuSocket):
    bl_idname = "AFSocketViewportShadingMode"
    bl_label = "Viewport Shading Mode"
    bl_icon = "DOWNARROW_HLT"
    SOCKET_COLOR = MENU_SOCKET_COLOR
    HIDE_DEFAULT_LABEL = True

    default_value: bpy.props.EnumProperty(name="Viewport Shading Mode", items=VIEWPORT_SHADING_MODE_ITEMS, default="SOLID")


class AFSocketReport(AFBaseSocket):
    bl_idname = "AFSocketReport"
    bl_label = "Report"
    bl_icon = "TEXT"
    SOCKET_COLOR = (1.0, 1.0, 1.0, 1.0)


class AFInterfaceSocketFlow(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketFlow"
    bl_label = "Flow"
    bl_icon = "SORTTIME"


class AFInterfaceSocketCollectionList(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketCollectionList"
    bl_label = "Collection List"
    bl_icon = "OUTLINER_COLLECTION"


class AFInterfaceSocketString(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketString"
    bl_label = "String"
    bl_icon = "SORTALPHA"


class AFInterfaceSocketObjectList(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketObjectList"
    bl_label = "Object List"
    bl_icon = "OUTLINER_OB_GROUP_INSTANCE"

class AFInterfaceSocketPropertyPackage(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketPropertyPackage"
    bl_label = PROPERTY_PACKAGE_SOCKET_NAME
    bl_icon = "NODE_COMPOSITING"


class AFInterfaceSocketPropertyDefinition(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketPropertyDefinition"
    bl_label = PROPERTY_DEFINITION_SOCKET_NAME
    bl_icon = "PREFERENCES"


class AFInterfaceSocketPropertyAssignment(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketPropertyAssignment"
    bl_label = PROPERTY_ASSIGNMENT_SOCKET_NAME
    bl_icon = "SETTINGS"


class AFInterfaceSocketTaskRef(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketTaskRef"
    bl_label = "Task Ref"
    bl_icon = "PLAY"


class AFInterfaceSocketTaskPlan(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketTaskPlan"
    bl_label = "Task Plan"
    bl_icon = "PLAY"


class AFInterfaceSocketTaskHandle(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketTaskHandle"
    bl_label = "Task Handle"
    bl_icon = "DECORATE_OVERRIDE"


class AFInterfaceSocketFloatValue(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketFloatValue"
    bl_label = "Float"
    bl_icon = "RNDCURVE"


class AFInterfaceSocketIntegerValue(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketIntegerValue"
    bl_label = "Integer"
    bl_icon = "SORTBYEXT"


class AFInterfaceSocketBooleanValue(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketBooleanValue"
    bl_label = "Boolean"
    bl_icon = "CHECKBOX_HLT"


class AFInterfaceSocketVectorValue(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketVectorValue"
    bl_label = "Vector"
    bl_icon = "EMPTY_AXIS"


class AFInterfaceSocketRotationValue(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketRotationValue"
    bl_label = "Rotation"
    bl_icon = "DRIVER_ROTATIONAL_DIFFERENCE"


class AFInterfaceSocketDisplayType(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketDisplayType"
    bl_label = "Display Type"
    bl_icon = "DOWNARROW_HLT"

    default_value: bpy.props.EnumProperty(name="Display Type", items=DISPLAY_TYPE_MENU_ITEMS, default="TEXTURED")

    def init_socket(self, node, socket, data_path):
        del node, data_path
        try:
            socket.default_value = str(getattr(self, "default_value", "TEXTURED") or "TEXTURED")
        except Exception:
            pass
        try:
            socket.hide_value = bool(getattr(self, "hide_value", False))
        except Exception:
            pass

    def from_socket(self, node, socket):
        del node
        try:
            self.default_value = str(getattr(socket, "default_value", "TEXTURED") or "TEXTURED")
        except Exception:
            pass
        try:
            self.hide_value = bool(getattr(socket, "hide_value", False))
        except Exception:
            pass


class AFInterfaceSocketRotationMode(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketRotationMode"
    bl_label = "Rotation Mode"
    bl_icon = "DOWNARROW_HLT"

    default_value: bpy.props.EnumProperty(name="Rotation Mode", items=ROTATION_MODE_MENU_ITEMS, default="XYZ")

    def init_socket(self, node, socket, data_path):
        del node, data_path
        try:
            socket.default_value = str(getattr(self, "default_value", "XYZ") or "XYZ")
        except Exception:
            pass
        try:
            socket.hide_value = bool(getattr(self, "hide_value", False))
        except Exception:
            pass

    def from_socket(self, node, socket):
        del node
        try:
            self.default_value = str(getattr(socket, "default_value", "XYZ") or "XYZ")
        except Exception:
            pass
        try:
            self.hide_value = bool(getattr(socket, "hide_value", False))
        except Exception:
            pass


class AFInterfaceSocketObjectInteractionMode(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketObjectInteractionMode"
    bl_label = "Object Interaction Mode"
    bl_icon = "DOWNARROW_HLT"

    default_value: bpy.props.EnumProperty(name="Object Interaction Mode", items=OBJECT_INTERACTION_MODE_ITEMS, default="OBJECT")

    def init_socket(self, node, socket, data_path):
        del node, data_path
        try:
            socket.default_value = str(getattr(self, "default_value", "OBJECT") or "OBJECT")
        except Exception:
            pass
        try:
            socket.hide_value = bool(getattr(self, "hide_value", False))
        except Exception:
            pass

    def from_socket(self, node, socket):
        del node
        try:
            self.default_value = str(getattr(socket, "default_value", "OBJECT") or "OBJECT")
        except Exception:
            pass
        try:
            self.hide_value = bool(getattr(socket, "hide_value", False))
        except Exception:
            pass


class AFInterfaceSocketViewportShadingMode(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketViewportShadingMode"
    bl_label = "Viewport Shading Mode"
    bl_icon = "DOWNARROW_HLT"

    default_value: bpy.props.EnumProperty(name="Viewport Shading Mode", items=VIEWPORT_SHADING_MODE_ITEMS, default="SOLID")

    def init_socket(self, node, socket, data_path):
        del node, data_path
        try:
            socket.default_value = str(getattr(self, "default_value", "SOLID") or "SOLID")
        except Exception:
            pass
        try:
            socket.hide_value = bool(getattr(self, "hide_value", False))
        except Exception:
            pass

    def from_socket(self, node, socket):
        del node
        try:
            self.default_value = str(getattr(socket, "default_value", "SOLID") or "SOLID")
        except Exception:
            pass
        try:
            self.hide_value = bool(getattr(socket, "hide_value", False))
        except Exception:
            pass


class AFInterfaceSocketReport(AFBaseInterfaceSocket):
    bl_socket_idname = "AFSocketReport"
    bl_label = "Report"
    bl_icon = "TEXT"


LEGACY_INTERFACE_SOCKET_CLASSES = (
    AFInterfaceSocketFloatValue,
    AFInterfaceSocketIntegerValue,
    AFInterfaceSocketBooleanValue,
    AFInterfaceSocketVectorValue,
)


CLASSES = (
    AFBaseSocket,
    AFSocketFlow,
    AFSocketCollectionList,
    AFSocketString,
    AFSocketObjectList,
    AFSocketPropertyPackage,
    AFSocketPropertyDefinition,
    AFSocketPropertyAssignment,
    AFSocketTaskRef,
    AFSocketTaskPlan,
    AFSocketTaskHandle,
    AFSocketPreviewData,
    AFSocketFloatValue,
    AFSocketIntegerValue,
    AFSocketBooleanValue,
    AFSocketVectorValue,
    AFSocketRotationValue,
    AFSocketMatrixValue,
    AFSocketDisplayType,
    AFSocketObjectInteractionMode,
    AFSocketRotationMode,
    AFSocketViewportShadingMode,
    AFSocketReport,
    AFInterfaceSocketFlow,
    AFInterfaceSocketCollectionList,
    AFInterfaceSocketString,
    AFInterfaceSocketObjectList,
    AFInterfaceSocketPropertyPackage,
    AFInterfaceSocketPropertyDefinition,
    AFInterfaceSocketPropertyAssignment,
    AFInterfaceSocketTaskRef,
    AFInterfaceSocketTaskPlan,
    AFInterfaceSocketTaskHandle,
    AFInterfaceSocketRotationValue,
    AFInterfaceSocketDisplayType,
    AFInterfaceSocketObjectInteractionMode,
    AFInterfaceSocketRotationMode,
    AFInterfaceSocketViewportShadingMode,
    AFInterfaceSocketReport,
)


def register():
    # Hot-reload can leave older interface socket classes registered even after
    # they are removed from the active registration list, so explicitly clear
    # these deprecated numeric variants before registering the current set.
    for cls in LEGACY_INTERFACE_SOCKET_CLASSES:
        safe_unregister_class(cls)
    for cls in CLASSES:
        safe_register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
