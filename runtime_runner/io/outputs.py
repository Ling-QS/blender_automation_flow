from ...runtime_persistence.serialization import (
    _deserialize_runtime_state_value,
    _serialize_runtime_state_value,
)
from ...runtime_state.cache import (
    _boolean_state_cache_key,
    _flow_toggle_cache_key,
    _read_flow_toggle_cache,
    _read_status_report_cache,
    _status_report_cache_key,
    _write_flow_toggle_cache,
    _write_status_report_cache,
)


class RuntimeOutputsMixin:
    def _flow_toggle_cache_key_for_node(self, node, group_path=None):
        tree = getattr(node, "id_data", None)
        tree_name = getattr(tree, "name_full", getattr(tree, "name", ""))
        return _flow_toggle_cache_key(
            tree_name,
            getattr(node, "name", ""),
            self.current_group_path if group_path is None else group_path,
        )

    def _get_flow_toggle_cache_payload(self):
        if self._flow_toggle_cache_payload is None:
            self._flow_toggle_cache_payload = _read_flow_toggle_cache(self.scene)
        return self._flow_toggle_cache_payload

    def _flush_flow_toggle_cache(self):
        if not self._flow_toggle_cache_dirty or self.scene is None:
            return
        _write_flow_toggle_cache(self.scene, self._flow_toggle_cache_payload or {})
        self._flow_toggle_cache_dirty = False

    def _read_flow_toggle_state(self, node, group_path=None):
        default_value = bool(getattr(node, "default_value", False))
        cache_payload = self._get_flow_toggle_cache_payload()
        cache_key = self._flow_toggle_cache_key_for_node(node, group_path)
        if cache_key not in cache_payload:
            return default_value
        try:
            return bool(cache_payload.get(cache_key))
        except Exception:
            return default_value

    def _write_flow_toggle_state(self, node, value, group_path=None):
        cache_payload = self._get_flow_toggle_cache_payload()
        cache_key = self._flow_toggle_cache_key_for_node(node, group_path)
        cache_payload[cache_key] = bool(value)
        self._flow_toggle_cache_dirty = True

    def _boolean_state_cache_key_for_node(self, node, state_kind, group_path=None):
        tree = getattr(node, "id_data", None)
        tree_name = getattr(tree, "name_full", getattr(tree, "name", ""))
        return _boolean_state_cache_key(
            tree_name,
            getattr(node, "name", ""),
            state_kind,
            self.current_group_path if group_path is None else group_path,
        )

    def _read_boolean_state(self, node, state_kind, default_value=False, group_path=None):
        cache_payload = self._get_flow_toggle_cache_payload()
        cache_key = self._boolean_state_cache_key_for_node(node, state_kind, group_path)
        if cache_key not in cache_payload:
            return bool(default_value)
        try:
            return bool(cache_payload.get(cache_key))
        except Exception:
            return bool(default_value)

    def _write_boolean_state(self, node, state_kind, value, group_path=None):
        cache_payload = self._get_flow_toggle_cache_payload()
        cache_key = self._boolean_state_cache_key_for_node(node, state_kind, group_path)
        cache_payload[cache_key] = bool(value)
        self._flow_toggle_cache_dirty = True

    def _status_report_cache_key_for_node(self, node, key, group_path=None):
        tree = getattr(node, "id_data", None)
        tree_name = getattr(tree, "name_full", getattr(tree, "name", ""))
        return _status_report_cache_key(
            tree_name,
            getattr(node, "name", ""),
            key,
            self.current_group_path if group_path is None else group_path,
        )

    def _should_persist_output(self, node, key):
        if self.scene is None or node is None:
            return False
        if key == "status":
            return str(getattr(node, "bl_idname", "") or "") != "AFNodeResolveTaskRef"
        if key == "report":
            return str(getattr(node, "bl_idname", "") or "") in {
                "AFNodeRunTaskPlan",
                "AFNodeRunBackgroundTaskPlan",
            }
        return False

    def _persist_status_report_output(self, node, key, value, group_path=None):
        if not self._should_persist_output(node, key):
            return
        cache_payload = self._get_status_report_cache_payload()
        cache_key = self._status_report_cache_key_for_node(node, key, group_path)
        cache_payload[cache_key] = _serialize_runtime_state_value(value)
        self._status_report_cache_dirty = True

    def _read_persisted_status_report_output(self, node, key, group_path=None):
        if not self._should_persist_output(node, key):
            return None
        cache_payload = self._get_status_report_cache_payload()
        cache_key = self._status_report_cache_key_for_node(node, key, group_path)
        if cache_key not in cache_payload:
            return None
        try:
            return _deserialize_runtime_state_value(cache_payload.get(cache_key))
        except Exception:
            return None

    def _get_status_report_cache_payload(self):
        if self._status_report_cache_payload is None:
            self._status_report_cache_payload = _read_status_report_cache(self.scene)
        return self._status_report_cache_payload

    def _flush_status_report_cache(self):
        if not self._status_report_cache_dirty or self.scene is None:
            return
        _write_status_report_cache(self.scene, self._status_report_cache_payload or {})
        self._status_report_cache_dirty = False

    def _set_output(self, node, key, value):
        active_group_path = list(self.current_group_path)
        self.vars[self._node_output_key(node, key, active_group_path)] = value
        self._persist_status_report_output(node, key, value, active_group_path)
        if (
            getattr(getattr(node, "id_data", None), "name", "") == self.node_tree.name
            and not active_group_path
            and not self._current_property_context_cache_key()
        ):
            self.vars[self._legacy_node_output_key(node, key)] = value

    def _get_output(self, node, key, group_path=None):
        unique_key = self._node_output_key(node, key, group_path)
        if unique_key in self.vars:
            return self.vars.get(unique_key)
        active_group_path = self.current_group_path if group_path is None else group_path
        if not active_group_path and not self._current_property_context_cache_key():
            legacy_value = self.vars.get(self._legacy_node_output_key(node, key))
            if legacy_value is not None:
                return legacy_value
        if str(getattr(node, "bl_idname", "") or "") == "AFNodeFlowToggle" and key == "bool_value":
            return self._read_flow_toggle_state(node, active_group_path)
        return self._read_persisted_status_report_output(node, key, active_group_path)

    def _invalidate_data_node_outputs(self):
        removable_keys = set()
        for node_group in self._bpy_data_node_groups():
            if getattr(node_group, "bl_idname", "") != "AFNodeTreeType":
                continue
            for node in getattr(node_group, "nodes", []):
                if getattr(node, "bl_idname", "") not in self.DATA_NODE_TYPES:
                    continue
                identity_prefix = f"{self._node_identity(node)}|"
                legacy_prefix = f"{node.name}."
                for key in self.vars.keys():
                    if key.startswith(identity_prefix) or key.startswith(legacy_prefix):
                        removable_keys.add(key)
        for key in removable_keys:
            self.vars.pop(key, None)
        self._geometry_attribute_cache.clear()
        self._property_context_dependency_cache.clear()

    def _bpy_data_node_groups(self):
        import bpy

        return bpy.data.node_groups


__all__ = ["RuntimeOutputsMixin"]
