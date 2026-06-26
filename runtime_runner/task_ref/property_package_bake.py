import copy
import uuid

import bpy

from ...runtime_core.constants import (
    PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE,
    PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_TARGET,
    FlowExecutionError,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    STATUS_PRECHECK,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
)
from ...node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME
from ...runtime_flow.helpers import _find_single_from_input_socket, _first_output_node
from ...runtime_property.packages import _iter_property_package_entries as _iter_property_package_entries_impl
from ...runtime_task_ref.helpers import (
    _make_property_package_bake_task_ref_payload as _make_property_package_bake_task_ref_payload_impl,
    _manual_predict_property_package_bake_targets as _manual_predict_property_package_bake_targets_impl,
    _predict_property_package_bake_targets_resilient as _predict_property_package_bake_targets_resilient_impl,
)
from ...runtime_scene.objects import _dedup_obj_items as _dedup_obj_items_impl


class RuntimeTaskRefPropertyPackageBakeMixin:
    def _use_lightweight_property_package_bake_prediction(self):
        if bool(getattr(self, "_lightweight_property_package_bake_prediction", False)):
            return True
        runtime_status = str(getattr(self, "status", "") or "").strip().upper()
        if runtime_status == STATUS_PRECHECK:
            return True
        run_mode = str(getattr(getattr(self, "settings", None), "run_mode", "NORMAL") or "NORMAL").strip().upper()
        return run_mode == "FLOW_TEST"

    def _lightweight_property_package_bake_predicted_targets(self, record_node_name="", reason=""):
        return {
            "predicted_object_items": [],
            "predicted_component_paths": [],
            "record_node_names": [str(record_node_name or "")] if str(record_node_name or "").strip() else [],
            "object_scope_mode": "DYNAMIC",
            "prediction_skipped": True,
            "prediction_reason": str(reason or "lightweight_property_package_bake_prediction"),
        }

    def _make_property_package_bake_task_ref_payload(
        self,
        *,
        node,
        owner_tree_name,
        start_tree_name,
        start_node_name,
        frame_start,
        frame_end,
        bake_asset_id,
        action_name,
        predicted_targets,
        preview_degraded=False,
        record_tree_name="",
        record_node_name="",
        record_group_path=None,
        ref_role=PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_TARGET,
    ):
        return _make_property_package_bake_task_ref_payload_impl(
            node,
            owner_tree_name,
            start_tree_name,
            start_node_name,
            frame_start,
            frame_end,
            bake_asset_id,
            action_name,
            predicted_targets,
            preview_degraded=preview_degraded,
            record_tree_name=record_tree_name,
            record_node_name=record_node_name,
            record_group_path=record_group_path,
            ref_role=ref_role,
            task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
            dedup_obj_items=self._dedup_obj_items,
        )

    def _manual_predict_property_package_bake_targets(self, start_tree, start_node_name, scene, owner_node_name):
        return _manual_predict_property_package_bake_targets_impl(
            start_tree,
            start_node_name,
            scene,
            owner_node_name,
            flow_runner_cls=self.__class__,
            find_single_from_input_socket=_find_single_from_input_socket,
            first_output_node=_first_output_node,
            collect_predicted_items_from_property_package=self._collect_predicted_items_from_property_package,
            dedup_obj_items=_dedup_obj_items_impl,
        )

    def _predict_property_package_bake_targets_resilient(self, start_tree, start_node_name, scene, owner_node_name):
        return _predict_property_package_bake_targets_resilient_impl(
            start_tree,
            start_node_name,
            scene,
            owner_node_name,
            flow_runner_cls=self.__class__,
            manual_predict_property_package_bake_targets=self._manual_predict_property_package_bake_targets,
        )

    def _collect_predicted_items_from_property_package(
        self,
        property_package,
        owner_node_name,
        predicted_by_id,
        predicted_component_paths,
    ):
        package_entries = _iter_property_package_entries_impl(
            property_package,
            owner_node_name,
            allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_ROLE_TARGET},
            allow_scopes={PROPERTY_PACKAGE_SCOPE_MODIFIER, PROPERTY_PACKAGE_SCOPE_OBJECT},
            validate_property_package=self._validate_property_package,
            is_composite_property_package=self._is_composite_property_package,
            clone_property_package=self._clone_property_package,
            flow_execution_error_cls=FlowExecutionError,
        )
        for entry in package_entries:
            for item in list(entry.get("items", [])):
                object_id = int(item.get("object_id", 0) or 0)
                object_name = str(item.get("object_name", "") or "").strip()
                if object_id or object_name:
                    predicted_by_id[object_id or object_name] = {
                        "id": int(object_id),
                        "name": object_name,
                        "uuid": str(item.get("object_uuid", "") or item.get("uuid", "") or ""),
                    }
                component_path = str(item.get("component_path", "") or "").strip()
                if component_path:
                    predicted_component_paths.add(component_path)

    def _resolve_property_package_bake_record_start(self, node):
        current = node
        active_group_path = list(getattr(self, "current_group_path", []) or [])
        visited = set()
        while current is not None:
            current_tree_name = str(getattr(getattr(current, "id_data", None), "name", "") or "")
            current_name = str(getattr(current, "name", "") or "")
            current_key = (current_tree_name, current_name, tuple(str(item) for item in active_group_path))
            if current_key in visited:
                raise FlowExecutionError("AF_E009", "Property Package Bake record flow has a loop", node.name)
            visited.add(current_key)
            if str(getattr(current, "bl_idname", "") or "") == "AFNodeStart":
                return {
                    "tree_name": current_tree_name,
                    "start_node_name": current_name,
                }
            flow_input = getattr(getattr(current, "inputs", None), "get", lambda _name: None)("Flow In")
            if flow_input is None:
                raise FlowExecutionError("AF_E009", "Record Property Package cannot reach Start", node.name)
            upstream_node, upstream_socket = _find_single_from_input_socket(flow_input)
            if upstream_node is None:
                raise FlowExecutionError("AF_E011", "Record Property Package is not connected to Start", node.name)
            if str(getattr(upstream_node, "bl_idname", "") or "") == "NodeGroupInput":
                upstream_node, upstream_socket, parent_group_path = self._resolve_group_input_source(
                    upstream_node,
                    upstream_socket,
                    active_group_path,
                )
                if upstream_node is None:
                    raise FlowExecutionError("AF_E009", "Record Property Package cannot resolve parent Start", node.name)
                active_group_path = list(parent_group_path or [])
            current = upstream_node

        raise FlowExecutionError("AF_E009", "Record Property Package cannot reach Start", node.name)

    def _collect_property_package_bake_record_predicted_targets(self, node):
        if self._use_lightweight_property_package_bake_prediction():
            return self._lightweight_property_package_bake_predicted_targets(
                str(getattr(node, "name", "") or ""),
                "precheck_or_flow_test",
            )
        property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
        if property_package is None:
            raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
        predicted_by_id = {}
        predicted_component_paths = set()
        prediction_dynamic = False
        try:
            self._collect_predicted_items_from_property_package(
                property_package,
                node.name,
                predicted_by_id,
                predicted_component_paths,
            )
        except FlowExecutionError:
            raise
        except Exception:
            prediction_dynamic = True
        predicted_items = _dedup_obj_items_impl(list(predicted_by_id.values()), "NAME_ASC")
        return {
            "predicted_object_items": predicted_items,
            "predicted_component_paths": sorted(predicted_component_paths),
            "record_node_names": [str(getattr(node, "name", "") or "")],
            "object_scope_mode": "DYNAMIC" if prediction_dynamic else "STATIC",
        }

    def _normalize_property_package_bake_record_group_path(self, active_group_path, start_tree_name, owner_tree_name, owner_node_name):
        normalized_path = [dict(item) for item in list(active_group_path or [])]
        if not normalized_path:
            return []

        start_tree_name = str(start_tree_name or "").strip()
        owner_tree_name = str(owner_tree_name or "").strip()
        if start_tree_name and owner_tree_name and start_tree_name == owner_tree_name:
            return []

        for index, group_ref in enumerate(normalized_path):
            try:
                group_node = self._resolve_step_ref(group_ref, owner_node_name)
            except FlowExecutionError:
                continue
            group_tree = getattr(group_node, "group_tree", None)
            if group_tree is None or getattr(group_tree, "bl_idname", "") != "AFNodeTreeType":
                continue
            group_tree_name = str(getattr(group_tree, "name", "") or "").strip()
            if group_tree_name != start_tree_name:
                continue
            return [dict(item) for item in normalized_path[index + 1 :]]

        return normalized_path

    def _build_record_property_package_task_ref(self, node):
        resolved_start = self._resolve_property_package_bake_record_start(node)
        owner_tree_name = str(getattr(getattr(node, "id_data", None), "name", self.node_tree.name) or self.node_tree.name)
        start_tree_name = str(resolved_start.get("tree_name", "") or owner_tree_name)
        record_group_path = self._normalize_property_package_bake_record_group_path(
            getattr(self, "current_group_path", []),
            start_tree_name,
            owner_tree_name,
            str(getattr(node, "name", "") or ""),
        )
        predicted_targets = self._collect_property_package_bake_record_predicted_targets(node)
        frame_start = int(getattr(self.scene, "frame_start", 1))
        frame_end = int(getattr(self.scene, "frame_end", frame_start))
        bake_asset_id = self._ensure_record_property_package_asset_id(node)
        action_name = self._property_package_bake_action_name_from_task_ref(
            {
                "bake_asset_id": bake_asset_id,
                "source_tree_name": owner_tree_name,
                "source_node": str(getattr(node, "name", "") or ""),
            }
        )
        task_ref = self._make_property_package_bake_task_ref_payload(
            node=node,
            owner_tree_name=owner_tree_name,
            start_tree_name=start_tree_name,
            start_node_name=str(resolved_start.get("start_node_name", "") or ""),
            frame_start=frame_start,
            frame_end=frame_end,
            bake_asset_id=bake_asset_id,
            action_name=action_name,
            predicted_targets=predicted_targets,
            record_tree_name=owner_tree_name,
            record_node_name=str(getattr(node, "name", "") or ""),
            record_group_path=record_group_path,
            ref_role=PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE,
        )
        return self._embed_task_ref_status_payload(node, task_ref)

    def _ensure_record_property_package_asset_id(self, node):
        bake_asset_id = str(getattr(node, "record_asset_id", "") or "").strip()
        if bake_asset_id:
            return bake_asset_id
        bake_asset_id = uuid.uuid4().hex
        try:
            node.record_asset_id = bake_asset_id
        except Exception:
            pass
        return bake_asset_id

    def _predict_property_package_bake_targets(self, start_tree, start_node_name, owner_node_name):
        child_runner = self.__class__(
            start_tree,
            self.scene,
            ui_context=dict(self.ui_context or {}),
            start_node_name=str(start_node_name or ""),
            auto_follow=False,
        )
        child_runner._compile_linear_flow()
        predicted_by_id = {}
        predicted_component_paths = set()
        record_node_names = []
        prediction_dynamic = False

        for index, flow_node in enumerate(list(getattr(child_runner, "nodes_in_order", []) or [])):
            if str(getattr(flow_node, "bl_idname", "") or "") != "AFNodeRecordPropertyPackage":
                continue
            if bool(getattr(flow_node, "mute", False)):
                continue
            record_node_names.append(str(getattr(flow_node, "name", "") or ""))
            previous_group_path = list(getattr(child_runner, "current_group_path", []) or [])
            child_runner.current_group_path = child_runner._flow_group_path_at(index)
            try:
                property_package = child_runner._get_linked_output(flow_node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
                if property_package is None:
                    prediction_dynamic = True
                    continue
                package_entries = _iter_property_package_entries_impl(
                    property_package,
                    owner_node_name,
                    allow_roles={PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_ROLE_TARGET},
                    allow_scopes={PROPERTY_PACKAGE_SCOPE_MODIFIER, PROPERTY_PACKAGE_SCOPE_OBJECT},
                    validate_property_package=self._validate_property_package,
                    is_composite_property_package=self._is_composite_property_package,
                    clone_property_package=self._clone_property_package,
                    flow_execution_error_cls=FlowExecutionError,
                )
                for entry in package_entries:
                    for item in list(entry.get("items", [])):
                        object_id = int(item.get("object_id", 0) or 0)
                        object_name = str(item.get("object_name", "") or "").strip()
                        if object_id or object_name:
                            predicted_by_id[object_id or object_name] = {
                                "id": int(object_id),
                                "name": object_name,
                                "uuid": str(item.get("object_uuid", "") or item.get("uuid", "") or ""),
                            }
                        component_path = str(item.get("component_path", "") or "").strip()
                        if component_path:
                            predicted_component_paths.add(component_path)
            except Exception:
                prediction_dynamic = True
            finally:
                child_runner.current_group_path = previous_group_path

        predicted_items = _dedup_obj_items_impl(list(predicted_by_id.values()), "NAME_ASC")
        return {
            "predicted_object_items": predicted_items,
            "predicted_component_paths": sorted(predicted_component_paths),
            "record_node_names": record_node_names,
            "object_scope_mode": "DYNAMIC" if prediction_dynamic else "STATIC",
        }

    def _resolve_property_package_bake_source_task_ref(self, node):
        source_ref = self._get_linked_output(node, "Task Ref", "task_ref")
        if source_ref is None:
            raise FlowExecutionError("AF_E011", "Task Ref input is not linked", node.name)
        if not isinstance(source_ref, dict):
            raise FlowExecutionError("AF_E011", "Task Ref payload is invalid", node.name)
        source_ref = self._raise_if_invalid_task_ref(source_ref, node.name)
        if str(source_ref.get("task_kind", "") or "") != TASK_KIND_PROPERTY_PACKAGE_BAKE:
            raise FlowExecutionError("AF_E011", "Task Ref is not a Property Package task reference", node.name)
        start_tree_name = str(source_ref.get("start_tree_name", "") or "").strip()
        start_node_name = str(source_ref.get("start_node_name", "") or "").strip()
        record_tree_name = str(source_ref.get("record_tree_name", "") or source_ref.get("source_tree_name", "") or "").strip()
        record_node_name = str(source_ref.get("record_node_name", "") or source_ref.get("source_node", "") or "").strip()
        if not start_tree_name or not start_node_name or not record_tree_name or not record_node_name:
            raise FlowExecutionError("AF_E011", "Property Package source Task Ref is invalid", node.name)
        return source_ref

    def _build_property_package_bake_task_ref(self, node):
        source_ref = self._resolve_property_package_bake_source_task_ref(node)
        start_tree_name = str(source_ref.get("start_tree_name", "") or "")
        start_node_name = str(source_ref.get("start_node_name", "") or "")
        record_tree_name = str(source_ref.get("record_tree_name", "") or source_ref.get("source_tree_name", "") or "")
        record_node_name = str(source_ref.get("record_node_name", "") or source_ref.get("source_node", "") or "")
        record_group_path = copy.deepcopy(list(source_ref.get("record_group_path", []) or []))
        start_tree = bpy.data.node_groups.get(start_tree_name)
        if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E011", f"Start tree '{start_tree_name}' was not found", node.name)
        record_tree = bpy.data.node_groups.get(record_tree_name)
        if record_tree is None or getattr(record_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E011", f"Record tree '{record_tree_name}' was not found", node.name)
        record_node = getattr(getattr(record_tree, "nodes", None), "get", lambda _name: None)(record_node_name)
        if record_node is None or getattr(record_node, "bl_idname", "") != "AFNodeRecordPropertyPackage":
            raise FlowExecutionError("AF_E011", f"Record Property Package node '{record_node_name}' was not found", node.name)
        frame_start = self._input_int(node, "Frame Start", int(getattr(self.scene, "frame_start", 1)))
        frame_end = self._input_int(node, "Frame End", int(getattr(self.scene, "frame_end", frame_start)))
        predicted_targets = {
            "predicted_object_items": list(source_ref.get("predicted_object_items", []) or []),
            "predicted_component_paths": list(source_ref.get("predicted_component_paths", []) or []),
            "record_node_names": list(source_ref.get("record_node_names", [record_node_name]) or [record_node_name]),
            "object_scope_mode": str(source_ref.get("object_scope_mode", "DYNAMIC") or "DYNAMIC"),
            "prediction_skipped": bool(source_ref.get("prediction_skipped", False)),
            "prediction_reason": str(source_ref.get("prediction_reason", "") or ""),
        }
        bake_asset_id = str(source_ref.get("bake_asset_id", "") or "").strip()
        if not bake_asset_id:
            bake_asset_id = self._ensure_record_property_package_asset_id(record_node)
        action_name = str(source_ref.get("action_name", "") or "").strip()
        if not action_name:
            action_name = self._property_package_bake_action_name_from_task_ref(
                {
                    "bake_asset_id": bake_asset_id,
                    "source_tree_name": record_tree_name,
                    "source_node": record_node_name,
                }
            )
        task_ref = self._make_property_package_bake_task_ref_payload(
            node=node,
            owner_tree_name=getattr(getattr(node, "id_data", None), "name", self.node_tree.name),
            start_tree_name=start_tree_name,
            start_node_name=start_node_name,
            frame_start=frame_start,
            frame_end=frame_end,
            bake_asset_id=bake_asset_id,
            action_name=action_name,
            predicted_targets=predicted_targets,
            record_tree_name=record_tree_name,
            record_node_name=record_node_name,
            record_group_path=record_group_path,
            ref_role=PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_TARGET,
        )
        return self._embed_task_ref_status_payload(node, task_ref)


__all__ = ["RuntimeTaskRefPropertyPackageBakeMixin"]
