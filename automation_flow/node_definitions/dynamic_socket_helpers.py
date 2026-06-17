from ..runtime_flow.helpers import _find_single_from_input_socket, _valid_socket_links
from ..node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME


def build_dynamic_socket_helpers(
    *,
    CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE,
    CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE,
    INDEX_SWITCH_SOCKET_IDNAME_BY_MODE,
    INDEX_SWITCH_VIRTUAL_LABEL,
    PROPERTY_ASSIGNMENT_INPUT_PREFIX,
    PROPERTY_ASSIGNMENT_VIRTUAL_LABEL,
    SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE,
    SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE,
    SWITCH_SOCKET_IDNAME_BY_MODE,
    _rebuild_sockets,
):
    index_switch_sync_guard = set()
    create_property_package_sync_guard = set()

    def _is_property_assignment_socket(socket):
        return getattr(socket, "bl_idname", "") == "AFSocketPropertyAssignment"

    def _is_index_switch_value_socket(socket):
        return getattr(socket, "bl_idname", "") in set(INDEX_SWITCH_SOCKET_IDNAME_BY_MODE.values())

    def _index_switch_socket_idname_for_mode(mode):
        return INDEX_SWITCH_SOCKET_IDNAME_BY_MODE.get(str(mode), "AFSocketFloatValue")

    def _switch_socket_idname_for_mode(mode):
        return SWITCH_SOCKET_IDNAME_BY_MODE.get(str(mode), "NodeSocketFloat")

    def _sample_object_index_socket_idname_for_mode(mode):
        return SAMPLE_OBJECT_INDEX_SOCKET_IDNAME_BY_MODE.get(str(mode), "NodeSocketFloat")

    def _sample_object_index_output_key_for_mode(mode):
        return SAMPLE_OBJECT_INDEX_OUTPUT_KEY_BY_MODE.get(str(mode), "float_value")

    def _context_reduce_socket_idname_for_type(value_type):
        return CONTEXT_REDUCE_SOCKET_IDNAME_BY_TYPE.get(str(value_type), "NodeSocketFloat")

    def _context_reduce_output_key_for_type(value_type):
        return CONTEXT_REDUCE_OUTPUT_KEY_BY_TYPE.get(str(value_type), "float_value")

    def _default_index_switch_socket_name(index):
        return str(index)

    def _default_property_assignment_socket_name(index):
        return f"{PROPERTY_ASSIGNMENT_INPUT_PREFIX}{index}"

    def _iter_create_property_package_assignment_inputs(node):
        return [
            socket
            for socket in getattr(node, "inputs", [])
            if _is_property_assignment_socket(socket) and not bool(getattr(socket, "af_is_virtual", False))
        ]

    def _iter_index_switch_real_inputs(node):
        return [
            socket
            for socket in getattr(node, "inputs", [])
            if _is_index_switch_value_socket(socket) and not bool(getattr(socket, "af_is_virtual", False))
        ]

    def _sync_index_switch_sockets(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in index_switch_sync_guard:
            return
        index_switch_sync_guard.add(node_key)
        try:
            socket_idname = _index_switch_socket_idname_for_mode(getattr(node, "mode", "FLOAT"))
            existing_value_sockets = [socket for socket in getattr(node, "inputs", []) if _is_index_switch_value_socket(socket)]
            real_input_count = 0
            for socket in existing_value_sockets:
                if bool(getattr(socket, "is_linked", False)) or not bool(getattr(socket, "af_is_virtual", False)):
                    socket.af_is_virtual = False
                    socket.name = _default_index_switch_socket_name(real_input_count)
                    real_input_count += 1
                else:
                    socket.af_is_virtual = True
                    socket.name = INDEX_SWITCH_VIRTUAL_LABEL
            real_input_count = max(1, real_input_count)
            input_specs = [("NodeSocketInt", "Index")]
            input_specs.extend((socket_idname, _default_index_switch_socket_name(index)) for index in range(real_input_count))
            input_specs.append((socket_idname, INDEX_SWITCH_VIRTUAL_LABEL))
            output_specs = [(socket_idname, "Value")]
            _rebuild_sockets(node, input_specs, output_specs)

            value_sockets = [socket for socket in getattr(node, "inputs", []) if getattr(socket, "bl_idname", "") == socket_idname]
            for index, socket in enumerate(value_sockets):
                is_virtual = index == len(value_sockets) - 1
                socket.af_is_virtual = is_virtual
                socket.name = INDEX_SWITCH_VIRTUAL_LABEL if is_virtual else _default_index_switch_socket_name(index)
            if len(getattr(node, "outputs", [])) >= 1:
                node.outputs[0].name = "Value"
            if getattr(node, "inputs", None):
                node.inputs[0].name = "Index"
        finally:
            index_switch_sync_guard.discard(node_key)

    def _remove_last_index_switch_input(node):
        real_sockets = _iter_index_switch_real_inputs(node)
        if len(real_sockets) <= 1:
            _sync_index_switch_sockets(node)
            return False
        node.inputs.remove(real_sockets[-1])
        _sync_index_switch_sockets(node)
        return True

    def _add_index_switch_input(node):
        if node is None:
            return False
        _sync_index_switch_sockets(node)
        virtual_socket = next(
            (
                socket
                for socket in getattr(node, "inputs", [])
                if _is_index_switch_value_socket(socket) and bool(getattr(socket, "af_is_virtual", False))
            ),
            None,
        )
        if virtual_socket is None:
            return False
        virtual_socket.af_is_virtual = False
        virtual_socket.name = _default_index_switch_socket_name(len(_iter_index_switch_real_inputs(node)))
        _sync_index_switch_sockets(node)
        return True

    def _sync_create_property_package_assignment_inputs(node):
        _sync_property_assignment_dynamic_inputs(node, visible=True)

    def _sync_property_assignment_dynamic_inputs(node, visible=True):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in create_property_package_sync_guard:
            return
        create_property_package_sync_guard.add(node_key)
        try:
            assignment_sockets = [socket for socket in getattr(node, "inputs", []) if _is_property_assignment_socket(socket)]
            if not assignment_sockets:
                assignment_sockets.append(node.inputs.new("AFSocketPropertyAssignment", _default_property_assignment_socket_name(1)))
                assignment_sockets.append(node.inputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_VIRTUAL_LABEL))

            removable = [socket for socket in assignment_sockets[:-1] if not bool(getattr(socket, "is_linked", False))]
            for socket in removable:
                node.inputs.remove(socket)

            assignment_sockets = [socket for socket in getattr(node, "inputs", []) if _is_property_assignment_socket(socket)]
            if not assignment_sockets:
                assignment_sockets.append(node.inputs.new("AFSocketPropertyAssignment", _default_property_assignment_socket_name(1)))
                assignment_sockets.append(node.inputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_VIRTUAL_LABEL))

            if bool(getattr(assignment_sockets[-1], "is_linked", False)):
                node.inputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_VIRTUAL_LABEL)
                assignment_sockets = [socket for socket in getattr(node, "inputs", []) if _is_property_assignment_socket(socket)]

            if len(assignment_sockets) == 1:
                node.inputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_VIRTUAL_LABEL)
                assignment_sockets = [socket for socket in getattr(node, "inputs", []) if _is_property_assignment_socket(socket)]

            for index, socket in enumerate(assignment_sockets):
                is_virtual = index == len(assignment_sockets) - 1 and not bool(getattr(socket, "is_linked", False))
                socket.af_is_virtual = is_virtual
                socket.name = PROPERTY_ASSIGNMENT_VIRTUAL_LABEL if is_virtual else _default_property_assignment_socket_name(index + 1)
                socket.hide = not bool(visible)
        finally:
            create_property_package_sync_guard.discard(node_key)

    def _remove_last_create_property_package_assignment_input(node):
        real_sockets = _iter_create_property_package_assignment_inputs(node)
        if len(real_sockets) <= 1:
            _sync_create_property_package_sockets(node)
            return False
        node.inputs.remove(real_sockets[-1])
        _sync_create_property_package_sockets(node)
        return True

    def _add_create_property_package_assignment_input(node):
        if node is None:
            return False
        _sync_create_property_package_sockets(node)
        virtual_socket = next(
            (
                socket
                for socket in getattr(node, "inputs", [])
                if _is_property_assignment_socket(socket) and bool(getattr(socket, "af_is_virtual", False))
            ),
            None,
        )
        if virtual_socket is None:
            return False
        virtual_socket.af_is_virtual = False
        _sync_create_property_package_sockets(node)
        return True

    def _sync_create_property_package_sockets(node):
        if len(getattr(node, "inputs", [])) >= 1 and getattr(node.inputs[0], "bl_idname", "") == "AFSocketObjectList":
            node.inputs[0].name = "Object List"
        _sync_create_property_package_assignment_inputs(node)

    def _sync_apply_object_properties_sockets(node):
        def _ensure_single_input(socket_idname, socket_name):
            matches = [socket for socket in getattr(node, "inputs", []) if getattr(socket, "bl_idname", "") == socket_idname]
            if not matches:
                matches = [node.inputs.new(socket_idname, socket_name)]
            primary = matches[0]
            primary.name = socket_name
            for socket in matches[1:]:
                node.inputs.remove(socket)
            return primary

        flow_socket = _ensure_single_input("AFSocketFlow", "Flow In")
        object_list_socket = _ensure_single_input("AFSocketObjectList", "Object List")
        property_package_socket = _ensure_single_input("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)

        try:
            current_inputs = list(getattr(node, "inputs", []))
            for target_index, socket in enumerate((flow_socket, object_list_socket, property_package_socket)):
                current_index = current_inputs.index(socket)
                if current_index != target_index:
                    node.inputs.move(current_index, target_index)
                    current_inputs.insert(target_index, current_inputs.pop(current_index))
        except Exception:
            pass

        use_assignment_mode = str(getattr(node, "apply_mode", "PACKAGE") or "PACKAGE") == "ASSIGNMENT"
        property_package_socket.hide = bool(use_assignment_mode)
        _sync_property_assignment_dynamic_inputs(node, visible=bool(use_assignment_mode))

    return {
        "_valid_socket_links": _valid_socket_links,
        "_find_single_from_input_socket": _find_single_from_input_socket,
        "_is_property_assignment_socket": _is_property_assignment_socket,
        "_is_index_switch_value_socket": _is_index_switch_value_socket,
        "_index_switch_socket_idname_for_mode": _index_switch_socket_idname_for_mode,
        "_switch_socket_idname_for_mode": _switch_socket_idname_for_mode,
        "_sample_object_index_socket_idname_for_mode": _sample_object_index_socket_idname_for_mode,
        "_sample_object_index_output_key_for_mode": _sample_object_index_output_key_for_mode,
        "_context_reduce_socket_idname_for_type": _context_reduce_socket_idname_for_type,
        "_context_reduce_output_key_for_type": _context_reduce_output_key_for_type,
        "_default_index_switch_socket_name": _default_index_switch_socket_name,
        "_default_property_assignment_socket_name": _default_property_assignment_socket_name,
        "_iter_create_property_package_assignment_inputs": _iter_create_property_package_assignment_inputs,
        "_iter_index_switch_real_inputs": _iter_index_switch_real_inputs,
        "_sync_index_switch_sockets": _sync_index_switch_sockets,
        "_remove_last_index_switch_input": _remove_last_index_switch_input,
        "_add_index_switch_input": _add_index_switch_input,
        "_sync_create_property_package_assignment_inputs": _sync_create_property_package_assignment_inputs,
        "_sync_property_assignment_dynamic_inputs": _sync_property_assignment_dynamic_inputs,
        "_remove_last_create_property_package_assignment_input": _remove_last_create_property_package_assignment_input,
        "_add_create_property_package_assignment_input": _add_create_property_package_assignment_input,
        "_sync_create_property_package_sockets": _sync_create_property_package_sockets,
        "_sync_apply_object_properties_sockets": _sync_apply_object_properties_sockets,
    }


__all__ = ["build_dynamic_socket_helpers"]
