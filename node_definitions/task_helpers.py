import uuid


def build_task_node_helpers(
    *,
    PHYSICS_BAKE_TASK_INPUT_PREFIX,
    PHYSICS_BAKE_TASK_SOCKET_IDNAME,
    PHYSICS_BAKE_TASK_VIRTUAL_LABEL,
    RUN_TASK_PLAN_INPUT_PREFIX,
    RUN_TASK_PLAN_VIRTUAL_LABEL,
    TASK_STEP_INPUT_SPECS,
    TASK_STEP_OUTPUT_SPECS,
    iface_,
    _hide_default_auxiliary_outputs,
    _rebuild_sockets,
):
    run_task_plan_sync_guard = set()

    def _socket_signature(socket):
        return (str(getattr(socket, "bl_idname", "") or ""), str(getattr(socket, "name", "") or ""))

    def _is_physics_bake_settings_socket(socket):
        return getattr(socket, "bl_idname", "") == PHYSICS_BAKE_TASK_SOCKET_IDNAME

    def _is_task_plan_socket(socket):
        return getattr(socket, "bl_idname", "") == "AFSocketTaskPlan"

    def _default_task_plan_socket_name(index):
        return f"{RUN_TASK_PLAN_INPUT_PREFIX}{index}"

    def _new_property_package_bake_asset_id():
        return uuid.uuid4().hex

    def _iter_run_task_plan_real_inputs(node):
        return [
            socket
            for socket in getattr(node, "inputs", [])
            if _is_task_plan_socket(socket) and not bool(getattr(socket, "af_is_virtual", False))
        ]

    def _sync_run_task_plan_inputs(node):
        node_key = int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        if node_key in run_task_plan_sync_guard:
            return
        run_task_plan_sync_guard.add(node_key)
        try:
            task_plan_sockets = [socket for socket in node.inputs if _is_task_plan_socket(socket)]
            if not task_plan_sockets:
                task_plan_sockets.append(node.inputs.new("AFSocketTaskPlan", _default_task_plan_socket_name(1)))

            for socket in task_plan_sockets:
                if (
                    not bool(getattr(socket, "is_linked", False))
                    and not bool(getattr(socket, "af_is_virtual", False))
                    and not bool(getattr(socket, "af_enabled", True))
                    and not str(getattr(socket, "af_display_title", "") or "").strip()
                    and not str(getattr(socket, "name", "") or "").strip()
                ):
                    socket.af_is_virtual = True
                if bool(getattr(socket, "af_is_virtual", False)) and bool(getattr(socket, "is_linked", False)):
                    socket.af_is_virtual = False
                    socket.af_enabled = True

            removable = [
                socket
                for socket in node.inputs
                if _is_task_plan_socket(socket) and bool(getattr(socket, "af_is_virtual", False)) and not bool(getattr(socket, "is_linked", False))
            ]
            for socket in removable:
                node.inputs.remove(socket)

            real_sockets = [socket for socket in node.inputs if _is_task_plan_socket(socket)]
            if not real_sockets:
                real_sockets.append(node.inputs.new("AFSocketTaskPlan", _default_task_plan_socket_name(1)))

            for index, socket in enumerate(real_sockets, 1):
                socket.af_is_virtual = False
                socket.name = _default_task_plan_socket_name(index)
                if not str(getattr(socket, "af_display_title", "") or "").strip():
                    socket.af_display_title = _default_task_plan_socket_name(index)

            virtual_socket = node.inputs.new("AFSocketTaskPlan", RUN_TASK_PLAN_VIRTUAL_LABEL)
            virtual_socket.af_enabled = False
            virtual_socket.af_display_title = ""
            virtual_socket.af_is_virtual = True
        finally:
            run_task_plan_sync_guard.discard(node_key)

    def _sync_run_task_plan_sockets(node):
        if len(getattr(node, "inputs", [])) >= 1 and getattr(node.inputs[0], "bl_idname", "") == "AFSocketFlow":
            node.inputs[0].name = "Flow In"
        if len(getattr(node, "outputs", [])) >= 3:
            if getattr(node.outputs[0], "bl_idname", "") == "AFSocketFlow":
                node.outputs[0].name = "Flow Out"
            if getattr(node.outputs[1], "bl_idname", "") in {"AFSocketString", "NodeSocketString"}:
                node.outputs[1].name = "Status"
            if getattr(node.outputs[2], "bl_idname", "") == "AFSocketReport":
                node.outputs[2].name = "Report"
        _sync_run_task_plan_inputs(node)

    def _remove_last_run_task_plan_input(node):
        real_sockets = _iter_run_task_plan_real_inputs(node)
        if len(real_sockets) <= 1:
            _sync_run_task_plan_sockets(node)
            return False
        node.inputs.remove(real_sockets[-1])
        _sync_run_task_plan_sockets(node)
        return True

    def _add_run_task_plan_input(node):
        if node is None:
            return False
        _sync_run_task_plan_sockets(node)
        virtual_socket = next(
            (
                socket
                for socket in getattr(node, "inputs", [])
                if _is_task_plan_socket(socket) and bool(getattr(socket, "af_is_virtual", False))
            ),
            None,
        )
        if virtual_socket is None:
            return False
        virtual_socket.af_is_virtual = False
        virtual_socket.af_enabled = True
        if not str(getattr(virtual_socket, "af_display_title", "") or "").strip():
            virtual_socket.af_display_title = _default_task_plan_socket_name(len(_iter_run_task_plan_real_inputs(node)) + 1)
        _sync_run_task_plan_sockets(node)
        return True

    def _sync_physics_bake_task_inputs(node):
        sockets = [socket for socket in node.inputs if _is_physics_bake_settings_socket(socket)]
        if not sockets:
            sockets.append(node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, f"{PHYSICS_BAKE_TASK_INPUT_PREFIX}1"))
            sockets.append(node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, PHYSICS_BAKE_TASK_VIRTUAL_LABEL))
        removable = [socket for socket in sockets[:-1] if not socket.is_linked]
        for socket in removable:
            node.inputs.remove(socket)
        sockets = [socket for socket in node.inputs if _is_physics_bake_settings_socket(socket)]
        if not sockets:
            sockets.append(node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, f"{PHYSICS_BAKE_TASK_INPUT_PREFIX}1"))
            sockets.append(node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, PHYSICS_BAKE_TASK_VIRTUAL_LABEL))
        if sockets[-1].is_linked:
            node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, PHYSICS_BAKE_TASK_VIRTUAL_LABEL)
            sockets = [socket for socket in node.inputs if _is_physics_bake_settings_socket(socket)]
        if len(sockets) == 1:
            node.inputs.new(PHYSICS_BAKE_TASK_SOCKET_IDNAME, PHYSICS_BAKE_TASK_VIRTUAL_LABEL)
            sockets = [socket for socket in node.inputs if _is_physics_bake_settings_socket(socket)]
        for index, socket in enumerate(sockets):
            if index == len(sockets) - 1 and not socket.is_linked:
                socket.name = PHYSICS_BAKE_TASK_VIRTUAL_LABEL
            else:
                socket.name = f"{PHYSICS_BAKE_TASK_INPUT_PREFIX}{index + 1}"

    def _sync_bake_target_sockets(node):
        if len(getattr(node, "inputs", [])) >= 2:
            if getattr(node.inputs[0], "bl_idname", "") == "NodeSocketInt":
                node.inputs[0].name = "Frame Start"
            if getattr(node.inputs[1], "bl_idname", "") == "NodeSocketInt":
                node.inputs[1].name = "Frame End"
        if len(getattr(node, "outputs", [])) >= 3:
            if getattr(node.outputs[0], "bl_idname", "") == "AFSocketTaskRef":
                node.outputs[0].name = "Task Ref"
            if getattr(node.outputs[1], "bl_idname", "") == "AFSocketObjectList":
                node.outputs[1].name = "Bake Objects"
            if getattr(node.outputs[2], "bl_idname", "") == "AFSocketReport":
                node.outputs[2].name = "Report"

    def _sync_physics_bake_target_sockets(node):
        if len(getattr(node, "inputs", [])) >= 2:
            if getattr(node.inputs[0], "bl_idname", "") == "NodeSocketInt":
                node.inputs[0].name = "Frame Start"
                node.inputs[0].hide = not bool(getattr(node, "override_frame_range", False))
            if getattr(node.inputs[1], "bl_idname", "") == "NodeSocketInt":
                node.inputs[1].name = "Frame End"
                node.inputs[1].hide = not bool(getattr(node, "override_frame_range", False))
        if len(getattr(node, "outputs", [])) >= 3:
            if getattr(node.outputs[0], "bl_idname", "") == "AFSocketTaskRef":
                node.outputs[0].name = "Task Ref"
            if getattr(node.outputs[1], "bl_idname", "") == "AFSocketObjectList":
                node.outputs[1].name = "Bake Objects"
            if getattr(node.outputs[2], "bl_idname", "") == "AFSocketReport":
                node.outputs[2].name = "Report"
        _sync_physics_bake_task_inputs(node)

    def _sync_evaluate_task_dependencies_sockets(node):
        if len(getattr(node, "inputs", [])) >= 1 and getattr(node.inputs[0], "bl_idname", "") == "AFSocketObjectList":
            node.inputs[0].name = "Object List"
        if len(getattr(node, "outputs", [])) >= 2:
            if getattr(node.outputs[0], "bl_idname", "") == "AFSocketObjectList":
                node.outputs[0].name = "Object List"
            if getattr(node.outputs[1], "bl_idname", "") == "AFSocketReport":
                node.outputs[1].name = "Report"

    def _ensure_named_socket(socket_collection, socket_idname, socket_name):
        matched = []
        for socket in socket_collection:
            if getattr(socket, "bl_idname", "") == socket_idname and str(getattr(socket, "name", "") or "") == socket_name:
                matched.append(socket)
        keep_socket = matched[0] if matched else socket_collection.new(socket_idname, socket_name)
        for socket in matched[1:]:
            if bool(getattr(socket, "is_linked", False)):
                continue
            try:
                socket_collection.remove(socket)
            except Exception:
                pass
        return keep_socket

    def _find_named_socket(socket_collection, socket_idname, socket_name):
        for socket in socket_collection:
            if getattr(socket, "bl_idname", "") == socket_idname and str(getattr(socket, "name", "") or "") == socket_name:
                return socket
        return None

    def _ensure_render_target_input_sockets(node):
        had_frame_socket = _find_named_socket(node.inputs, "NodeSocketInt", "Frame") is not None
        had_frame_start_socket = _find_named_socket(node.inputs, "NodeSocketInt", "Frame Start") is not None
        had_frame_end_socket = _find_named_socket(node.inputs, "NodeSocketInt", "Frame End") is not None
        frame_socket = _ensure_named_socket(node.inputs, "NodeSocketInt", "Frame")
        frame_start_socket = _ensure_named_socket(node.inputs, "NodeSocketInt", "Frame Start")
        frame_end_socket = _ensure_named_socket(node.inputs, "NodeSocketInt", "Frame End")
        if not had_frame_socket and not bool(getattr(frame_socket, "is_linked", False)):
            frame_socket.default_value = int(getattr(node, "frame", 1))
        if not had_frame_start_socket and not bool(getattr(frame_start_socket, "is_linked", False)):
            frame_start_socket.default_value = int(getattr(node, "frame_start", 1))
        if not had_frame_end_socket and not bool(getattr(frame_end_socket, "is_linked", False)):
            frame_end_socket.default_value = int(getattr(node, "frame_end", 250))

    def _sync_render_target_sockets(node):
        _ensure_render_target_input_sockets(node)
        _ensure_named_socket(node.outputs, "AFSocketTaskRef", "Task Ref")
        _ensure_named_socket(node.outputs, "AFSocketObjectList", "Render Objects")
        _ensure_named_socket(node.outputs, "AFSocketReport", "Report")

    def _sync_task_step_sockets(node):
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature == TASK_STEP_INPUT_SPECS and output_signature == TASK_STEP_OUTPUT_SPECS:
            return
        _rebuild_sockets(node, TASK_STEP_INPUT_SPECS, TASK_STEP_OUTPUT_SPECS)

    def _sync_task_output_sockets(node):
        input_specs = (
            ("AFSocketFlow", "Flow In"),
            ("NodeSocketString", "Status"),
        )
        output_specs = (
            ("AFSocketTaskPlan", "Task Plan"),
            ("AFSocketReport", "Report"),
        )
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature != input_specs or output_signature != output_specs:
            _rebuild_sockets(node, input_specs, output_specs)
        status_input = getattr(node, "inputs", {}).get("Status") if hasattr(getattr(node, "inputs", None), "get") else None
        if status_input is not None:
            try:
                status_input.hide_value = True
            except Exception:
                pass
        _hide_default_auxiliary_outputs(node)

    def _sync_branch_end_sockets(node):
        input_specs = (
            ("AFSocketFlow", "Branch Flow"),
        )
        output_specs = ()
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature != input_specs or output_signature != output_specs:
            _rebuild_sockets(node, input_specs, output_specs)

    def _sync_run_background_task_plan_sockets(node):
        input_specs = (
            ("AFSocketFlow", "Flow In"),
            ("AFSocketTaskPlan", "Task Plan"),
        )
        output_specs = (
            ("AFSocketFlow", "Flow Out"),
            ("AFSocketTaskHandle", "Task Handle"),
            ("NodeSocketString", "Status"),
            ("AFSocketReport", "Report"),
        )
        input_signature = tuple(_socket_signature(socket) for socket in getattr(node, "inputs", []))
        output_signature = tuple(_socket_signature(socket) for socket in getattr(node, "outputs", []))
        if input_signature != input_specs or output_signature != output_specs:
            _rebuild_sockets(node, input_specs, output_specs)

    return {
        "_socket_signature": _socket_signature,
        "_is_physics_bake_settings_socket": _is_physics_bake_settings_socket,
        "_is_task_plan_socket": _is_task_plan_socket,
        "_default_task_plan_socket_name": _default_task_plan_socket_name,
        "_new_property_package_bake_asset_id": _new_property_package_bake_asset_id,
        "_iter_run_task_plan_real_inputs": _iter_run_task_plan_real_inputs,
        "_sync_run_task_plan_inputs": _sync_run_task_plan_inputs,
        "_sync_run_task_plan_sockets": _sync_run_task_plan_sockets,
        "_remove_last_run_task_plan_input": _remove_last_run_task_plan_input,
        "_add_run_task_plan_input": _add_run_task_plan_input,
        "_sync_physics_bake_task_inputs": _sync_physics_bake_task_inputs,
        "_sync_bake_target_sockets": _sync_bake_target_sockets,
        "_sync_physics_bake_target_sockets": _sync_physics_bake_target_sockets,
        "_sync_evaluate_task_dependencies_sockets": _sync_evaluate_task_dependencies_sockets,
        "_ensure_named_socket": _ensure_named_socket,
        "_find_named_socket": _find_named_socket,
        "_ensure_render_target_input_sockets": _ensure_render_target_input_sockets,
        "_sync_render_target_sockets": _sync_render_target_sockets,
        "_sync_task_step_sockets": _sync_task_step_sockets,
        "_sync_task_output_sockets": _sync_task_output_sockets,
        "_sync_branch_end_sockets": _sync_branch_end_sockets,
        "_sync_run_background_task_plan_sockets": _sync_run_background_task_plan_sockets,
    }
