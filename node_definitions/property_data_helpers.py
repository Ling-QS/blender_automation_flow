import json

from bpy.app.translations import pgettext_iface as iface_

from ..node_system.socket_aliases import (
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    canonical_socket_display_name,
)

def build_property_data_helpers(
    *,
    CUSTOM_MENU_SOCKET_IDNAMES,
    PROPERTY_DATA_FIELD_SPECS,
    PROPERTY_SOURCE_VALUE,
    _draw_compact_property_source,
    _find_single_from_input_socket,
    _rebuild_sockets,
    _socket_signature,
):
    def _draw_modifier_property_assignment_fields(layout, node, heading_text):
        del heading_text
        name_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Name")
        filter_row = layout.row(align=True)
        filter_row.prop(node, "filter_by_type", text=iface_("Type"), toggle=True)
        filter_row.prop(node, "filter_by_name", text=iface_("Name"), toggle=True)
        filter_row.prop(node, "filter_by_context", text=iface_("Context"), toggle=True)
        if bool(getattr(node, "filter_by_type", False)):
            layout.prop(node, "modifier_type_filter", text="")
        if bool(getattr(node, "filter_by_name", False)):
            row = layout.row(align=True)
            split = row.split(factor=0.34, align=True)
            mode_row = split.row(align=True)
            mode_row.prop(node, "modifier_name_match_mode", text="")
            value_row = split.row(align=True)
            if name_socket is not None and hasattr(name_socket, "default_value"):
                value_row.enabled = _find_single_from_input_socket(name_socket)[0] is None
                value_row.prop(name_socket, "default_value", text="")
            else:
                value_row.label(text="")

    def _draw_object_display_property_assignment_fields(layout, node, heading_text):
        del layout, node, heading_text

    def _draw_object_transform_property_assignment_fields(layout, node, heading_text):
        del layout, node, heading_text

    def _draw_rotation_value_inputs(layout, node, rotation_mode_attr, euler_attr, quaternion_attr, axis_angle_attr):
        rotation_mode = str(getattr(node, rotation_mode_attr, "XYZ") or "XYZ")
        if rotation_mode == "QUATERNION":
            col = layout.column(align=True)
            col.prop(node, quaternion_attr, index=0, text="W")
            col.prop(node, quaternion_attr, index=1, text="X")
            col.prop(node, quaternion_attr, index=2, text="Y")
            col.prop(node, quaternion_attr, index=3, text="Z")
            return
        if rotation_mode == "AXIS_ANGLE":
            col = layout.column(align=True)
            col.prop(node, axis_angle_attr, index=0, text="Angle")
            col.prop(node, axis_angle_attr, index=1, text="Axis X")
            col.prop(node, axis_angle_attr, index=2, text="Axis Y")
            col.prop(node, axis_angle_attr, index=3, text="Axis Z")
            return
        col = layout.column(align=True)
        col.prop(node, euler_attr, index=0, text="X")
        col.prop(node, euler_attr, index=1, text="Y")
        col.prop(node, euler_attr, index=2, text="Z")

    def _property_data_field_specs(node_or_type):
        node_type = str(node_or_type if isinstance(node_or_type, str) else getattr(node_or_type, "bl_idname", "") or "")
        return PROPERTY_DATA_FIELD_SPECS.get(node_type, ())

    def _property_data_field_spec_by_input_name(node, socket_name):
        socket_name = str(socket_name or "")
        for spec in _property_data_field_specs(node):
            if str(spec.get("input_socket", "") or "") == socket_name:
                return spec
        return None

    def _property_data_input_specs(node):
        input_specs = []
        if getattr(node, "bl_idname", "") == "AFNodeModifierPropertyData":
            if bool(getattr(node, "filter_by_name", False)):
                input_specs.append(("NodeSocketString", "Name"))
            if bool(getattr(node, "filter_by_context", False)):
                input_specs.append(("NodeSocketBool", "Context"))
        input_specs.extend(
            (str(spec["socket_idname"]), str(spec["input_socket"]))
            for spec in _property_data_field_specs(node)
            if str(spec.get("input_socket", "") or "").strip() and str(spec.get("socket_idname", "") or "").strip()
        )
        return tuple(input_specs)

    def _property_data_context_output_specs(node):
        output_specs = []
        if getattr(node, "bl_idname", "") == "AFNodeModifierPropertyData":
            output_specs.append(("NodeSocketString", "Name"))
        output_specs.extend(
            (str(spec["socket_idname"]), str(spec["output_socket"]))
            for spec in _property_data_field_specs(node)
            if bool(spec.get("supports_context", False))
            and str(spec.get("output_socket", "") or "").strip()
            and str(spec.get("socket_idname", "") or "").strip()
        )
        return tuple(output_specs)

    def _property_data_output_specs(node):
        output_specs = [("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME)]
        output_specs.extend(list(_property_data_context_output_specs(node)))
        output_specs.append(("AFSocketReport", "Report"))
        return tuple(output_specs)

    def _capture_socket_hidden_state(node):
        state = {}
        for socket in list(getattr(node, "inputs", [])) + list(getattr(node, "outputs", [])):
            try:
                key = (
                    str(getattr(socket, "is_output", False)),
                    canonical_socket_display_name(getattr(socket, "name", "")),
                )
                state[key] = {
                    "hide": bool(getattr(socket, "hide", False)),
                    "mode_hidden": bool(socket.get("af_property_data_mode_hidden", False)),
                }
            except Exception:
                continue
        return state

    property_data_manual_hidden_keys = "af_property_data_manual_hidden_keys"
    property_data_last_applied_hide_state = "af_property_data_last_applied_hide_state"

    def _property_data_socket_key(*, socket=None, is_output=False, socket_name=""):
        if socket is not None:
            is_output = bool(getattr(socket, "is_output", False))
            socket_name = canonical_socket_display_name(getattr(socket, "name", ""))
        direction = "OUTPUT" if bool(is_output) else "INPUT"
        return f"{direction}:{str(socket_name or '')}"

    def _load_property_data_manual_hidden_keys(node):
        try:
            raw_value = str(node.get(property_data_manual_hidden_keys, "") or "")
        except Exception:
            raw_value = ""
        if not raw_value:
            return set()
        try:
            decoded = json.loads(raw_value)
        except Exception:
            return set()
        if not isinstance(decoded, list):
            return set()
        return {str(item or "") for item in decoded if str(item or "").strip()}

    def _load_property_data_manual_hidden_state(node):
        hidden_state = {}
        for socket in list(getattr(node, "inputs", [])) + list(getattr(node, "outputs", [])):
            try:
                socket_key = _property_data_socket_key(socket=socket)
                hidden_state[socket_key] = bool(getattr(socket, "hide", False)) and not bool(socket.get("af_property_data_mode_hidden", False))
            except Exception:
                continue
        return hidden_state

    def _store_property_data_manual_hidden_keys(node, manual_hidden_keys):
        encoded = json.dumps(sorted({str(key or "") for key in manual_hidden_keys if str(key or "").strip()}))
        try:
            if encoded == "[]":
                if property_data_manual_hidden_keys in node:
                    del node[property_data_manual_hidden_keys]
                return
            node[property_data_manual_hidden_keys] = encoded
        except Exception:
            pass

    def _load_property_data_last_applied_hide_state(node):
        try:
            raw_value = str(node.get(property_data_last_applied_hide_state, "") or "")
        except Exception:
            raw_value = ""
        if not raw_value:
            return {}
        try:
            decoded = json.loads(raw_value)
        except Exception:
            return {}
        if not isinstance(decoded, dict):
            return {}
        return {str(key or ""): bool(value) for key, value in decoded.items() if str(key or "").strip()}

    def _store_property_data_last_applied_hide_state(node, hide_state):
        serialized = {
            str(key or ""): bool(value)
            for key, value in dict(hide_state or {}).items()
            if str(key or "").strip()
        }
        encoded = json.dumps(serialized, sort_keys=True)
        try:
            if encoded == "{}":
                if property_data_last_applied_hide_state in node:
                    del node[property_data_last_applied_hide_state]
                return
            node[property_data_last_applied_hide_state] = encoded
        except Exception:
            pass

    def _observe_property_data_manual_hidden_keys(node):
        stored_hidden = _load_property_data_manual_hidden_keys(node)
        last_applied_hide_state = _load_property_data_last_applied_hide_state(node)
        resolved = set(stored_hidden)
        for socket in list(getattr(node, "inputs", [])) + list(getattr(node, "outputs", [])):
            try:
                if bool(socket.get("af_property_data_mode_hidden", False)):
                    continue
                socket_key = _property_data_socket_key(socket=socket)
                current_hidden = bool(getattr(socket, "hide", False))
                last_hidden = last_applied_hide_state.get(socket_key, None)
                if last_hidden is None:
                    if current_hidden:
                        resolved.add(socket_key)
                    continue
                if current_hidden == bool(last_hidden):
                    continue
                if current_hidden:
                    resolved.add(socket_key)
                else:
                    resolved.discard(socket_key)
            except Exception:
                continue
        _store_property_data_manual_hidden_keys(node, resolved)
        return resolved

    def _persist_property_data_manual_hidden_keys(node):
        return _observe_property_data_manual_hidden_keys(node)

    def _resolve_property_data_manual_hidden_keys(node, manual_hidden_keys=None, observe_current=False):
        if manual_hidden_keys is not None:
            resolved = {str(key or "") for key in manual_hidden_keys if str(key or "").strip()}
            _store_property_data_manual_hidden_keys(node, resolved)
            return resolved

        if observe_current:
            return _observe_property_data_manual_hidden_keys(node)
        return _load_property_data_manual_hidden_keys(node)

    def _socket_manual_hidden(previous_hidden_state, socket, forced_hidden):
        key = (
            str(getattr(socket, "is_output", False)),
            canonical_socket_display_name(getattr(socket, "name", "")),
        )
        previous_state = dict(previous_hidden_state.get(key, {}) or {})
        previous_hidden = bool(previous_state.get("hide", False))
        previous_mode_hidden = bool(previous_state.get("mode_hidden", False))
        return bool(previous_hidden and not previous_mode_hidden and not forced_hidden)

    def _apply_property_data_socket_visibility(node, manual_hidden_keys=None):
        previous_hidden_state = _capture_socket_hidden_state(node)
        manual_hidden_keys = _resolve_property_data_manual_hidden_keys(node, manual_hidden_keys)
        previous_manual_hidden_state = _load_property_data_manual_hidden_state(node)
        last_applied_hide_state = _load_property_data_last_applied_hide_state(node)
        output_mode = str(getattr(node, "output_mode", "ASSIGNMENT") or "ASSIGNMENT")
        visible_manual_hidden = set()
        applied_hide_state = {}
        default_hidden_output_names = {"Report"}
        always_visible_context_input_names = set()
        if str(getattr(node, "bl_idname", "") or "") == "AFNodeModifierPropertyData":
            if bool(getattr(node, "filter_by_name", False)):
                always_visible_context_input_names.add("Name")
            if bool(getattr(node, "filter_by_context", False)):
                always_visible_context_input_names.add("Context")
        for socket in getattr(node, "inputs", []):
            try:
                socket_name = str(getattr(socket, "name", "") or "")
                forced_hidden = output_mode == "CONTEXT" and socket_name not in always_visible_context_input_names
                socket_key = _property_data_socket_key(socket=socket)
                manual_hidden = (
                    bool(socket_key in manual_hidden_keys)
                    or bool(previous_manual_hidden_state.get(socket_key, False))
                    or _socket_manual_hidden(previous_hidden_state, socket, forced_hidden)
                )
                if manual_hidden and not forced_hidden:
                    visible_manual_hidden.add(socket_key)
                socket.hide = bool(forced_hidden or manual_hidden)
                socket["af_property_data_mode_hidden"] = bool(forced_hidden)
                if not forced_hidden:
                    applied_hide_state[socket_key] = bool(manual_hidden)
            except Exception:
                pass
        context_output_names = {
            str(spec["output_socket"])
            for spec in _property_data_field_specs(node)
            if bool(spec.get("supports_context", False))
        }
        if str(getattr(node, "bl_idname", "") or "") == "AFNodeModifierPropertyData":
            context_output_names.add("Name")
        for socket in getattr(node, "outputs", []):
            socket_name = str(getattr(socket, "name", "") or "")
            try:
                forced_hidden = False
                if socket_name == PROPERTY_ASSIGNMENT_SOCKET_NAME:
                    forced_hidden = output_mode == "CONTEXT"
                elif socket_name in context_output_names:
                    forced_hidden = output_mode != "CONTEXT"
                socket_key = _property_data_socket_key(socket=socket)
                default_manual_hidden = bool(
                    socket_name in default_hidden_output_names
                    and socket_key not in manual_hidden_keys
                    and socket_key not in previous_manual_hidden_state
                    and socket_key not in last_applied_hide_state
                )
                manual_hidden = (
                    default_manual_hidden
                    or bool(socket_key in manual_hidden_keys)
                    or bool(previous_manual_hidden_state.get(socket_key, False))
                    or _socket_manual_hidden(previous_hidden_state, socket, forced_hidden)
                )
                if manual_hidden and not forced_hidden:
                    visible_manual_hidden.add(socket_key)
                socket.hide = bool(forced_hidden or manual_hidden)
                socket["af_property_data_mode_hidden"] = bool(forced_hidden)
                if not forced_hidden:
                    applied_hide_state[socket_key] = bool(manual_hidden)
            except Exception:
                pass
        _store_property_data_manual_hidden_keys(node, visible_manual_hidden)
        _store_property_data_last_applied_hide_state(node, applied_hide_state)

    def _refresh_property_data_socket_visibility(node):
        if getattr(node, "bl_idname", "") not in PROPERTY_DATA_FIELD_SPECS:
            return
        try:
            manual_hidden_keys = _load_property_data_manual_hidden_keys(node)
            _apply_property_data_socket_visibility(node, manual_hidden_keys=manual_hidden_keys)
        except Exception:
            pass

    def _sync_property_data_node_sockets(node, manual_hidden_keys=None):
        manual_hidden_keys = _resolve_property_data_manual_hidden_keys(node, manual_hidden_keys)
        input_specs = _property_data_input_specs(node)
        output_specs = _property_data_output_specs(node)
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature != input_specs or output_signature != output_specs:
            _rebuild_sockets(node, input_specs, output_specs)
        if getattr(node, "bl_idname", "") == "AFNodeModifierPropertyData":
            name_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Name")
            if name_socket is not None:
                try:
                    name_socket.hide_value = True
                except Exception:
                    pass
            context_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Context")
            if context_socket is not None:
                try:
                    context_socket.default_value = True
                    context_socket.hide_value = True
                except Exception:
                    pass
        _apply_property_data_socket_visibility(node, manual_hidden_keys=manual_hidden_keys)

    _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS = (
        ("AFSocketVectorValue", "Location"),
        ("AFSocketRotationValue", "Rotation"),
        ("AFSocketRotationMode", "Rotation Mode"),
        ("AFSocketVectorValue", "Scale"),
    )

    def _initialize_object_transform_property_input_defaults(node):
        if bool(getattr(node, "transform_inputs_initialized", False)):
            return
        scale_socket = getattr(node, "inputs", None)
        scale_socket = scale_socket.get("Scale") if scale_socket is not None else None
        initialized = False
        if scale_socket is not None and hasattr(scale_socket, "default_value"):
            try:
                current_scale = tuple(float(value) for value in getattr(scale_socket, "default_value", (0.0, 0.0, 0.0)))
                target_scale = tuple(float(value) for value in getattr(node, "target_scale", (1.0, 1.0, 1.0)))
                if len(current_scale) < 3 or all(abs(float(value)) <= 1e-8 for value in current_scale[:3]):
                    scale_socket.default_value = target_scale[:3]
                initialized = True
            except Exception:
                pass
        if initialized:
            try:
                node.transform_inputs_initialized = True
            except Exception:
                pass

    def _sync_object_transform_property_data_sockets(node, manual_hidden_keys=None):
        manual_hidden_keys = _resolve_property_data_manual_hidden_keys(node, manual_hidden_keys)
        input_specs = _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS
        output_specs = _property_data_output_specs(node)
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature != input_specs or output_signature != output_specs:
            _rebuild_sockets(node, input_specs, output_specs, include_default_values=False)
        _initialize_object_transform_property_input_defaults(node)
        _apply_property_data_socket_visibility(node, manual_hidden_keys=manual_hidden_keys)

    def _property_data_update_socket_layout(self, _context):
        if getattr(self, "bl_idname", "") not in PROPERTY_DATA_FIELD_SPECS:
            return
        manual_hidden_keys = _resolve_property_data_manual_hidden_keys(self, observe_current=True)
        if getattr(self, "bl_idname", "") == "AFNodeObjectTransformPropertyData":
            _sync_object_transform_property_data_sockets(self, manual_hidden_keys=manual_hidden_keys)
            return
        _sync_property_data_node_sockets(self, manual_hidden_keys=manual_hidden_keys)

    def _draw_property_data_input_socket(socket, layout, node, text):
        if bool(getattr(socket, "is_output", False)):
            return False
        if bool(getattr(socket, "hide", False)):
            return False
        socket_name = str(getattr(socket, "name", "") or "")
        spec = _property_data_field_spec_by_input_name(node, socket_name)
        if spec is None and text:
            spec = _property_data_field_spec_by_input_name(node, text)
        if spec is None:
            return False

        enabled_attr = str(spec["capture_attr"])
        source_attr = str(spec["source_attr"])
        label_text = str(spec["label"])
        target_attr = str(spec.get("target_attr", "") or "")
        is_enabled = bool(getattr(node, enabled_attr, False))
        source_mode = str(getattr(node, source_attr, PROPERTY_SOURCE_VALUE) or PROPERTY_SOURCE_VALUE)
        socket_type = str(getattr(socket, "bl_idname", "") or "")
        show_value_input = bool(is_enabled) and source_mode == PROPERTY_SOURCE_VALUE and not bool(getattr(socket, "is_linked", False))

        col = None
        if socket_type in {"AFSocketVectorValue", "NodeSocketVector", "NodeSocketRotation", "AFSocketRotationValue"} or socket_type in CUSTOM_MENU_SOCKET_IDNAMES:
            col = layout.column(align=True)
            row = col.row(align=True)
        else:
            row = layout.row(align=True)
        row.prop(node, enabled_attr, text=label_text)

        if socket_type in {"AFSocketVectorValue", "NodeSocketVector"}:
            _draw_compact_property_source(row, node, source_attr, enabled=is_enabled)
            if show_value_input:
                value_col = col.column(align=True)
                value_col.enabled = is_enabled
                if target_attr:
                    value_col.prop(node, target_attr, index=0, text="X")
                    value_col.prop(node, target_attr, index=1, text="Y")
                    value_col.prop(node, target_attr, index=2, text="Z")
                else:
                    value_col.prop(socket, "default_value", index=0, text="X")
                    value_col.prop(socket, "default_value", index=1, text="Y")
                    value_col.prop(socket, "default_value", index=2, text="Z")
            return True

        if socket_type in {"NodeSocketRotation", "AFSocketRotationValue"}:
            _draw_compact_property_source(row, node, source_attr, enabled=is_enabled)
            if show_value_input:
                value_col = col.column(align=True)
                value_col.enabled = is_enabled
                _draw_rotation_value_inputs(
                    value_col,
                    node,
                    "target_rotation_mode",
                    "target_rotation_euler",
                    "target_rotation_quaternion",
                    "target_rotation_axis_angle",
                )
            return True

        if socket_type in CUSTOM_MENU_SOCKET_IDNAMES:
            _draw_compact_property_source(row, node, source_attr, enabled=is_enabled)
            if show_value_input and target_attr:
                value_row = col.row(align=True)
                value_row.enabled = is_enabled
                value_row.prop(node, target_attr, text="")
            return True

        if show_value_input:
            value_row = row.row(align=True)
            value_row.enabled = is_enabled
            value_row.prop(socket, "default_value", text="")
        _draw_compact_property_source(row, node, source_attr, enabled=is_enabled)
        return True

    def _modifier_property_definition_from_node(node):
        modifier_name_socket = getattr(getattr(node, "inputs", None), "get", lambda _name: None)("Name")
        filter_by_type = bool(getattr(node, "filter_by_type", False))
        filter_by_name = bool(getattr(node, "filter_by_name", False))
        filter_by_context = bool(getattr(node, "filter_by_context", False))
        modifier_name_filter = str(getattr(modifier_name_socket, "default_value", "") or "").strip() if filter_by_name and modifier_name_socket is not None else ""
        return {
            "definition_kind": "MODIFIER",
            "scope_kind": "MODIFIER",
            "source_node": str(getattr(node, "name", "") or ""),
            "properties": {
                "show_viewport": bool(getattr(node, "capture_show_viewport", False)),
                "show_render": bool(getattr(node, "capture_show_render", False)),
                "show_in_editmode": bool(getattr(node, "capture_show_in_editmode", False)),
            },
            "metadata": {
                "filter_by_type": filter_by_type,
                "filter_by_name": filter_by_name,
                "filter_by_context": filter_by_context,
                "modifier_type_filter": str(getattr(node, "modifier_type_filter", "ALL") or "ALL") if filter_by_type else "ALL",
                "modifier_name_filter": modifier_name_filter,
                "modifier_name_match_mode": str(getattr(node, "modifier_name_match_mode", "EXACT") or "EXACT"),
            },
        }

    def _object_display_property_definition_from_node(node):
        return {
            "definition_kind": "OBJECT_DISPLAY",
            "scope_kind": "OBJECT",
            "source_node": str(getattr(node, "name", "") or ""),
            "properties": {
                "hide_viewport": bool(getattr(node, "capture_hide_viewport", False)),
                "hide_render": bool(getattr(node, "capture_hide_render", False)),
                "show_in_front": bool(getattr(node, "capture_show_in_front", False)),
                "show_name": bool(getattr(node, "capture_show_name", False)),
                "show_axis": bool(getattr(node, "capture_show_axis", False)),
                "display_type": bool(getattr(node, "capture_display_type", False)),
            },
            "metadata": {},
        }

    def _object_transform_property_definition_from_node(node):
        return {
            "definition_kind": "OBJECT_TRANSFORM",
            "scope_kind": "OBJECT",
            "source_node": str(getattr(node, "name", "") or ""),
            "properties": {
                "location": bool(getattr(node, "capture_location", False)),
                "rotation": bool(getattr(node, "capture_rotation", False)),
                "scale": bool(getattr(node, "capture_scale", False)),
                "rotation_mode": bool(getattr(node, "capture_rotation_mode", False)),
            },
            "metadata": {},
        }

    return {
        "_OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS": _OBJECT_TRANSFORM_PROPERTY_INPUT_SPECS,
        "_apply_property_data_socket_visibility": _apply_property_data_socket_visibility,
        "_draw_modifier_property_assignment_fields": _draw_modifier_property_assignment_fields,
        "_draw_object_display_property_assignment_fields": _draw_object_display_property_assignment_fields,
        "_draw_object_transform_property_assignment_fields": _draw_object_transform_property_assignment_fields,
        "_draw_property_data_input_socket": _draw_property_data_input_socket,
        "_draw_rotation_value_inputs": _draw_rotation_value_inputs,
        "_initialize_object_transform_property_input_defaults": _initialize_object_transform_property_input_defaults,
        "_modifier_property_definition_from_node": _modifier_property_definition_from_node,
        "_object_display_property_definition_from_node": _object_display_property_definition_from_node,
        "_object_transform_property_definition_from_node": _object_transform_property_definition_from_node,
        "_persist_property_data_manual_hidden_keys": _persist_property_data_manual_hidden_keys,
        "_property_data_field_specs": _property_data_field_specs,
        "_property_data_input_specs": _property_data_input_specs,
        "_property_data_output_specs": _property_data_output_specs,
        "_property_data_socket_key": _property_data_socket_key,
        "_property_data_update_socket_layout": _property_data_update_socket_layout,
        "_refresh_property_data_socket_visibility": _refresh_property_data_socket_visibility,
        "_resolve_property_data_manual_hidden_keys": _resolve_property_data_manual_hidden_keys,
        "_sync_object_transform_property_data_sockets": _sync_object_transform_property_data_sockets,
        "_sync_property_data_node_sockets": _sync_property_data_node_sockets,
    }
