import bpy

from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES,
    PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES,
)
from ...runtime_flow.helpers import _find_single_from_input_socket


class RuntimeIdentityMixin:
    def _node_identity(self, node):
        tree = getattr(node, "id_data", None)
        tree_name = getattr(tree, "name_full", getattr(tree, "name", ""))
        return f"{tree_name}::{node.name}"

    def _group_path_key(self, group_path):
        if not group_path:
            return ""
        return " > ".join(
            f"{str(item.get('tree_name', ''))}::{str(item.get('node_name', ''))}"
            for item in group_path
        )

    def _current_property_context_cache_key(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict) or not context:
            return ""
        object_item = context.get("object_item")
        object_id = ""
        object_name = ""
        if isinstance(object_item, dict):
            object_id = str(object_item.get("id", "") or "")
            object_name = str(object_item.get("name", "") or "")
        modifier_name = str(context.get("modifier_name", "") or "")
        modifier_type = str(context.get("modifier_type", "") or "")
        component_kind = str(context.get("component_kind", "") or "")
        object_index = int(context.get("object_index", 0) or 0)
        component_index = int(context.get("component_index", 0) or 0)
        return "|".join(
            (
                object_id,
                object_name,
                modifier_name,
                modifier_type,
                component_kind,
                str(object_index),
                str(component_index),
            )
        )

    def _data_node_depends_on_property_context(self, node, _visited=None):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type not in self.DATA_NODE_TYPES:
            return False
        if node_type in PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES:
            return True
        if node_type in PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES:
            return False

        group_path_key = self._group_path_key(self.current_group_path)
        cache_key = (self._node_identity(node), group_path_key)
        cached = self._property_context_dependency_cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        if _visited is None:
            _visited = set()
        if cache_key in _visited:
            return False
        _visited.add(cache_key)
        self._property_context_dependency_cache[cache_key] = False

        if node_type == "AFNodeGroup":
            if self._group_node_depends_on_property_context(node, _visited):
                self._property_context_dependency_cache[cache_key] = True
                return True

        for input_socket in getattr(node, "inputs", []):
            from_node, from_socket = _find_single_from_input_socket(input_socket)
            if from_node is None:
                continue
            if self._source_depends_on_property_context(from_node, from_socket, _visited):
                self._property_context_dependency_cache[cache_key] = True
                return True
        return False

    def _source_depends_on_property_context(self, from_node, from_socket, _visited):
        resolved_node, _resolved_socket, resolved_group_path = self._trace_output_source(
            from_node,
            from_socket,
            self.current_group_path,
        )
        if resolved_node is None:
            return False
        resolved_type = str(getattr(resolved_node, "bl_idname", "") or "")
        if resolved_type in PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES:
            return True
        if (
            resolved_type not in self.DATA_NODE_TYPES
            or resolved_type in PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES
        ):
            return False
        previous_group_path = list(self.current_group_path)
        self.current_group_path = list(resolved_group_path)
        try:
            return self._data_node_depends_on_property_context(resolved_node, _visited)
        finally:
            self.current_group_path = previous_group_path

    def _group_node_depends_on_property_context(self, node, _visited):
        for output_socket in getattr(node, "outputs", []):
            upstream_node, upstream_socket, child_group_path = self._resolve_group_output_source(
                node,
                output_socket,
                self.current_group_path,
            )
            if upstream_node is None or upstream_socket is None:
                continue
            previous_group_path = list(self.current_group_path)
            self.current_group_path = list(child_group_path)
            try:
                if self._source_depends_on_property_context(upstream_node, upstream_socket, _visited):
                    return True
            finally:
                self.current_group_path = previous_group_path
        return False

    def _node_output_key(self, node, key, group_path=None):
        path_key = self._group_path_key(self.current_group_path if group_path is None else group_path)
        context_key = self._current_property_context_cache_key()
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type in self.DATA_NODE_TYPES and not self._data_node_depends_on_property_context(node):
            context_key = ""
        if context_key:
            return f"{self._node_identity(node)}|{path_key}|ctx:{context_key}.{key}"
        return f"{self._node_identity(node)}|{path_key}.{key}"

    def _legacy_node_output_key(self, node, key):
        return f"{node.name}.{key}"

    def _make_step_ref(self, node, group_path=None):
        tree = getattr(node, "id_data", None)
        step_ref = {
            "tree_name": getattr(tree, "name", ""),
            "node_name": node.name,
        }
        if group_path:
            step_ref["group_path"] = [dict(item) for item in group_path]
        return step_ref

    def _resolve_step_ref(self, step_ref, owner_node_name):
        if not isinstance(step_ref, dict):
            raise FlowExecutionError("AF_E011", "Task Plan step reference is invalid", owner_node_name)
        tree_name = str(step_ref.get("tree_name", "") or "")
        node_name = str(step_ref.get("node_name", "") or "")
        if not tree_name or not node_name:
            raise FlowExecutionError("AF_E011", "Task Plan step reference is incomplete", owner_node_name)
        node_tree = bpy.data.node_groups.get(tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E009", f"Task plan tree '{tree_name}' is missing", owner_node_name)
        node = node_tree.nodes.get(node_name)
        if node is None:
            raise FlowExecutionError("AF_E009", f"Task plan step '{node_name}' is missing", owner_node_name)
        return node

    def _find_task_group_nodes(self, group_tree, node_type):
        return [node for node in group_tree.nodes if getattr(node, "bl_idname", "") == node_type]

    def _find_single_group_flow_socket(self, node, socket_collection_name):
        sockets = getattr(node, socket_collection_name, [])
        flow_sockets = [socket for socket in sockets if getattr(socket, "bl_idname", "") == "AFSocketFlow"]
        if len(flow_sockets) != 1:
            return None
        return flow_sockets[0]

    def _find_group_flow_socket_nodes(self, group_tree, node_type, socket_collection_name):
        matches = []
        for node in self._find_task_group_nodes(group_tree, node_type):
            flow_socket = self._find_single_group_flow_socket(node, socket_collection_name)
            if flow_socket is None:
                continue
            matches.append((node, flow_socket))
        return matches

    def _flow_group_path_at(self, index):
        try:
            parsed_index = int(index)
        except Exception:
            return []
        group_paths = getattr(self, "node_group_paths_in_order", None)
        if not isinstance(group_paths, list):
            return []
        if parsed_index < 0 or parsed_index >= len(group_paths):
            return []
        return [
            dict(item)
            for item in list(group_paths[parsed_index] or [])
            if isinstance(item, dict)
        ]


__all__ = ["RuntimeIdentityMixin"]
