def build_socket_rebuild_helpers(
    *,
    _capture_dynamic_socket_state,
    _restore_dynamic_socket_state,
):
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

    return {
        "_rebuild_sockets": _rebuild_sockets,
    }


__all__ = ["build_socket_rebuild_helpers"]
