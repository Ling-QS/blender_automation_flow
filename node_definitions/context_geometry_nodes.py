import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..node_system.socket_aliases import (
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)


def build_context_geometry_node_classes(
    *,
    AFBaseNode,
    CONTEXT_REDUCE_OPERATION_ITEMS,
    CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE,
    CONTEXT_REDUCE_VALUE_TYPE_ITEMS,
    CONTEXT_REDUCE_VECTOR_MODE_ITEMS,
    GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE,
    GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS,
    SAMPLE_OBJECT_INDEX_MODE_ITEMS,
    SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE,
    PREVIEW_DATA_VIRTUAL_LABEL,
    _find_single_from_input_socket,
    _hide_default_auxiliary_outputs,
    _set_default_node_width,
    _set_node_color,
    _socket_signature,
    _sync_node_sockets_in_place,
):
    sample_context_data_sync_guard = set()
    context_reduce_sync_guard = set()
    set_geometry_attribute_sync_guard = set()
    publish_geometry_attribute_sync_guard = set()

    def _context_reduce_socket_idname_for_type(value_type):
        return CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE.get(str(value_type), "NodeSocketFloat")

    def _sync_property_context_sockets(node):
        _hide_default_auxiliary_outputs(node)

    def _sample_context_data_real_inputs(node):
        return [
            socket
            for socket in getattr(node, "inputs", [])
            if str(getattr(socket, "bl_idname", "") or "") == "AFSocketPreviewData"
            and not bool(getattr(socket, "af_is_virtual", False))
        ]

    def _sample_context_data_unique_names(source_names):
        counts = {}
        unique_names = []
        reserved_names = {"Object List", "Object Index", "Report"}
        for raw_name in list(source_names or []):
            base_name = str(raw_name or "").strip() or "Value"
            suffix = int(counts.get(base_name, 0) or 0)
            while True:
                suffix += 1
                candidate = base_name if suffix == 1 else f"{base_name} {suffix}"
                if candidate not in reserved_names:
                    break
            counts[base_name] = int(suffix)
            reserved_names.add(candidate)
            unique_names.append(candidate)
        return tuple(unique_names)

    def _sync_sample_context_data_sockets(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in sample_context_data_sync_guard:
            return
        sample_context_data_sync_guard.add(node_key)
        try:
            source_entries = []
            for socket in list(getattr(node, "inputs", []) or []):
                if str(getattr(socket, "bl_idname", "") or "") != "AFSocketPreviewData":
                    continue
                if bool(getattr(socket, "af_is_virtual", False)) and not bool(getattr(socket, "is_linked", False)):
                    continue
                from_node, from_socket = _find_single_from_input_socket(socket)
                if from_node is None or from_socket is None:
                    continue
                source_entries.append(
                    (
                        str(getattr(from_socket, "bl_idname", "") or ""),
                        str(getattr(from_socket, "name", "") or ""),
                    )
                )

            unique_names = _sample_context_data_unique_names(entry[1] for entry in source_entries)
            input_specs = [
                ("AFSocketObjectList", "Object List"),
                ("NodeSocketInt", "Object Index"),
            ]
            output_specs = []
            for index, (socket_idname, _raw_name) in enumerate(source_entries):
                socket_name = unique_names[index]
                input_specs.append(("AFSocketPreviewData", socket_name))
                output_specs.append((socket_idname, socket_name))
            input_specs.append(("AFSocketPreviewData", PREVIEW_DATA_VIRTUAL_LABEL))
            output_specs.append(("AFSocketReport", "Report"))
            _sync_node_sockets_in_place(node, tuple(input_specs), tuple(output_specs))

            dynamic_inputs = [
                socket
                for socket in getattr(node, "inputs", [])
                if str(getattr(socket, "bl_idname", "") or "") == "AFSocketPreviewData"
            ]
            for index, socket in enumerate(dynamic_inputs):
                is_virtual = index == len(dynamic_inputs) - 1
                try:
                    socket.af_is_virtual = bool(is_virtual)
                except Exception:
                    pass
                target_name = PREVIEW_DATA_VIRTUAL_LABEL if is_virtual else unique_names[index]
                if str(getattr(socket, "name", "") or "") != target_name:
                    try:
                        socket.name = target_name
                    except Exception:
                        pass

            index_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Object Index")
            if index_socket is not None and hasattr(index_socket, "default_value"):
                try:
                    index_socket.default_value = int(getattr(index_socket, "default_value", 0) or 0)
                except Exception:
                    pass
            _hide_default_auxiliary_outputs(node)
        finally:
            sample_context_data_sync_guard.discard(node_key)

    def _sync_context_reduce_value_sockets(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in context_reduce_sync_guard:
            return
        context_reduce_sync_guard.add(node_key)
        try:
            value_socket_idname = _context_reduce_socket_idname_for_type(getattr(node, "value_type", "FLOAT"))
            input_specs = (
                (value_socket_idname, "Value"),
            )
            output_specs = (
                (value_socket_idname, "Value"),
                ("AFSocketObjectList", "Object"),
                ("NodeSocketInt", "Object Index"),
                ("AFSocketReport", "Report"),
            )
            _sync_node_sockets_in_place(node, input_specs, output_specs)
            value_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Value")
            if value_socket is not None:
                try:
                    value_socket.hide_value = True
                except Exception:
                    pass
            _hide_default_auxiliary_outputs(node)
        finally:
            context_reduce_sync_guard.discard(node_key)

    def _sync_geometry_attribute_node_sockets(node):
        input_specs = (
            ("AFSocketObjectList", "Object List"),
            ("NodeSocketInt", "Element Index"),
        )
        output_mode = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
        output_socket_idname = GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE.get(output_mode, "NodeSocketFloat")
        output_specs = (
            (output_socket_idname, "Value"),
            ("AFSocketReport", "Report"),
        )
        _sync_node_sockets_in_place(node, input_specs, output_specs)
        element_index_socket = node.inputs.get("Element Index")
        if element_index_socket is not None and hasattr(element_index_socket, "default_value"):
            try:
                element_index_socket.default_value = max(0, int(getattr(element_index_socket, "default_value", 0)))
            except Exception:
                pass

    def _sync_set_geometry_attribute_node_sockets(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in set_geometry_attribute_sync_guard:
            return
        set_geometry_attribute_sync_guard.add(node_key)
        try:
            value_mode = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
            value_socket_idname = GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE.get(value_mode, "NodeSocketFloat")
            input_specs = (
                ("AFSocketFlow", "Flow In"),
                ("AFSocketObjectList", "Object List"),
                (value_socket_idname, "Value"),
            )
            output_specs = (
                ("AFSocketFlow", "Flow Out"),
                ("AFSocketReport", "Report"),
            )
            _sync_node_sockets_in_place(node, input_specs, output_specs)
        finally:
            set_geometry_attribute_sync_guard.discard(node_key)

    def _sync_publish_geometry_attribute_node_sockets(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in publish_geometry_attribute_sync_guard:
            return
        publish_geometry_attribute_sync_guard.add(node_key)
        try:
            value_mode = str(getattr(node, "value_type", "FLOAT") or "FLOAT")
            value_socket_idname = GEOMETRY_ATTRIBUTE_OUTPUT_SOCKET_BY_MODE.get(value_mode, "NodeSocketFloat")
            input_specs = (
                ("AFSocketFlow", "Flow In"),
                ("AFSocketObjectList", "Object List"),
                (value_socket_idname, "Value"),
            )
            output_specs = (
                ("AFSocketFlow", "Flow Out"),
                ("AFSocketObjectList", "Carrier Object"),
                ("AFSocketReport", "Report"),
            )
            _sync_node_sockets_in_place(node, input_specs, output_specs)
        finally:
            publish_geometry_attribute_sync_guard.discard(node_key)

    class AFNodePropertyContext(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePropertyContext"
        bl_label = "Property Context"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Prop Context")

        def init(self, context):
            del context
            self.outputs.new("AFSocketObjectList", "Object")
            self.outputs.new("NodeSocketInt", "Object Index")
            self.outputs.new("NodeSocketInt", "Object Count")
            self.outputs.new("NodeSocketInt", "Component Index")
            self.outputs.new("NodeSocketInt", "Component Count")
            self.outputs.new("NodeSocketBool", "Is Modifier")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _sync_property_context_sockets(self)

        def update(self):
            _sync_property_context_sockets(self)

    class AFNodeExtractPropertyAssignments(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeExtractPropertyAssignments"
        bl_label = "Extract Property Assignments"
        bl_description = "Extract Property Assignments from the input Property Package using current Property Context"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Extract Prop Assigns")

        def init(self, context):
            del context
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self)
            _set_node_color(self, "GEOMETRY")

    class AFNodeSampleContextData(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSampleContextData"
        bl_label = "Sample Context Data"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self._sync_sockets()
            _set_default_node_width(self)
            _set_node_color(self, "GEOMETRY")

        def _sync_sockets(self):
            _sync_sample_context_data_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeReduceContextValue(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeReduceContextValue"
        bl_label = "Reduce Context Value"
        bl_icon = "BLANK1"

        value_type: bpy.props.EnumProperty(
            name="Type",
            items=CONTEXT_REDUCE_VALUE_TYPE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )
        operation: bpy.props.EnumProperty(
            name="Operation",
            items=CONTEXT_REDUCE_OPERATION_ITEMS,
            default="AVERAGE",
        )
        vector_mode: bpy.props.EnumProperty(
            name="Vector Mode",
            items=CONTEXT_REDUCE_VECTOR_MODE_ITEMS,
            default="COMPONENTS",
        )

        def init(self, context):
            del context
            self._sync_sockets()
            _set_default_node_width(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "value_type", text="")
            layout.prop(self, "operation", text="")
            if str(getattr(self, "value_type", "FLOAT") or "FLOAT") == "VECTOR" and str(getattr(self, "operation", "AVERAGE") or "AVERAGE") in {"MINIMUM", "MAXIMUM"}:
                layout.prop(self, "vector_mode", text="")

        def _sync_sockets(self):
            _sync_context_reduce_value_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeReadGeometryAttribute(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeReadGeometryAttribute"
        bl_label = "Read Geometry Attribute"
        bl_icon = "BLANK1"

        target_object: bpy.props.PointerProperty(type=bpy.types.Object)
        attribute_name: bpy.props.StringProperty(name="Attribute Name", default="")
        value_type: bpy.props.EnumProperty(
            name="Value Type",
            items=GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            del context
            self._sync_sockets()
            _set_default_node_width(self)
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_object", text="Object")
            layout.prop(self, "attribute_name", text="Attribute")
            layout.prop(self, "value_type", text="")

        def _sync_sockets(self):
            _sync_geometry_attribute_node_sockets(self)
            _hide_default_auxiliary_outputs(self)

        def update(self):
            self._sync_sockets()

    class AFNodeSetGeometryAttribute(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSetGeometryAttribute"
        bl_label = "Set Geometry Attribute"
        bl_icon = "BLANK1"

        target_object: bpy.props.PointerProperty(type=bpy.types.Object)
        attribute_name: bpy.props.StringProperty(name="Attribute Name", default="")
        value_type: bpy.props.EnumProperty(
            name="Value Type",
            items=GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            del context
            self._sync_sockets()
            _set_default_node_width(self)
            _set_node_color(self, "GEOMETRY")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_object", text="Target Object")
            layout.prop(self, "attribute_name", text="Attribute")
            layout.prop(self, "value_type", text="")

        def _sync_sockets(self):
            _sync_set_geometry_attribute_node_sockets(self)
            _hide_default_auxiliary_outputs(self)

        def update(self):
            self._sync_sockets()

    class AFNodePublishGeometryAttribute(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePublishGeometryAttribute"
        bl_label = "Publish Geometry Attribute"
        bl_icon = "BLANK1"

        carrier_object: bpy.props.PointerProperty(type=bpy.types.Object)
        attribute_name: bpy.props.StringProperty(name="Attribute Name", default="")
        index_attribute_name: bpy.props.StringProperty(name="Index Attribute Name", default="af_source_index")
        value_type: bpy.props.EnumProperty(
            name="Value Type",
            items=GEOMETRY_ATTRIBUTE_VALUE_TYPE_ITEMS,
            default="FLOAT",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            del context
            self._sync_sockets()
            _set_default_node_width(self)
            _set_node_color(self, "GEOMETRY")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "carrier_object", text="Carrier Object")
            layout.prop(self, "attribute_name", text="Attribute")
            layout.prop(self, "index_attribute_name", text="Index Attribute")
            layout.prop(self, "value_type", text="")

        def _sync_sockets(self):
            _sync_publish_geometry_attribute_node_sockets(self)
            _hide_default_auxiliary_outputs(self)

        def update(self):
            self._sync_sockets()

    return {
        "_sync_property_context_sockets": _sync_property_context_sockets,
        "_sync_sample_context_data_sockets": _sync_sample_context_data_sockets,
        "_sync_context_reduce_value_sockets": _sync_context_reduce_value_sockets,
        "_sync_geometry_attribute_node_sockets": _sync_geometry_attribute_node_sockets,
        "_sync_set_geometry_attribute_node_sockets": _sync_set_geometry_attribute_node_sockets,
        "_sync_publish_geometry_attribute_node_sockets": _sync_publish_geometry_attribute_node_sockets,
        "AFNodePropertyContext": AFNodePropertyContext,
        "AFNodeExtractPropertyAssignments": AFNodeExtractPropertyAssignments,
        "AFNodeSampleContextData": AFNodeSampleContextData,
        "AFNodeReduceContextValue": AFNodeReduceContextValue,
        "AFNodeReadGeometryAttribute": AFNodeReadGeometryAttribute,
        "AFNodeSetGeometryAttribute": AFNodeSetGeometryAttribute,
        "AFNodePublishGeometryAttribute": AFNodePublishGeometryAttribute,
    }
