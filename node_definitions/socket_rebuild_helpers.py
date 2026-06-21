def build_socket_rebuild_helpers(
    *,
    _capture_dynamic_socket_state,
    _restore_dynamic_socket_state,
):
    PARSE_PROPERTY_PACKAGE_INPUT_SPECS = (
        ("AFSocketPropertyPackage", "Property Package"),
    )
    PARSE_PROPERTY_PACKAGE_OUTPUT_SPECS = (
        ("AFSocketObjectList", "Object List"),
        ("AFSocketPropertyDefinition", "Property Definition"),
        ("AFSocketReport", "Report"),
    )

    def _rebuild_sockets(node, input_specs, output_specs, include_default_values=True, restore_dynamic_state=True):
        input_state = []
        output_state = []
        if restore_dynamic_state:
            input_state = _capture_dynamic_socket_state(node, "INPUT", include_default_values=include_default_values)
            output_state = _capture_dynamic_socket_state(node, "OUTPUT", include_default_values=include_default_values)
        while len(node.inputs) > 0:
            node.inputs.remove(node.inputs[-1])
        while len(node.outputs) > 0:
            node.outputs.remove(node.outputs[-1])
        for socket_id, socket_name in input_specs:
            node.inputs.new(socket_id, socket_name)
        for socket_id, socket_name in output_specs:
            node.outputs.new(socket_id, socket_name)
        if restore_dynamic_state:
            _restore_dynamic_socket_state(
                node,
                "INPUT",
                input_state,
                input_specs,
                restore_default_values=include_default_values,
            )
            _restore_dynamic_socket_state(
                node,
                "OUTPUT",
                output_state,
                output_specs,
                restore_default_values=include_default_values,
            )

    def _sync_parse_property_package_sockets(node):
        if str(getattr(node, "bl_idname", "") or "") != "AFNodeParsePropertyPackage":
            return
        input_signature = [
            (str(getattr(socket, "bl_idname", "") or ""), str(getattr(socket, "name", "") or ""))
            for socket in getattr(node, "inputs", [])
        ]
        output_signature = [
            (str(getattr(socket, "bl_idname", "") or ""), str(getattr(socket, "name", "") or ""))
            for socket in getattr(node, "outputs", [])
        ]
        if input_signature == list(PARSE_PROPERTY_PACKAGE_INPUT_SPECS) and output_signature == list(PARSE_PROPERTY_PACKAGE_OUTPUT_SPECS):
            return
        suspend_runtime_sync = None
        resume_runtime_sync = None
        try:
            from ..node_system.tree import resume_runtime_sync, suspend_runtime_sync
        except Exception:
            pass
        if suspend_runtime_sync is not None:
            suspend_runtime_sync()
        try:
            _rebuild_sockets(node, PARSE_PROPERTY_PACKAGE_INPUT_SPECS, PARSE_PROPERTY_PACKAGE_OUTPUT_SPECS)
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()

    return {
        "_rebuild_sockets": _rebuild_sockets,
        "_sync_parse_property_package_sockets": _sync_parse_property_package_sockets,
    }


__all__ = ["build_socket_rebuild_helpers"]
