import copy

from ...runtime_flow.helpers import _find_single_from_input_socket


class RuntimeMutedDataMixin:
    def _find_muted_passthrough_source(self, node, output_socket):
        candidates = []
        output_name = str(getattr(output_socket, "name", "") or "")
        if output_name and output_name in node.inputs:
            candidates.append(node.inputs[output_name])

        output_index = -1
        for index, socket in enumerate(node.outputs):
            if socket == output_socket:
                output_index = index
                break
        if 0 <= output_index < len(node.inputs):
            candidates.append(node.inputs[output_index])

        output_socket_type = str(getattr(output_socket, "bl_idname", "") or "")
        candidates.extend([socket for socket in node.inputs if str(getattr(socket, "bl_idname", "") or "") == output_socket_type])
        candidates.extend(list(node.inputs))

        seen = set()
        unique_candidates = []
        for socket in candidates:
            key = int(socket.as_pointer()) if hasattr(socket, "as_pointer") else id(socket)
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append(socket)

        for input_socket in unique_candidates:
            from_node, from_socket = _find_single_from_input_socket(input_socket)
            if from_node is not None:
                return from_node, from_socket
        return None, None

    def _evaluate_muted_data_node(self, node):
        for output_socket in node.outputs:
            keys = self._socket_output_keys(output_socket)
            if not keys:
                continue
            source_node, source_socket = self._find_muted_passthrough_source(node, output_socket)
            if source_node is None:
                continue
            resolved_value = None
            for key in keys:
                value = self._get_output_from_source(source_node, source_socket, key)
                if value is not None:
                    resolved_value = value
                    break
            if resolved_value is None:
                continue
            for key in keys:
                self._set_output(node, key, copy.deepcopy(resolved_value))


__all__ = ["RuntimeMutedDataMixin"]
