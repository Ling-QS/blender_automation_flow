import uuid

from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_SCOPE_KIND_MIXED,
    TASK_PLAN_KIND,
)
from ...runtime_math.values import _identity_matrix_payload, _identity_rotation_payload
from ...runtime_persistence.serialization import (
    _deserialize_runtime_state_value,
    _serialize_runtime_state_value,
)
from ...runtime_property.api import _property_package_item_count, _validate_property_package
from ...runtime_property.definitions import (
    _iter_property_assignment_entries,
    _make_empty_property_assignment,
    _make_empty_property_definition,
    _property_definition_has_content,
    _validate_property_assignment,
    _validate_property_definition,
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
from ...runtime_task_ref.refs import _invalid_task_ref_issue


class RuntimeOutputsMixin:
    def _output_source_node_name(self, source_node):
        if source_node is None:
            return ""
        if hasattr(source_node, "name"):
            return str(getattr(source_node, "name", "") or "")
        return str(source_node or "")

    def _output_source_tree_name(self, source_node):
        tree = getattr(source_node, "id_data", None) if source_node is not None else None
        tree_name = str(getattr(tree, "name", "") or getattr(tree, "name_full", "") or "")
        if tree_name:
            return tree_name
        return str(getattr(getattr(self, "node_tree", None), "name", "") or "")

    def _make_invalid_task_ref_output(self, source_node, error_code="AF_E011", error_message="Task Ref is invalid"):
        if source_node is not None and hasattr(self, "_make_invalid_task_ref_payload"):
            try:
                return self._make_invalid_task_ref_payload(
                    source_node,
                    FlowExecutionError(
                        str(error_code or "AF_E011"),
                        str(error_message or "Task Ref is invalid"),
                        self._output_source_node_name(source_node),
                    ),
                )
            except Exception:
                pass

        source_node_name = self._output_source_node_name(source_node)
        frame_start = int(getattr(getattr(self, "scene", None), "frame_start", 0) or 0)
        frame_end = int(getattr(getattr(self, "scene", None), "frame_end", frame_start) or frame_start)
        report = {
            "status": "INVALID",
            "task_kind": "",
            "object_count": 0,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "error_code": str(error_code or "AF_E011"),
            "error_message": str(error_message or "Task Ref is invalid"),
        }
        return {
            "task_kind": "",
            "task_uid": str(uuid.uuid4()),
            "source_node": source_node_name,
            "source_tree_name": self._output_source_tree_name(source_node),
            "status": "INVALID",
            "report": report,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
        }

    def _make_invalid_task_plan_output(self, source_node, error_code="AF_E011", error_message="Task Plan is invalid"):
        source_node_name = self._output_source_node_name(source_node)
        return {
            "plan_kind": "",
            "plan_uid": str(uuid.uuid4()),
            "output_node": source_node_name,
            "output_tree_name": self._output_source_tree_name(source_node),
            "output_ref": {},
            "step_refs": [],
            "step_names": [],
            "step_count": 0,
            "repeat_pairs": {},
            "subflow_plans": {},
            "branch_plans": {},
            "report": {
                "status": "INVALID",
                "error_code": str(error_code or "AF_E011"),
                "error_message": str(error_message or "Task Plan is invalid"),
            },
        }

    def _make_invalid_task_handle_output(self, source_node, error_code="AF_E011", error_message="Task Handle is invalid"):
        return {
            "task_id": "",
            "task_uid": "",
            "task_kind": "",
            "status": "INVALID",
            "skipped": False,
            "node_name": self._output_source_node_name(source_node),
            "started_at": 0.0,
            "finished_at": 0.0,
            "report": {
                "status": "INVALID",
                "error_code": str(error_code or "AF_E011"),
                "error_message": str(error_message or "Task Handle is invalid"),
            },
        }

    def _typed_empty_output_value(self, output_key, source_node=None):
        output_key = str(output_key or "")
        source_node_name = self._output_source_node_name(source_node)
        if output_key == "bool_value":
            return False
        if output_key in {"int_value", "frame", "frame_start", "frame_end", "count"}:
            return 0
        if output_key in {"float_value", "float_x", "float_y", "float_z"}:
            return 0.0
        if output_key in {"string_value", "status"}:
            return ""
        if output_key == "vector_value":
            return (0.0, 0.0, 0.0)
        if output_key == "rotation_value":
            return _identity_rotation_payload()
        if output_key == "matrix_value":
            return _identity_matrix_payload()
        if output_key == "display_type_value":
            return "TEXTURED"
        if output_key == "object_interaction_mode_value":
            return "OBJECT"
        if output_key == "rotation_mode_value":
            return "XYZ"
        if output_key == "viewport_shading_mode_value":
            return "SOLID"
        if output_key == "collection_list":
            return {"items": [], "count": 0}
        if output_key == "object_list":
            return {"items": [], "count": 0, "sort_mode": "NAME_ASC"}
        if output_key == "property_definition":
            return _make_empty_property_definition(source_node_name)
        if output_key == "property_assignment":
            return _make_empty_property_assignment(source_node_name)
        if output_key == "property_package":
            if hasattr(self, "_make_empty_composite_property_package"):
                return self._make_empty_composite_property_package(source_node_name)
            return {
                "package_role": PROPERTY_PACKAGE_ROLE_COMPOSITE,
                "scope_kind": PROPERTY_SCOPE_KIND_MIXED,
                "source_node": source_node_name,
                "entries": [],
                "metadata": {
                    "entry_count": 0,
                    "count": 0,
                    "object_count": 0,
                    "property_definition": _make_empty_property_definition(source_node_name),
                },
            }
        if output_key == "report":
            return {}
        if output_key == "task_ref":
            return self._make_invalid_task_ref_output(source_node)
        if output_key == "task_plan":
            return self._make_invalid_task_plan_output(source_node)
        if output_key == "task_handle":
            return self._make_invalid_task_handle_output(source_node)
        return None

    def _normalize_output_value(self, output_key, value, source_node=None):
        if value is not None:
            return value
        return self._typed_empty_output_value(output_key, source_node)

    def _socket_supports_output_key(self, socket, output_key):
        if socket is None:
            return False
        output_key = str(output_key or "")
        socket_token = self._socket_cache_token(socket)
        cache_key = (socket_token, output_key)
        cache = getattr(self, "_socket_output_key_support_cache", None)
        if cache is not None and cache_key in cache:
            return bool(cache[cache_key])
        socket_keys = set(self._socket_output_keys(socket))
        result = False
        if output_key in socket_keys:
            result = True
        elif output_key == "string_value" and "status" in socket_keys:
            result = True
        elif output_key == "status" and "string_value" in socket_keys:
            result = True
        if cache is not None:
            cache[cache_key] = bool(result)
        return result

    def _node_supports_output_key(self, node, output_key):
        if node is None:
            return False
        output_key = str(output_key or "")
        node_token = self._node_cache_token(node)
        cache_key = (node_token, output_key)
        cache = getattr(self, "_node_output_key_support_cache", None)
        if cache is not None and cache_key in cache:
            return bool(cache[cache_key])
        result = False
        for socket in getattr(node, "outputs", []):
            if self._socket_supports_output_key(socket, output_key):
                result = True
                break
        if cache is not None:
            cache[cache_key] = bool(result)
        return result

    def _has_effective_output_content(self, output_key, value, source_node=None):
        output_key = str(output_key or "")
        if value is None:
            return False
        if output_key in {"task_ref", "task_plan", "task_handle"}:
            return self._is_valid_reference_payload(output_key, value)
        if output_key in {"collection_list", "object_list"}:
            try:
                return int(dict(value or {}).get("count", 0) or 0) > 0
            except Exception:
                return False
        if output_key == "property_definition":
            try:
                node_name = self._output_source_node_name(source_node) or "Property Definition"
                return bool(_property_definition_has_content(_validate_property_definition(value, node_name), node_name))
            except Exception:
                return False
        if output_key == "property_assignment":
            try:
                node_name = self._output_source_node_name(source_node) or "Property Assignment"
                return len(_iter_property_assignment_entries(_validate_property_assignment(value, node_name), node_name)) > 0
            except Exception:
                return False
        if output_key == "property_package":
            try:
                node_name = self._output_source_node_name(source_node) or "Property Package"
                return int(_property_package_item_count(_validate_property_package(value, node_name))) > 0
            except Exception:
                return False
        if output_key == "report":
            return bool(dict(value or {}))
        if output_key in {"string_value", "status"}:
            return bool(str(value or ""))
        return True

    def _is_valid_reference_payload(self, output_key, value):
        output_key = str(output_key or "")
        if output_key == "task_ref":
            return isinstance(value, dict) and _invalid_task_ref_issue(value) is None
        if output_key == "task_plan":
            return isinstance(value, dict) and str(value.get("plan_kind", "") or "") == TASK_PLAN_KIND
        if output_key == "task_handle":
            return (
                isinstance(value, dict)
                and str(value.get("status", "") or "").strip().upper() != "INVALID"
                and bool(str(value.get("task_id", "") or "").strip())
            )
        return False

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

    def _read_boolean_toggle_state(self, node, group_path=None):
        return self._read_boolean_state(
            node,
            "BOOLEAN_TOGGLE_STATE",
            bool(getattr(node, "default_value", False)),
            group_path=group_path,
        )

    def _write_boolean_toggle_state(self, node, value, group_path=None):
        self._write_boolean_state(node, "BOOLEAN_TOGGLE_STATE", bool(value), group_path=group_path)

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
        cache_payload[cache_key] = _serialize_runtime_state_value(self._normalize_output_value(key, value, node))
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
        normalized_value = self._normalize_output_value(key, value, node)
        active_group_path = list(self.current_group_path)
        self.vars[self._node_output_key(node, key, active_group_path)] = normalized_value
        self._persist_status_report_output(node, key, normalized_value, active_group_path)
        if (
            getattr(getattr(node, "id_data", None), "name", "") == self.node_tree.name
            and not active_group_path
            and not self._current_property_context_cache_key()
        ):
            self.vars[self._legacy_node_output_key(node, key)] = normalized_value

    def _get_output(self, node, key, group_path=None, normalize=True):
        unique_key = self._node_output_key(node, key, group_path)
        if unique_key in self.vars:
            value = self.vars.get(unique_key)
            return self._normalize_output_value(key, value, node) if normalize else value
        active_group_path = self.current_group_path if group_path is None else group_path
        if not active_group_path and not self._current_property_context_cache_key():
            legacy_value = self.vars.get(self._legacy_node_output_key(node, key))
            if legacy_value is not None:
                return self._normalize_output_value(key, legacy_value, node) if normalize else legacy_value
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeFlowToggle" and key == "bool_value":
            return self._read_flow_toggle_state(node, active_group_path)
        persisted_value = self._read_persisted_status_report_output(node, key, active_group_path)
        if persisted_value is not None:
            return self._normalize_output_value(key, persisted_value, node) if normalize else persisted_value
        if normalize and self._node_supports_output_key(node, key):
            return self._normalize_output_value(key, None, node)
        return None

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
        self._context_reduce_cache.clear()
        self._property_context_dependency_cache.clear()

    def _bpy_data_node_groups(self):
        import bpy

        return bpy.data.node_groups


__all__ = ["RuntimeOutputsMixin"]
