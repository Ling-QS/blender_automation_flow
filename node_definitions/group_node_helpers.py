import json

import bpy


def build_group_node_helpers(
    *,
    AFNodeTree,
    GROUP_NODE_INPUT_IDENTIFIERS_KEY,
    GROUP_NODE_OUTPUT_IDENTIFIERS_KEY,
    GROUP_SUPPORTED_SOCKET_IDNAMES,
    NUMERIC_COMPATIBLE_SOCKET_IDNAMES,
):
    def _tag_all_af_node_editor_redraw():
        wm = getattr(bpy.context, "window_manager", None)
        if wm is None:
            return
        for window in getattr(wm, "windows", []):
            screen = getattr(window, "screen", None)
            if screen is None:
                continue
            for area in getattr(screen, "areas", []):
                if getattr(area, "type", "") != "NODE_EDITOR":
                    continue
                area.tag_redraw()

    def _builtin_socket_family(socket_type):
        socket_type = str(socket_type or "")
        if not socket_type:
            return ""
        for prefix, family in (
            ("NodeSocketBool", "NodeSocketBool"),
            ("NodeSocketInt", "NodeSocketInt"),
            ("NodeSocketFloat", "NodeSocketFloat"),
            ("NodeSocketVector", "NodeSocketVector"),
            ("NodeSocketString", "NodeSocketString"),
            ("NodeSocketRotation", "NodeSocketRotation"),
            ("NodeSocketMatrix", "NodeSocketMatrix"),
        ):
            if socket_type == prefix or socket_type.startswith(prefix):
                return family
        return ""

    def _numeric_socket_family(socket_type):
        socket_type = str(socket_type or "")
        if socket_type in NUMERIC_COMPATIBLE_SOCKET_IDNAMES:
            return {
                "NodeSocketBool": "NodeSocketBool",
                "NodeSocketInt": "NodeSocketInt",
                "NodeSocketFloat": "NodeSocketFloat",
                "NodeSocketVector": "NodeSocketVector",
                "AFSocketBooleanValue": "NodeSocketBool",
                "AFSocketIntegerValue": "NodeSocketInt",
                "AFSocketFloatValue": "NodeSocketFloat",
                "AFSocketVectorValue": "NodeSocketVector",
            }.get(socket_type, "")
        family = _builtin_socket_family(socket_type)
        if family in {"NodeSocketBool", "NodeSocketInt", "NodeSocketFloat", "NodeSocketVector"}:
            return family
        return ""

    def _string_socket_family(socket_type):
        socket_type = str(socket_type or "")
        if socket_type == "AFSocketString":
            return "NodeSocketString"
        family = _builtin_socket_family(socket_type)
        if family == "NodeSocketString":
            return family
        return ""

    def _is_supported_group_socket_type(socket_type):
        socket_type = str(socket_type or "")
        if not socket_type:
            return False
        if socket_type in GROUP_SUPPORTED_SOCKET_IDNAMES:
            return True
        return _builtin_socket_family(socket_type) in {
            "NodeSocketBool",
            "NodeSocketInt",
            "NodeSocketFloat",
            "NodeSocketVector",
            "NodeSocketString",
            "NodeSocketRotation",
            "NodeSocketMatrix",
        }

    def _group_socket_spec_hide_value_supported(socket_type):
        socket_type = str(socket_type or "")
        if socket_type in {
            "AFSocketFlow",
            "AFSocketCollectionList",
            "AFSocketObjectList",
            "AFSocketPropertyPackage",
            "AFSocketPropertyDefinition",
            "AFSocketPropertyAssignment",
            "AFSocketTaskRef",
            "AFSocketTaskPlan",
            "AFSocketTaskHandle",
            "AFSocketReport",
        }:
            return False
        if socket_type in {
            "AFSocketDisplayType",
            "AFSocketObjectInteractionMode",
            "AFSocketRotationMode",
            "AFSocketViewportShadingMode",
        }:
            return True
        family = _builtin_socket_family(socket_type) or _string_socket_family(socket_type)
        return family in {
            "NodeSocketBool",
            "NodeSocketInt",
            "NodeSocketFloat",
            "NodeSocketVector",
            "NodeSocketString",
            "NodeSocketRotation",
        }

    def _iter_group_interface_sockets(node_tree, in_out):
        if node_tree is None:
            return []
        items = []
        for item in node_tree.interface.items_tree:
            if getattr(item, "item_type", "") != "SOCKET":
                continue
            if getattr(item, "in_out", "") != in_out:
                continue
            socket_type = _group_interface_socket_type(item)
            if not _is_supported_group_socket_type(socket_type):
                continue
            items.append(item)
        items.sort(key=lambda item: int(getattr(item, "position", 0)))
        return items

    def _group_interface_socket_type(item):
        candidates = (
            str(getattr(item, "bl_socket_idname", "") or ""),
            str(getattr(item, "socket_type", "") or ""),
        )
        for socket_type in candidates:
            if _is_supported_group_socket_type(socket_type):
                return socket_type
        return candidates[0] or candidates[1]

    def _is_custom_group_socket_type(socket_type):
        return str(socket_type).startswith("AFSocket")

    def _sanitize_group_node_socket_specs(group_tree, direction, specs):
        del group_tree
        if not specs:
            return []

        sanitized = []
        seen_identifiers = set()
        for spec in specs:
            item = dict(spec)
            identifier = str(item["identifier"] or "")
            if not identifier or identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)
            sanitized.append(item)

        sanitized.sort(key=lambda item: int(item["position"]))
        return sanitized

    def _build_group_node_socket_specs(group_tree, direction):
        interface_items = _iter_group_interface_sockets(group_tree, direction)
        specs = [
            _build_group_node_socket_spec(item, direction, index)
            for index, item in enumerate(interface_items)
        ]
        return _sanitize_group_node_socket_specs(group_tree, direction, specs)

    def _build_group_node_socket_spec(item, direction, index):
        socket_type = _group_interface_socket_type(item)
        spec = {
            "identifier": str(getattr(item, "identifier", f"{direction}_{index}")),
            "socket_type": socket_type,
            "name": str(item.name),
            "position": int(getattr(item, "position", index)),
            "has_default_value": False,
            "default_value": None,
            "description": str(getattr(item, "description", "") or ""),
            "optional_label": bool(getattr(item, "optional_label", False)),
            "hide_value": None,
            "min_value": None,
            "max_value": None,
        }
        if str(direction) != "INPUT":
            return spec

        if hasattr(item, "default_value"):
            try:
                spec["default_value"] = _copy_socket_default_value(getattr(item, "default_value"))
                spec["has_default_value"] = True
            except Exception:
                spec["default_value"] = None
                spec["has_default_value"] = False

        if _group_socket_spec_hide_value_supported(socket_type) and hasattr(item, "hide_value"):
            try:
                spec["hide_value"] = bool(getattr(item, "hide_value", False))
            except Exception:
                spec["hide_value"] = None

        for prop_name in ("min_value", "max_value"):
            if not hasattr(item, prop_name):
                continue
            try:
                spec[prop_name] = _copy_socket_default_value(getattr(item, prop_name))
            except Exception:
                spec[prop_name] = None
        return spec

    def _group_node_expected_socket_signature(group_tree, direction):
        specs = _build_group_node_socket_specs(group_tree, direction)
        return [(str(spec["name"]), str(spec["socket_type"])) for spec in specs]

    def _group_node_current_socket_signature(node, direction):
        sockets = node.inputs if direction == "INPUT" else node.outputs
        return [(str(socket.name), str(socket.bl_idname)) for socket in sockets]

    def _group_node_socket_signatures_match(node):
        group_tree = getattr(node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != AFNodeTree.bl_idname:
            return len(node.inputs) == 0 and len(node.outputs) == 0
        return (
            _group_node_current_socket_signature(node, "INPUT") == _group_node_expected_socket_signature(group_tree, "INPUT")
            and _group_node_current_socket_signature(node, "OUTPUT") == _group_node_expected_socket_signature(group_tree, "OUTPUT")
        )

    def _group_node_identifier_key(direction):
        return GROUP_NODE_INPUT_IDENTIFIERS_KEY if direction == "INPUT" else GROUP_NODE_OUTPUT_IDENTIFIERS_KEY

    def _decode_group_node_identifiers(node, direction):
        raw = str(node.get(_group_node_identifier_key(direction), "") or "").strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except Exception:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _encode_group_node_identifiers(node, direction, identifiers):
        try:
            node[_group_node_identifier_key(direction)] = json.dumps([str(item) for item in identifiers], ensure_ascii=True)
        except Exception:
            pass

    def _copy_socket_default_value(value):
        if isinstance(value, (str, bytes, int, float, bool)) or value is None:
            return value
        try:
            materialized = tuple(_copy_socket_default_value(component) for component in value)
            return materialized
        except Exception:
            pass
        if hasattr(value, "copy"):
            try:
                return value.copy()
            except Exception:
                return value
        return value

    def _describe_socket_reference(socket):
        if socket is None:
            return None
        node = getattr(socket, "node", None)
        if node is None:
            return None
        is_output = bool(getattr(socket, "is_output", False))
        sockets = getattr(node, "outputs" if is_output else "inputs", [])
        socket_index = -1
        try:
            socket_index = list(sockets).index(socket)
        except Exception:
            socket_index = -1
        return {
            "node_name": str(getattr(node, "name", "") or ""),
            "socket_name": str(getattr(socket, "name", "") or ""),
            "socket_type": str(getattr(socket, "bl_idname", "") or ""),
            "is_output": is_output,
            "socket_index": int(socket_index),
        }

    def _resolve_socket_reference(node_tree, socket_ref):
        if node_tree is None or not isinstance(socket_ref, dict):
            return None
        node_name = str(socket_ref.get("node_name", "") or "")
        if not node_name:
            return None
        node = getattr(node_tree, "nodes", {}).get(node_name)
        if node is None:
            return None
        is_output = bool(socket_ref.get("is_output", False))
        sockets = list(getattr(node, "outputs" if is_output else "inputs", []))
        socket_index = int(socket_ref.get("socket_index", -1) or -1)
        socket_name = str(socket_ref.get("socket_name", "") or "")
        socket_type = str(socket_ref.get("socket_type", "") or "")
        if 0 <= socket_index < len(sockets):
            candidate = sockets[socket_index]
            if (
                str(getattr(candidate, "name", "") or "") == socket_name
                and str(getattr(candidate, "bl_idname", "") or "") == socket_type
            ):
                return candidate
        for candidate in sockets:
            if (
                str(getattr(candidate, "name", "") or "") == socket_name
                and str(getattr(candidate, "bl_idname", "") or "") == socket_type
            ):
                return candidate
        for candidate in sockets:
            if str(getattr(candidate, "name", "") or "") == socket_name:
                return candidate
        return None

    def _capture_dynamic_socket_state(node, direction, include_default_values=True):
        sockets = node.inputs if direction == "INPUT" else node.outputs
        state = []
        for index, socket in enumerate(sockets):
            socket_state = {
                "index": int(index),
                "socket_type": str(getattr(socket, "bl_idname", "") or ""),
                "name": str(getattr(socket, "name", "") or ""),
                "links": [],
                "default_value": None,
                "hide": bool(getattr(socket, "hide", False)),
            }
            if direction == "INPUT":
                socket_state["links"].extend(
                    [
                        _describe_socket_reference(getattr(link, "from_socket", None))
                        for link in socket.links
                        if getattr(link, "from_socket", None) is not None
                    ]
                )
            else:
                socket_state["links"].extend(
                    [
                        _describe_socket_reference(getattr(link, "to_socket", None))
                        for link in socket.links
                        if getattr(link, "to_socket", None) is not None
                    ]
                )
            if include_default_values and hasattr(socket, "default_value"):
                try:
                    socket_state["default_value"] = _copy_socket_default_value(socket.default_value)
                except Exception:
                    pass
            state.append(socket_state)
        return state

    def _socket_types_are_numeric_compatible(socket_type_a, socket_type_b):
        family_a = _numeric_socket_family(socket_type_a)
        family_b = _numeric_socket_family(socket_type_b)
        return bool(family_a) and bool(family_b) and family_a == family_b

    def _socket_types_are_string_compatible(socket_type_a, socket_type_b):
        family_a = _string_socket_family(socket_type_a)
        family_b = _string_socket_family(socket_type_b)
        return bool(family_a) and bool(family_b) and family_a == family_b

    def _socket_types_restore_default_compatible(socket_type_a, socket_type_b):
        socket_type_a = str(socket_type_a or "")
        socket_type_b = str(socket_type_b or "")
        return (
            socket_type_a == socket_type_b
            or _socket_types_are_numeric_compatible(socket_type_a, socket_type_b)
            or _socket_types_are_string_compatible(socket_type_a, socket_type_b)
        )

    def _apply_group_socket_interface_shape(socket, spec):
        if socket is None or not isinstance(spec, dict):
            return
        if hasattr(socket, "description"):
            try:
                socket.description = str(spec.get("description", "") or "")
            except Exception:
                pass
        if hasattr(socket, "optional_label"):
            try:
                socket.optional_label = bool(spec.get("optional_label", False))
            except Exception:
                pass
        if hasattr(socket, "label"):
            try:
                socket.label = str(getattr(socket, "name", "") or "")
            except Exception:
                pass
        for prop_name in ("hide_value", "min_value", "max_value"):
            if prop_name not in spec:
                continue
            value = spec.get(prop_name, None)
            if value is None and prop_name != "hide_value":
                continue
            if not hasattr(socket, prop_name):
                continue
            try:
                setattr(socket, prop_name, _copy_socket_default_value(value))
            except Exception:
                continue

    def _initialize_group_socket_from_spec(socket, spec):
        _apply_group_socket_interface_shape(socket, spec)
        if socket is None or not isinstance(spec, dict):
            return
        if not bool(spec.get("has_default_value", False)) or not hasattr(socket, "default_value"):
            return
        try:
            socket.default_value = _copy_socket_default_value(spec.get("default_value", None))
        except Exception:
            pass

    def _coerce_group_socket_default_value(socket, value):
        if socket is None:
            return value
        numeric_family = _numeric_socket_family(getattr(socket, "bl_idname", ""))
        if numeric_family == "NodeSocketFloat":
            try:
                return float(value)
            except Exception:
                return value
        if numeric_family == "NodeSocketInt":
            try:
                return int(value)
            except Exception:
                return value
        if _numeric_socket_family(getattr(socket, "bl_idname", "")) != "NodeSocketVector":
            return value
        try:
            current_value = tuple(float(component) for component in getattr(socket, "default_value", ()))
            source_value = tuple(float(component) for component in value)
        except Exception:
            return value
        if not current_value:
            return value
        target_value = list(current_value)
        for index in range(min(len(target_value), len(source_value))):
            target_value[index] = source_value[index]
        return tuple(target_value)

    def _clamp_group_socket_default_value(socket, spec):
        if socket is None or not isinstance(spec, dict) or not hasattr(socket, "default_value"):
            return
        numeric_family = _numeric_socket_family(getattr(socket, "bl_idname", ""))
        if numeric_family not in {"NodeSocketFloat", "NodeSocketInt", "NodeSocketVector"}:
            return
        min_value = spec.get("min_value", None)
        max_value = spec.get("max_value", None)
        if min_value is None and max_value is None:
            return
        try:
            default_value = getattr(socket, "default_value")
            if numeric_family == "NodeSocketFloat":
                clamped = float(default_value)
                if min_value is not None:
                    clamped = max(float(min_value), clamped)
                if max_value is not None:
                    clamped = min(float(max_value), clamped)
                if float(default_value) != clamped:
                    socket.default_value = clamped
                return
            if numeric_family == "NodeSocketInt":
                clamped = int(default_value)
                if min_value is not None:
                    clamped = max(int(min_value), clamped)
                if max_value is not None:
                    clamped = min(int(max_value), clamped)
                if int(default_value) != clamped:
                    socket.default_value = clamped
                return
            components = [float(component) for component in default_value]
            changed = False
            if min_value is not None:
                min_components = [float(component) for component in min_value]
                for index in range(min(len(components), len(min_components))):
                    new_value = max(min_components[index], components[index])
                    if new_value != components[index]:
                        components[index] = new_value
                        changed = True
            if max_value is not None:
                max_components = [float(component) for component in max_value]
                for index in range(min(len(components), len(max_components))):
                    new_value = min(max_components[index], components[index])
                    if new_value != components[index]:
                        components[index] = new_value
                        changed = True
            if changed:
                socket.default_value = tuple(components[: len(default_value)])
        except Exception:
            pass

    def _restore_group_socket_default_value(socket, socket_state):
        if socket is None or not isinstance(socket_state, dict) or not hasattr(socket, "default_value"):
            return
        old_socket_type = str(socket_state.get("socket_type", "") or "")
        new_socket_type = str(getattr(socket, "bl_idname", "") or "")
        if not _socket_types_restore_default_compatible(new_socket_type, old_socket_type):
            return
        if socket_state.get("default_value", None) is None:
            return
        try:
            socket.default_value = _coerce_group_socket_default_value(
                socket,
                _copy_socket_default_value(socket_state["default_value"]),
            )
        except Exception:
            pass

    def _restore_dynamic_socket_state(
        node,
        direction,
        state,
        socket_specs,
        restore_default_values=True,
        restore_hide_state=True,
    ):
        del socket_specs
        sockets = list(node.inputs if direction == "INPUT" else node.outputs)
        node_tree = getattr(node, "id_data", None)
        if node_tree is None or not sockets or not state:
            return

        unmatched_new_indices = set(range(len(sockets)))
        assignments = {}

        for old_index, old_state in enumerate(state):
            for new_index, socket in enumerate(sockets):
                if new_index not in unmatched_new_indices:
                    continue
                if str(getattr(socket, "bl_idname", "") or "") != old_state["socket_type"]:
                    continue
                if str(getattr(socket, "name", "") or "") != old_state["name"]:
                    continue
                assignments[old_index] = new_index
                unmatched_new_indices.discard(new_index)
                break

        for old_index, old_state in enumerate(state):
            if old_index in assignments:
                continue
            for new_index, socket in enumerate(sockets):
                if new_index not in unmatched_new_indices:
                    continue
                if str(getattr(socket, "name", "") or "") != old_state["name"]:
                    continue
                if not (
                    _socket_types_are_numeric_compatible(getattr(socket, "bl_idname", ""), old_state["socket_type"])
                    or _socket_types_are_string_compatible(getattr(socket, "bl_idname", ""), old_state["socket_type"])
                ):
                    continue
                assignments[old_index] = new_index
                unmatched_new_indices.discard(new_index)
                break

        for old_index, old_state in enumerate(state):
            if old_index in assignments:
                continue
            preferred_index = int(old_state["index"])
            if preferred_index not in unmatched_new_indices or preferred_index >= len(sockets):
                continue
            socket = sockets[preferred_index]
            if str(getattr(socket, "bl_idname", "") or "") != old_state["socket_type"]:
                continue
            assignments[old_index] = preferred_index
            unmatched_new_indices.discard(preferred_index)

        for old_index, new_index in assignments.items():
            socket = sockets[new_index]
            old_state = state[old_index]
            new_socket_type = str(getattr(socket, "bl_idname", "") or "")
            old_socket_type = str(old_state.get("socket_type", "") or "")
            can_restore_default_value = (
                old_socket_type == new_socket_type
                or _socket_types_are_string_compatible(new_socket_type, old_socket_type)
            )
            if (
                direction == "INPUT"
                and restore_default_values
                and can_restore_default_value
                and old_state.get("default_value", None) is not None
                and hasattr(socket, "default_value")
            ):
                try:
                    socket.default_value = _copy_socket_default_value(old_state["default_value"])
                except Exception:
                    pass
            for socket_ref in old_state.get("links", []):
                other_socket = _resolve_socket_reference(node_tree, socket_ref)
                if other_socket is None:
                    continue
                try:
                    if direction == "INPUT":
                        node_tree.links.new(other_socket, socket)
                    else:
                        node_tree.links.new(socket, other_socket)
                except Exception:
                    continue
            if restore_hide_state:
                try:
                    socket.hide = bool(old_state.get("hide", False))
                except Exception:
                    pass

    def _capture_group_socket_state(node, direction, socket_specs):
        sockets = node.inputs if direction == "INPUT" else node.outputs
        stored_identifiers = _decode_group_node_identifiers(node, direction)
        if len(stored_identifiers) != len(sockets):
            if len(socket_specs) == len(sockets):
                stored_identifiers = [str(spec["identifier"]) for spec in socket_specs]
            else:
                stored_identifiers = [f"{direction}_{index}" for index, _socket in enumerate(sockets)]

        state = {}
        for index, socket in enumerate(sockets):
            identifier = stored_identifiers[index] if index < len(stored_identifiers) else f"{direction}_{index}"
            socket_state = state.setdefault(
                identifier,
                {
                    "links": [],
                    "default_value": None,
                    "socket_type": str(getattr(socket, "bl_idname", "") or ""),
                },
            )
            if direction == "INPUT":
                socket_state["links"].extend(
                    [
                        _describe_socket_reference(getattr(link, "from_socket", None))
                        for link in socket.links
                        if getattr(link, "from_socket", None) is not None
                    ]
                )
            else:
                socket_state["links"].extend(
                    [
                        _describe_socket_reference(getattr(link, "to_socket", None))
                        for link in socket.links
                        if getattr(link, "to_socket", None) is not None
                    ]
                )
            if hasattr(socket, "default_value"):
                try:
                    socket_state["default_value"] = _copy_socket_default_value(socket.default_value)
                except Exception:
                    pass
        return state

    def _restore_group_socket_state(node, direction, state, socket_specs, restore_default_values=True):
        sockets = node.inputs if direction == "INPUT" else node.outputs
        node_tree = getattr(node, "id_data", None)
        if node_tree is None:
            return

        identifier_to_socket = {}
        new_identifiers = []
        for socket, spec in zip(sockets, socket_specs):
            identifier = str(spec["identifier"])
            identifier_to_socket[identifier] = socket
            new_identifiers.append(identifier)
            socket_state = state.get(identifier)
            _apply_group_socket_interface_shape(socket, spec)
            if str(direction) == "INPUT" and bool(spec.get("has_default_value", False)):
                _initialize_group_socket_from_spec(socket, spec)
            if direction == "INPUT" and socket_state and restore_default_values:
                _restore_group_socket_default_value(socket, socket_state)

        for identifier, socket_state in state.items():
            socket = identifier_to_socket.get(identifier)
            if socket is None:
                continue
            for socket_ref in socket_state.get("links", []):
                other_socket = _resolve_socket_reference(node_tree, socket_ref)
                if other_socket is None:
                    continue
                try:
                    if direction == "INPUT":
                        node_tree.links.new(other_socket, socket)
                    else:
                        node_tree.links.new(socket, other_socket)
                except Exception:
                    continue

        _encode_group_node_identifiers(node, direction, new_identifiers)

    def _capture_group_socket_entries(node, direction, socket_specs):
        sockets = list(node.inputs if direction == "INPUT" else node.outputs)
        stored_identifiers = _decode_group_node_identifiers(node, direction)
        if len(stored_identifiers) != len(sockets):
            if len(socket_specs) == len(sockets):
                stored_identifiers = [str(spec["identifier"]) for spec in socket_specs]
            else:
                stored_identifiers = [f"{direction}_{index}" for index, _socket in enumerate(sockets)]

        entries = []
        for index, socket in enumerate(sockets):
            entries.append(
                {
                    "identifier": stored_identifiers[index] if index < len(stored_identifiers) else f"{direction}_{index}",
                    "socket": socket,
                    "socket_type": str(getattr(socket, "bl_idname", "") or ""),
                }
            )
        return entries

    def _link_exists_between_sockets(direction, socket, other_socket):
        for link in getattr(socket, "links", []):
            if direction == "INPUT":
                if getattr(link, "from_socket", None) == other_socket and getattr(link, "to_socket", None) == socket:
                    return True
            else:
                if getattr(link, "from_socket", None) == socket and getattr(link, "to_socket", None) == other_socket:
                    return True
        return False

    def _restore_group_socket_links(node, direction, state, identifier_to_socket):
        node_tree = getattr(node, "id_data", None)
        if node_tree is None:
            return
        for identifier, socket in dict(identifier_to_socket or {}).items():
            socket_state = dict(state or {}).get(str(identifier))
            if socket is None or not isinstance(socket_state, dict):
                continue
            for socket_ref in socket_state.get("links", []):
                other_socket = _resolve_socket_reference(node_tree, socket_ref)
                if other_socket is None or _link_exists_between_sockets(direction, socket, other_socket):
                    continue
                try:
                    if direction == "INPUT":
                        node_tree.links.new(other_socket, socket)
                    else:
                        node_tree.links.new(socket, other_socket)
                except Exception:
                    continue

    def _sync_group_node_direction_in_place(node, direction, socket_specs, state):
        sockets = node.inputs if direction == "INPUT" else node.outputs
        existing_entries = _capture_group_socket_entries(node, direction, socket_specs)
        unused_entries = list(existing_entries)
        target_entries = []
        recreated_sockets = {}

        for spec in socket_specs:
            identifier = str(spec["identifier"])
            socket_type = str(spec["socket_type"])
            socket_name = str(spec["name"])
            match = next(
                (
                    entry
                    for entry in unused_entries
                    if str(entry["identifier"]) == identifier and str(entry["socket_type"]) == socket_type
                ),
                None,
            )
            if match is not None:
                unused_entries.remove(match)
                socket = match["socket"]
                try:
                    if str(getattr(socket, "name", "") or "") != socket_name:
                        socket.name = socket_name
                except Exception:
                    pass
            else:
                socket = sockets.new(socket_type, socket_name)
                _initialize_group_socket_from_spec(socket, spec)
                recreated_sockets[identifier] = socket
            _apply_group_socket_interface_shape(socket, spec)
            target_entries.append((identifier, socket, socket_name, spec))

        current_sockets = list(sockets)
        for target_index, (_identifier, socket, socket_name, _spec) in enumerate(target_entries):
            try:
                if str(getattr(socket, "name", "") or "") != socket_name:
                    socket.name = socket_name
            except Exception:
                pass
            try:
                current_index = current_sockets.index(socket)
            except ValueError:
                continue
            if current_index != target_index:
                try:
                    sockets.move(current_index, target_index)
                    current_sockets.insert(target_index, current_sockets.pop(current_index))
                except Exception:
                    pass

        kept_sockets = {socket for _identifier, socket, _socket_name, _spec in target_entries}
        for socket in list(sockets):
            if socket in kept_sockets:
                continue
            try:
                sockets.remove(socket)
            except Exception:
                continue

        if direction == "INPUT":
            for identifier, socket, _socket_name, spec in target_entries:
                _apply_group_socket_interface_shape(socket, spec)
                if identifier in recreated_sockets:
                    _restore_group_socket_default_value(socket, state.get(identifier))

        _encode_group_node_identifiers(node, direction, [identifier for identifier, _socket, _socket_name, _spec in target_entries])
        _restore_group_socket_links(node, direction, state, recreated_sockets)

    def _sync_visible_node_editor_sockets(node_tree, node_name):
        window_manager = getattr(bpy.context, "window_manager", None)
        if window_manager is None or node_tree is None or not node_name:
            return

        for window in window_manager.windows:
            screen = getattr(window, "screen", None)
            if screen is None:
                continue
            for area in screen.areas:
                if getattr(area, "type", "") != "NODE_EDITOR":
                    continue
                region = next((region for region in area.regions if getattr(region, "type", "") == "WINDOW"), None)
                if region is None:
                    continue
                for space in area.spaces:
                    if getattr(space, "type", "") != "NODE_EDITOR":
                        continue
                    if getattr(space, "edit_tree", None) != node_tree:
                        continue
                    try:
                        node_tree.update_tag()
                    except Exception:
                        pass
                    try:
                        area.tag_redraw()
                    except Exception:
                        pass
                    break

    def _sync_group_node_sockets(node):
        try:
            from ..node_system.tree import suspend_runtime_sync, resume_runtime_sync
        except Exception:
            suspend_runtime_sync = None
            resume_runtime_sync = None

        if suspend_runtime_sync is not None:
            suspend_runtime_sync()
        try:
            group_tree = getattr(node, "group_tree", None)
            if group_tree is None or getattr(group_tree, "bl_idname", "") != AFNodeTree.bl_idname:
                node.pop(GROUP_NODE_INPUT_IDENTIFIERS_KEY, None)
                node.pop(GROUP_NODE_OUTPUT_IDENTIFIERS_KEY, None)
                return

            input_specs = _build_group_node_socket_specs(group_tree, "INPUT")
            output_specs = _build_group_node_socket_specs(group_tree, "OUTPUT")
            input_state = _capture_group_socket_state(node, "INPUT", input_specs)
            output_state = _capture_group_socket_state(node, "OUTPUT", output_specs)
            _sync_group_node_direction_in_place(node, "INPUT", input_specs, input_state)
            _sync_group_node_direction_in_place(node, "OUTPUT", output_specs, output_state)
            _apply_group_node_input_constraints(node, input_specs)
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()
        _sync_visible_node_editor_sockets(getattr(node, "id_data", None), getattr(node, "name", ""))

    def _apply_group_node_input_constraints(node, input_specs=None):
        group_tree = getattr(node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != AFNodeTree.bl_idname:
            return
        specs = input_specs if input_specs is not None else _build_group_node_socket_specs(group_tree, "INPUT")
        for socket, spec in zip(getattr(node, "inputs", []), specs):
            _apply_group_socket_interface_shape(socket, spec)
            _clamp_group_socket_default_value(socket, spec)

    def _apply_group_node_constraints_in_tree(node_tree):
        if node_tree is None or getattr(node_tree, "bl_idname", "") != AFNodeTree.bl_idname:
            return
        for node in getattr(node_tree, "nodes", []):
            if getattr(node, "bl_idname", "") != "AFNodeGroup":
                continue
            try:
                _apply_group_node_input_constraints(node)
            except Exception:
                continue

    def _replace_group_node_instance(node, restore_default_values=True):
        node_tree = getattr(node, "id_data", None)
        group_tree = getattr(node, "group_tree", None)
        if node_tree is None or group_tree is None:
            return node

        input_specs = _build_group_node_socket_specs(group_tree, "INPUT")
        output_specs = _build_group_node_socket_specs(group_tree, "OUTPUT")
        input_state = _capture_group_socket_state(node, "INPUT", input_specs)
        output_state = _capture_group_socket_state(node, "OUTPUT", output_specs)

        old_name = str(node.name)
        was_active = getattr(node_tree.nodes, "active", None) == node
        was_selected = bool(getattr(node, "select", False))
        parent = getattr(node, "parent", None)
        try:
            location = getattr(node, "location").copy()
        except Exception:
            location = tuple(getattr(node, "location", (0.0, 0.0)))
        width = float(getattr(node, "width", 140.0))
        hide = bool(getattr(node, "hide", False))
        label = str(getattr(node, "label", "") or "")
        use_custom_color = bool(getattr(node, "use_custom_color", False))
        color = tuple(getattr(node, "color", (0.0, 0.0, 0.0)))

        node_tree.nodes.remove(node)

        new_node = node_tree.nodes.new("AFNodeGroup")
        new_node.name = old_name
        new_node.group_tree = group_tree
        new_node.parent = parent
        new_node.location = location
        new_node.width = width
        new_node.hide = hide
        new_node.label = label
        new_node.use_custom_color = use_custom_color
        if use_custom_color:
            new_node.color = color
        _restore_group_socket_state(
            new_node,
            "INPUT",
            input_state,
            input_specs,
            restore_default_values=restore_default_values,
        )
        _restore_group_socket_state(
            new_node,
            "OUTPUT",
            output_state,
            output_specs,
            restore_default_values=restore_default_values,
        )
        new_node.select = was_selected
        if was_active:
            node_tree.nodes.active = new_node
        _sync_visible_node_editor_sockets(node_tree, new_node.name)
        return new_node

    def _hard_sync_group_node(node):
        _sync_group_node_sockets(node)
        if _group_node_socket_signatures_match(node):
            return node
        return _replace_group_node_instance(node, restore_default_values=False)

    def _iter_group_nodes_referencing_tree(group_tree):
        if group_tree is None:
            return
        for node_tree in bpy.data.node_groups:
            if getattr(node_tree, "bl_idname", "") != AFNodeTree.bl_idname:
                continue
            for node in list(node_tree.nodes):
                if getattr(node, "bl_idname", "") != "AFNodeGroup":
                    continue
                if getattr(node, "group_tree", None) == group_tree:
                    yield node

    def _sync_group_nodes_referencing_tree(group_tree):
        for node in _iter_group_nodes_referencing_tree(group_tree):
            try:
                _hard_sync_group_node(node)
            except Exception:
                pass

    def _group_tree_poll(self, node_tree):
        del self
        return getattr(node_tree, "bl_idname", "") == AFNodeTree.bl_idname

    def _group_tree_updated(self, context):
        del context
        _sync_group_node_sockets(self)

    return {
        "_tag_all_af_node_editor_redraw": _tag_all_af_node_editor_redraw,
        "_iter_group_interface_sockets": _iter_group_interface_sockets,
        "_group_interface_socket_type": _group_interface_socket_type,
        "_is_custom_group_socket_type": _is_custom_group_socket_type,
        "_sanitize_group_node_socket_specs": _sanitize_group_node_socket_specs,
        "_build_group_node_socket_specs": _build_group_node_socket_specs,
        "_group_node_expected_socket_signature": _group_node_expected_socket_signature,
        "_group_node_current_socket_signature": _group_node_current_socket_signature,
        "_group_node_socket_signatures_match": _group_node_socket_signatures_match,
        "_group_node_identifier_key": _group_node_identifier_key,
        "_decode_group_node_identifiers": _decode_group_node_identifiers,
        "_encode_group_node_identifiers": _encode_group_node_identifiers,
        "_copy_socket_default_value": _copy_socket_default_value,
        "_describe_socket_reference": _describe_socket_reference,
        "_resolve_socket_reference": _resolve_socket_reference,
        "_capture_dynamic_socket_state": _capture_dynamic_socket_state,
        "_socket_types_are_numeric_compatible": _socket_types_are_numeric_compatible,
        "_socket_types_are_string_compatible": _socket_types_are_string_compatible,
        "_restore_dynamic_socket_state": _restore_dynamic_socket_state,
        "_capture_group_socket_state": _capture_group_socket_state,
        "_restore_group_socket_state": _restore_group_socket_state,
        "_sync_visible_node_editor_sockets": _sync_visible_node_editor_sockets,
        "_sync_group_node_sockets": _sync_group_node_sockets,
        "_apply_group_node_input_constraints": _apply_group_node_input_constraints,
        "_apply_group_node_constraints_in_tree": _apply_group_node_constraints_in_tree,
        "_replace_group_node_instance": _replace_group_node_instance,
        "_hard_sync_group_node": _hard_sync_group_node,
        "_iter_group_nodes_referencing_tree": _iter_group_nodes_referencing_tree,
        "_sync_group_nodes_referencing_tree": _sync_group_nodes_referencing_tree,
        "_group_tree_poll": _group_tree_poll,
        "_group_tree_updated": _group_tree_updated,
    }
