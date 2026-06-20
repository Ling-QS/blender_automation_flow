import bpy

from ...runtime_core.constants import FlowExecutionError, TASK_KIND_PROPERTY_PACKAGE_BAKE
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

    def _compile_linear_flow(self):
        start = self._find_start_node()
        ordered = []
        visited = set()
        current = start
        while current is not None:
            if current.name in visited:
                raise FlowExecutionError("AF_E009", "Flow graph has a loop", current.name)
            visited.add(current.name)
            ordered.append(current)
            if current.bl_idname == "AFNodeEnd":
                break
            current = _first_output_node(current, "Flow Out")
        if not ordered or ordered[-1].bl_idname != "AFNodeEnd":
            raise FlowExecutionError("AF_E009", "Start node cannot reach End node")
        flow_entries = [{"node": node, "group_path": []} for node in ordered]
        self.flow_repeat_pairs, total_steps = self._compile_repeat_metadata(
            flow_entries,
            start.name,
            lambda entry: self._flow_node_step_cost(entry["node"]),
        )
        self.flow_subflow_plans, subflow_steps = self._compile_subflow_metadata(flow_entries, start.name)
        self.flow_branch_plans, branch_steps = self._compile_branch_metadata(flow_entries, start.name)
        self.nodes_in_order = ordered
        self.settings.total_step_count = int(total_steps) + int(subflow_steps) + int(branch_steps)

    def _flow_entry_identity(self, node, group_path=None):
        return f"{self._group_path_key(group_path)}::{self._node_identity(node)}"

    def _collect_group_linear_flow_entries(self, group_node, parent_group_path=None, visited=None):
        group_tree = getattr(group_node, "group_tree", None)
        if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
            return []

        group_inputs = self._find_task_group_nodes(group_tree, "NodeGroupInput")
        group_outputs = self._find_task_group_nodes(group_tree, "NodeGroupOutput")
        if len(group_inputs) != 1 or len(group_outputs) != 1:
            return []

        flow_socket = self._find_single_group_flow_socket(group_inputs[0], "outputs")
        if flow_socket is None:
            return []

        start_node = _first_output_node(group_inputs[0], flow_socket.name)
        if start_node is None:
            return []

        group_path = list(parent_group_path or [])
        group_path.append(self._make_step_ref(group_node))
        return self._collect_linear_flow_entries(start_node, {"NodeGroupOutput"}, group_path, visited)

    def _collect_linear_flow_entries(self, start_node, stop_node_types, group_path=None, visited=None):
        entries = []
        current = start_node
        active_group_path = list(group_path or [])
        visited_identities = visited if visited is not None else set()

        while current is not None:
            current_identity = self._flow_entry_identity(current, active_group_path)
            if current_identity in visited_identities:
                raise FlowExecutionError("AF_E009", "Flow graph has a loop", current.name)
            visited_identities.add(current_identity)

            entries.append(
                {
                    "node": current,
                    "group_path": [dict(item) for item in active_group_path],
                }
            )
            if current.bl_idname in stop_node_types:
                break

            if current.bl_idname == "AFNodeGroup":
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
