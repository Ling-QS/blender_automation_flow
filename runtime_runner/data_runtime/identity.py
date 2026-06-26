import bpy

from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES,
    PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES,
)
from ...runtime_flow.helpers import _find_single_from_input_socket, _node_bl_idname, _node_name, _node_tree_name


class RuntimeIdentityMixin:
    def _node_tree_runtime_revision_value(self, node_tree):
        if node_tree is None:
            return 0
        try:
            from ...node_system.tree import node_tree_runtime_revision
        except Exception:
            return 0
        try:
            return int(node_tree_runtime_revision(node_tree) or 0)
        except Exception:
            return 0

    def _node_cache_token(self, node):
        if node is None:
            return None
        try:
            if hasattr(node, "as_pointer"):
                return int(node.as_pointer())
        except Exception:
            pass
        try:
            return id(node)
        except Exception:
            return None

    def _socket_cache_token(self, socket):
        if socket is None:
            return None
        try:
            if hasattr(socket, "as_pointer"):
                return int(socket.as_pointer())
        except Exception:
            pass
        try:
            return id(socket)
        except Exception:
            return None

    def _node_identity(self, node):
        if node is getattr(self, "_last_node_identity_source", None):
            return str(getattr(self, "_last_node_identity_value", "") or "")
        cache = getattr(self, "_node_identity_cache", None)
        cache_token = self._node_cache_token(node)
        if cache is not None and cache_token is not None:
            cached = cache.get(cache_token)
            if cached is not None:
                self._last_node_identity_source = node
                self._last_node_identity_value = cached
                return str(cached)
        tree_name = _node_tree_name(node)
        node_name = _node_name(node)
        if not node_name:
            cache_fallback = cache_token if cache_token is not None else "unknown"
            node_name = f"<invalid-node:{cache_fallback}>"
        value = f"{tree_name}::{node_name}"
        self._last_node_identity_source = node
        self._last_node_identity_value = value
        if cache is not None and cache_token is not None:
            cache[cache_token] = value
        return value

    def _data_eval_token(self, node, group_path=None):
        active_group_path = self.current_group_path if group_path is None else group_path
        node_token = self._node_cache_token(node)
        if node_token is None:
            node_token = self._node_identity(node)
        return (
            node_token,
            self._group_path_key(active_group_path),
            self._current_property_context_cache_key(),
        )

    def _group_path_signature(self, group_path):
        if group_path is getattr(self, "_last_group_path_signature_source", None):
            return tuple(getattr(self, "_last_group_path_signature_value", ()) or ())
        signature = tuple(
            (
                str(item.get("tree_name", "") or ""),
                str(item.get("node_name", "") or ""),
            )
            for item in list(group_path or [])
            if isinstance(item, dict)
        )
        self._last_group_path_signature_source = group_path
        self._last_group_path_signature_value = signature
        return signature

    def _group_path_key(self, group_path):
        if group_path is getattr(self, "_last_group_path_key_source", None):
            return str(getattr(self, "_last_group_path_key_value", "") or "")
        signature = self._group_path_signature(group_path)
        if not signature:
            return ""
        cache = getattr(self, "_group_path_key_cache", None)
        if cache is not None:
            cached = cache.get(signature)
            if cached is not None:
                self._last_group_path_key_source = group_path
                self._last_group_path_key_value = cached
                return str(cached)
        value = " > ".join(f"{tree_name}::{node_name}" for tree_name, node_name in signature)
        self._last_group_path_key_source = group_path
        self._last_group_path_key_value = value
        if cache is not None:
            cache[signature] = value
        return value

    def _current_property_context_cache_key(self):
        context = getattr(self, "current_property_context", None)
        if not isinstance(context, dict) or not context:
            return ""
        if context is getattr(self, "_last_property_context_key_source", None):
            return str(getattr(self, "_last_property_context_key_value", "") or "")
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
        value = "|".join(
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
        self._last_property_context_key_source = context
        self._last_property_context_key_value = value
        return value

    def _data_node_depends_on_property_context(self, node, _visited=None):
        node_type = _node_bl_idname(node)
        if node_type not in self.DATA_NODE_TYPES:
            return False
        if node_type in PROPERTY_CONTEXT_DEPENDENT_DATA_NODE_TYPES:
            return True
        if node_type in PROPERTY_CONTEXT_STATIC_DATA_NODE_TYPES:
            return False

        group_path_key = self._group_path_key(self.current_group_path)
        cache_key = (
            self._node_identity(node),
            group_path_key,
            self._node_tree_runtime_revision_value(getattr(node, "id_data", None)),
        )
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
        resolved_type = _node_bl_idname(resolved_node)
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
        active_group_path = self.current_group_path if group_path is None else group_path
        path_key = self._group_path_key(active_group_path)
        context_key = self._current_property_context_cache_key()
        node_type = _node_bl_idname(node)
        if node_type in self.DATA_NODE_TYPES and not self._data_node_depends_on_property_context(node):
            context_key = ""
        cache_key = (self._node_cache_token(node), path_key, str(key or ""), context_key)
        cache = getattr(self, "_node_output_key_cache", None)
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return str(cached)
        if context_key:
            value = f"{self._node_identity(node)}|{path_key}|ctx:{context_key}.{key}"
        else:
            value = f"{self._node_identity(node)}|{path_key}.{key}"
        if cache is not None:
            cache[cache_key] = value
        return value

    def _legacy_node_output_key(self, node, key):
        cache_key = (self._node_cache_token(node), str(key or ""))
        cache = getattr(self, "_legacy_node_output_key_cache", None)
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return str(cached)
        value = f"{_node_name(node, '<invalid-node>')}.{key}"
        if cache is not None:
            cache[cache_key] = value
        return value

    def _make_step_ref(self, node, group_path=None):
        step_ref = {
            "tree_name": _node_tree_name(node),
            "node_name": _node_name(node),
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
        if node_tree is None or _node_bl_idname(node_tree) != "AFNodeTreeType":
            raise FlowExecutionError("AF_E009", f"Task plan tree '{tree_name}' is missing", owner_node_name)
        node = node_tree.nodes.get(node_name)
        if node is None:
            raise FlowExecutionError("AF_E009", f"Task plan step '{node_name}' is missing", owner_node_name)
        return node

    def _find_task_group_nodes(self, group_tree, node_type):
        return [node for node in group_tree.nodes if _node_bl_idname(node) == node_type]

    def _find_single_group_flow_socket(self, node, socket_collection_name):
        sockets = getattr(node, socket_collection_name, [])
        flow_sockets = [socket for socket in sockets if _node_bl_idname(socket) == "AFSocketFlow"]
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
