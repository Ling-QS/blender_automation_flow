def build_socket_rebuild_helpers():
    PARSE_PROPERTY_PACKAGE_INPUT_SPECS = (
        ("AFSocketPropertyPackage", "Property Package"),
    )
    PARSE_PROPERTY_PACKAGE_OUTPUT_SPECS = (
        ("AFSocketObjectList", "Object List"),
        ("AFSocketPropertyDefinition", "Property Definition"),
        ("AFSocketReport", "Report"),
    )
    REFRESH_PROPERTY_PACKAGE_INPUT_SPECS = (
        ("AFSocketPropertyPackage", "Property Package"),
        ("AFSocketObjectList", "Object List"),
        ("AFSocketPropertyDefinition", "Property Definition"),
    )
    REFRESH_PROPERTY_PACKAGE_OUTPUT_SPECS = (
        ("AFSocketPropertyPackage", "Property Package"),
        ("AFSocketReport", "Report"),
    )

    def _socket_pointer(socket):
        try:
            return int(socket.as_pointer()) if hasattr(socket, "as_pointer") else id(socket)
        except Exception:
            return id(socket)

    def _find_reusable_socket(unused_sockets, socket_idname, socket_name):
        socket_idname = str(socket_idname or "")
        socket_name = str(socket_name or "")
        exact_match = next(
            (
                socket
                for socket in list(unused_sockets or [])
                if str(getattr(socket, "bl_idname", "") or "") == socket_idname
                and str(getattr(socket, "name", "") or "") == socket_name
            ),
            None,
        )
        if exact_match is not None:
            return exact_match
        return next(
            (
                socket
                for socket in list(unused_sockets or [])
                if str(getattr(socket, "bl_idname", "") or "") == socket_idname
            ),
            None,
        )

    def _sync_socket_collection_in_place(socket_collection, socket_specs):
        current_sockets = list(getattr(socket_collection, "__iter__", lambda: [])())
        unused_sockets = list(current_sockets)
        ordered_sockets = []

        for socket_idname, socket_name in list(socket_specs or []):
            socket = _find_reusable_socket(unused_sockets, socket_idname, socket_name)
            if socket is None:
                socket = socket_collection.new(str(socket_idname or ""), str(socket_name or ""))
            else:
                unused_sockets.remove(socket)
            try:
                if str(getattr(socket, "name", "") or "") != str(socket_name or ""):
                    socket.name = str(socket_name or "")
            except Exception:
                pass
            ordered_sockets.append(socket)

        live_sockets = list(socket_collection)
        for target_index, socket in enumerate(ordered_sockets):
            target_pointer = _socket_pointer(socket)
            current_index = next(
                (
                    index
                    for index, live_socket in enumerate(live_sockets)
                    if _socket_pointer(live_socket) == target_pointer
                ),
                -1,
            )
            if current_index < 0:
                continue
            if current_index != target_index:
                try:
                    socket_collection.move(current_index, target_index)
                    live_sockets.insert(target_index, live_sockets.pop(current_index))
                except Exception:
                    pass

        kept_socket_pointers = {_socket_pointer(socket) for socket in ordered_sockets}
        for socket in list(socket_collection):
            if _socket_pointer(socket) in kept_socket_pointers:
                continue
            try:
                socket_collection.remove(socket)
            except Exception:
                continue

    def _sync_node_sockets_in_place(node, input_specs, output_specs):
        _sync_socket_collection_in_place(getattr(node, "inputs", []), input_specs)
        _sync_socket_collection_in_place(getattr(node, "outputs", []), output_specs)

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
            _sync_node_sockets_in_place(node, PARSE_PROPERTY_PACKAGE_INPUT_SPECS, PARSE_PROPERTY_PACKAGE_OUTPUT_SPECS)
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()

    def _sync_refresh_property_package_sockets(node):
        if str(getattr(node, "bl_idname", "") or "") != "AFNodeRefreshPropertyPackage":
            return
        input_signature = [
            (str(getattr(socket, "bl_idname", "") or ""), str(getattr(socket, "name", "") or ""))
            for socket in getattr(node, "inputs", [])
        ]
        output_signature = [
            (str(getattr(socket, "bl_idname", "") or ""), str(getattr(socket, "name", "") or ""))
            for socket in getattr(node, "outputs", [])
        ]
        if input_signature == list(REFRESH_PROPERTY_PACKAGE_INPUT_SPECS) and output_signature == list(
            REFRESH_PROPERTY_PACKAGE_OUTPUT_SPECS
        ):
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
            _sync_node_sockets_in_place(node, REFRESH_PROPERTY_PACKAGE_INPUT_SPECS, REFRESH_PROPERTY_PACKAGE_OUTPUT_SPECS)
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()

    return {
        "_sync_parse_property_package_sockets": _sync_parse_property_package_sockets,
        "_sync_refresh_property_package_sockets": _sync_refresh_property_package_sockets,
    }


__all__ = ["build_socket_rebuild_helpers"]
