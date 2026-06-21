import bpy

from ...runtime_core.constants import FlowExecutionError, TASK_KIND_PROPERTY_PACKAGE_BAKE, _enrich_flow_error_context
from ...runtime_flow.helpers import _find_single_from_input_socket, _first_output_node


class RuntimeLinearFlowMixin:
    def _find_start_node(self):
        start_nodes = [n for n in self.node_tree.nodes if n.bl_idname == "AFNodeStart"]
        if not start_nodes:
            raise FlowExecutionError("AF_E009", "Flow must contain at least one Start node")
        if self.start_node_name:
            start_node = self.node_tree.nodes.get(self.start_node_name)
            if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
                raise FlowExecutionError("AF_E009", f"Start node '{self.start_node_name}' was not found")
            return start_node
        active_start_nodes = [node for node in start_nodes if bool(getattr(node, "is_active_start", True))]
        if len(active_start_nodes) != 1:
            raise FlowExecutionError("AF_E009", "Flow must contain exactly one enabled Start node")
        return active_start_nodes[0]

    def _is_executable_flow_entry(self, entry):
        node = entry.get("node") if isinstance(entry, dict) else None
        node_type = str(getattr(node, "bl_idname", "") or "")
        return node is not None and node_type not in {"AFNodeGroup", "NodeGroupOutput"}

    def _compile_linear_flow(self):
        start = self._find_start_node()
        raw_entries = self._collect_linear_flow_entries(start, {"AFNodeEnd"}, [], set())
        if not raw_entries or getattr(raw_entries[-1].get("node"), "bl_idname", "") != "AFNodeEnd":
            raise FlowExecutionError("AF_E009", "Start node cannot reach End node")
        flow_entries = [entry for entry in raw_entries if self._is_executable_flow_entry(entry)]
        self.flow_repeat_pairs, total_steps = self._compile_repeat_metadata(
            flow_entries,
            start.name,
            lambda entry: self._flow_node_step_cost(entry["node"]),
        )
        self.flow_subflow_plans, subflow_steps = self._compile_subflow_metadata(flow_entries, start.name)
        self.flow_branch_plans, branch_steps = self._compile_branch_metadata(flow_entries, start.name)
        self.nodes_in_order = [entry["node"] for entry in flow_entries]
        self.node_group_paths_in_order = [
            [dict(item) for item in list(entry.get("group_path", []) or []) if isinstance(item, dict)]
            for entry in flow_entries
        ]
        self.settings.total_step_count = int(total_steps) + int(subflow_steps) + int(branch_steps)

    def _flow_entry_identity(self, node, group_path=None):
        return f"{self._group_path_key(group_path)}::{self._node_identity(node)}"

    def _collect_group_linear_flow_entries(self, group_node, parent_group_path=None, visited=None):
        group_tree = getattr(group_node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError(
                "AF_E030",
                "Group tree is missing",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )

        flow_group_inputs = self._find_group_flow_socket_nodes(group_tree, "NodeGroupInput", "outputs")
        linked_flow_group_inputs = [
            (node, socket)
            for node, socket in flow_group_inputs
            if bool(getattr(socket, "links", None))
        ]
        if linked_flow_group_inputs:
            flow_group_inputs = linked_flow_group_inputs
        if not flow_group_inputs:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group is missing Flow output on Group Input",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        if len(flow_group_inputs) > 1:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group must contain exactly one flow-capable Group Input",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        flow_input_node, flow_socket = flow_group_inputs[0]

        flow_group_outputs = self._find_group_flow_socket_nodes(group_tree, "NodeGroupOutput", "inputs")
        linked_flow_group_outputs = [
            (node, socket)
            for node, socket in flow_group_outputs
            if bool(getattr(socket, "links", None))
        ]
        if linked_flow_group_outputs:
            flow_group_outputs = linked_flow_group_outputs
        if not flow_group_outputs:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group is missing Flow input on Group Output",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        if len(flow_group_outputs) > 1:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group must contain exactly one flow-capable Group Output",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        expected_group_output, _output_flow_socket = flow_group_outputs[0]

        start_node = _first_output_node(flow_input_node, flow_socket.name)
        if start_node is None:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group input is not connected to a group flow path",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )

        group_path = list(parent_group_path or [])
        group_path.append(self._make_step_ref(group_node))
        try:
            group_entries = self._collect_linear_flow_entries(start_node, {"NodeGroupOutput"}, group_path, visited)
        except FlowExecutionError as exc:
            raise _enrich_flow_error_context(
                exc,
                group_node,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        if not group_entries or getattr(group_entries[-1].get("node"), "bl_idname", "") != "NodeGroupOutput":
            raise FlowExecutionError(
                "AF_E009",
                "Flow group cannot reach Group Output",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        if group_entries[-1].get("node") != expected_group_output:
            raise FlowExecutionError(
                "AF_E009",
                "Flow group cannot reach the flow-capable Group Output",
                group_node.name,
                getattr(getattr(group_node, "id_data", None), "name", self.node_tree.name),
                parent_group_path,
            )
        return group_entries

    def _collect_linear_flow_entries(self, start_node, stop_node_types, group_path=None, visited=None):
        entries = []
        current = start_node
        active_group_path = list(group_path or [])
        visited_identities = visited if visited is not None else set()

        while current is not None:
            current_identity = self._flow_entry_identity(current, active_group_path)
            if current_identity in visited_identities:
                raise FlowExecutionError(
                    "AF_E009",
                    "Flow graph has a loop",
                    current.name,
                    getattr(getattr(current, "id_data", None), "name", self.node_tree.name),
                    active_group_path,
                )
            visited_identities.add(current_identity)

            entries.append(
                {
                    "node": current,
                    "group_path": [dict(item) for item in active_group_path],
                }
            )
            if current.bl_idname in stop_node_types:
                break

            if current.bl_idname == "AFNodeGroup" and not bool(getattr(current, "mute", False)):
                entries.extend(self._collect_group_linear_flow_entries(current, active_group_path, visited_identities))

            current = _first_output_node(current, "Flow Out")
        return entries

    def _collect_upstream_geometry_attribute_dependencies(self, node, group_path, visited=None, found=None):
        if node is None:
            return [] if found is None else list(found.values())

        visited_nodes = visited if visited is not None else set()
        found_objects = found if found is not None else {}
        node_identity = self._flow_entry_identity(node, group_path)
        if node_identity in visited_nodes:
            return list(found_objects.values())
        visited_nodes.add(node_identity)

        if str(getattr(node, "bl_idname", "") or "") == "AFNodeReadGeometryAttribute" and not bool(getattr(node, "mute", False)):
            try:
                source_object, _source_item, _source_count = self._geometry_attribute_source_object(node, group_path)
            except Exception:
                source_object = getattr(node, "target_object", None)
            if source_object is not None:
                found_objects[int(source_object.session_uid)] = source_object

        for input_socket in getattr(node, "inputs", []):
            if str(getattr(input_socket, "bl_idname", "") or "") == "AFSocketFlow":
                continue
            from_node, from_socket = _find_single_from_input_socket(input_socket)
            if from_node is None:
                continue
            resolved_node, _resolved_socket, resolved_group_path = self._trace_output_source(from_node, from_socket, group_path)
            if resolved_node is None:
                continue
            self._collect_upstream_geometry_attribute_dependencies(
                resolved_node,
                resolved_group_path,
                visited_nodes,
                found_objects,
            )
        return list(found_objects.values())

    def _collect_property_package_bake_read_geometry_dependency_objects(self, task_ref):
        if not isinstance(task_ref, dict):
            return []
        if str(task_ref.get("task_kind", "") or "") != TASK_KIND_PROPERTY_PACKAGE_BAKE:
            return []

        start_tree_name = str(task_ref.get("start_tree_name", "") or task_ref.get("source_tree_name", "") or "")
        start_node_name = str(task_ref.get("start_node_name", "") or "").strip()
        if not start_tree_name or not start_node_name:
            return []

        start_tree = bpy.data.node_groups.get(start_tree_name)
        if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
            return []

        start_node = getattr(getattr(start_tree, "nodes", None), "get", lambda _name: None)(start_node_name)
        if start_node is None:
            return []

        child_runner = self.__class__(
            start_tree,
            self.scene,
            ui_context=dict(self.ui_context or {}),
            start_node_name=start_node_name,
            auto_follow=False,
        )
        flow_entries = child_runner._collect_linear_flow_entries(start_node, {"AFNodeEnd"}, [], set())

        found = {}
        visited = set()
        for entry in flow_entries:
            flow_node = entry.get("node")
            if flow_node is None or bool(getattr(flow_node, "mute", False)):
                continue
            for source_object in child_runner._collect_upstream_geometry_attribute_dependencies(
                flow_node,
                entry.get("group_path", []),
                visited,
                found,
            ):
                if source_object is None:
                    continue
                found[int(source_object.session_uid)] = source_object
        return list(found.values())


__all__ = ["RuntimeLinearFlowMixin"]
