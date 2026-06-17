import bpy

from ..i18n import af_iface, af_status_label


def build_display_helpers(
    *,
    PROPERTY_SOURCE_CURRENT,
    PROPERTY_SOURCE_VALUE,
):
    def _use_chinese_ui():
        try:
            language = str(getattr(getattr(bpy.context, "preferences", None), "view", None).language or "")
        except Exception:
            language = ""
        return language.startswith("zh")

    def _status_value_display_label(identifier):
        return af_status_label(identifier)

    def _camera_object_poll(self, obj):
        del self
        return obj is None or getattr(obj, "type", "") == "CAMERA"

    def _set_node_color(node, _color_tag):
        node.use_custom_color = False

    def _enum_property_label(node, property_name, fallback):
        rna = getattr(node, "bl_rna", None)
        if rna is None:
            return fallback
        try:
            prop = rna.properties[property_name]
        except Exception:
            return fallback

        current_value = str(getattr(node, property_name, "") or "")
        for item in getattr(prop, "enum_items", []):
            if str(getattr(item, "identifier", "") or "") != current_value:
                continue
            label = str(getattr(item, "name", "") or "").strip()
            return af_iface(label) if label else fallback
        return fallback

    def _enum_identifier_label(items, identifier):
        identifier = str(identifier or "")
        for item_identifier, item_name, _item_description in items:
            if str(item_identifier or "") != identifier:
                continue
            label = str(item_name or "").strip()
            return label if label else identifier
        return identifier or "-"

    def _hide_auxiliary_output_socket(socket):
        socket_type = str(getattr(socket, "bl_idname", "") or "")
        socket_name = str(getattr(socket, "name", "") or "")
        if socket_type == "AFSocketReport":
            pass
        elif socket_type in {"AFSocketString", "NodeSocketString"} and socket_name == "Status":
            pass
        else:
            return
        try:
            socket.hide = True
        except Exception:
            pass

    def _hide_default_auxiliary_outputs(node):
        for socket in getattr(node, "outputs", []):
            _hide_auxiliary_output_socket(socket)

    def _draw_compact_property_source(row, node, source_attr, enabled=True):
        source_row = row.row(align=True)
        source_row.enabled = bool(enabled)
        source_row.scale_x = 0.72
        source_row.prop_enum(node, source_attr, PROPERTY_SOURCE_VALUE, text="V")
        source_row.prop_enum(node, source_attr, PROPERTY_SOURCE_CURRENT, text="C")
        return source_row

    def _set_default_node_width(node, multiplier=1.0, base_width=140.0):
        try:
            node.width = float(base_width) * float(multiplier)
        except Exception:
            pass

    return {
        "_use_chinese_ui": _use_chinese_ui,
        "_status_value_display_label": _status_value_display_label,
        "_camera_object_poll": _camera_object_poll,
        "_set_node_color": _set_node_color,
        "_enum_property_label": _enum_property_label,
        "_enum_identifier_label": _enum_identifier_label,
        "_hide_auxiliary_output_socket": _hide_auxiliary_output_socket,
        "_hide_default_auxiliary_outputs": _hide_default_auxiliary_outputs,
        "_draw_compact_property_source": _draw_compact_property_source,
        "_set_default_node_width": _set_default_node_width,
    }


__all__ = ["build_display_helpers"]
