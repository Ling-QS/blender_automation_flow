import json

import bpy


def build_group_node_helpers(
    *,
    AFNodeTree,
    GROUP_NODE_INPUT_IDENTIFIERS_KEY,
    GROUP_NODE_OUTPUT_IDENTIFIERS_KEY,
    GROUP_SUPPORTED_SOCKET_IDNAMES,
    NUMERIC_COMPATIBLE_SOCKET_IDNAMES,
    _rebuild_sockets,
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
            if socket_type not in GROUP_SUPPORTED_SOCKET_IDNAMES:
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
            if socket_type in GROUP_SUPPORTED_SOCKET_IDNAMES:
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
            {
                "identifier": str(getattr(item, "identifier", f"{direction}_{index}")),
                "socket_type": _group_interface_socket_type(item),
                "name": str(item.name),
                "position": int(getattr(item, "position", index)),
            }
            for index, item in enumerate(interface_items)
        ]
        return _sanitize_group_node_socket_specs(group_tree, direction, specs)

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
        socket_type_a = str(socket_type_a or "")
        socket_type_b = str(socket_type_b or "")
        return (
            bool(socket_type_a)
            and bool(socket_type_b)
            and socket_type_a in NUMERIC_COMPATIBLE_SOCKET_IDNAMES
            and socket_type_b in NUMERIC_COMPATIBLE_SOCKET_IDNAMES
        )

    def _socket_types_are_string_compatible(socket_type_a, socket_type_b):
        socket_type_a = str(socket_type_a or "")
        socket_type_b = str(socket_type_b or "")
        string_types = {"AFSocketString", "NodeSocketString"}
        return bool(socket_type_a) and bool(socket_type_b) and socket_type_a in string_types and socket_type_b in string_types

    def _restore_dynamic_socket_state(node, direction, state, socket_specs, restore_default_values=True):
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
            if (
                direction == "INPUT"
                and restore_default_values
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
                    "socket_name": str(getattr(socket, "name", "") or ""),
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

    def _restore_group_socket_state(node, direction, state, socket_specs):
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
            previous_socket_type = str((socket_state or {}).get("socket_type", "") or "")
            current_socket_type = str(getattr(socket, "bl_idname", "") or "")
            default_types_match = (
                previous_socket_type == current_socket_type
                or _socket_types_are_numeric_compatible(previous_socket_type, current_socket_type)
            )
            if (
                direction == "INPUT"
                and socket_state
                and default_types_match
                and socket_state.get("default_value", None) is not None
                and hasattr(socket, "default_value")
            ):
                try:
                    socket.default_value = _copy_socket_default_value(socket_state["default_value"])
                except Exception:
                    pass

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
            _rebuild_sockets(
                node,
                [(spec["socket_type"], spec["name"]) for spec in input_specs],
                [(spec["socket_type"], spec["name"]) for spec in output_specs],
                restore_dynamic_state=False,
            )
            _restore_group_socket_state(node, "INPUT", input_state, input_specs)
            _restore_group_socket_state(node, "OUTPUT", output_state, output_specs)
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()
        _sync_visible_node_editor_sockets(getattr(node, "id_data", None), getattr(node, "name", ""))

    def _replace_group_node_instance(node):
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
        _restore_group_socket_state(new_node, "INPUT", input_state, input_specs)
        _restore_group_socket_state(new_node, "OUTPUT", output_state, output_specs)
        new_node.select = was_selected
        if was_active:
            node_tree.nodes.active = new_node
        _sync_visible_node_editor_sockets(node_tree, new_node.name)
        return new_node

    def _hard_sync_group_node(node):
        if _group_node_socket_signatures_match(node):
            return node
        _sync_group_node_sockets(node)
        if _group_node_socket_signatures_match(node):
            return node
        return _replace_group_node_instance(node)

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
        "_replace_group_node_instance": _replace_group_node_instance,
        "_hard_sync_group_node": _hard_sync_group_node,
        "_iter_group_nodes_referencing_tree": _iter_group_nodes_referencing_tree,
        "_sync_group_nodes_referencing_tree": _sync_group_nodes_referencing_tree,
        "_group_tree_poll": _group_tree_poll,
        "_group_tree_updated": _group_tree_updated,
    }
