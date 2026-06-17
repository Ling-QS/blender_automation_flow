import uuid

import bpy

from ...runtime_core.constants import (
    FlowExecutionError,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_ROLE_TARGET,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    PROPERTY_PACKAGE_SCOPE_OBJECT,
    TASK_KIND_AUTO_FLOW_BAKE,
)
from ...runtime_flow.helpers import _find_single_from_input_socket, _first_output_node
from ...runtime_property.packages import _iter_property_package_entries as _iter_property_package_entries_impl
from ...runtime_task_ref.helpers import (
    _make_auto_flow_bake_task_ref_payload as _make_auto_flow_bake_task_ref_payload_impl,
    _manual_predict_auto_flow_bake_targets as _manual_predict_auto_flow_bake_targets_impl,
    _predict_auto_flow_bake_targets_resilient as _predict_auto_flow_bake_targets_resilient_impl,
)
from ...runtime_scene.objects import _dedup_obj_items as _dedup_obj_items_impl


class RuntimeTaskRefAutoFlowMixin:
    def _make_auto_flow_bake_task_ref_payload(
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
    ):
        return _make_auto_flow_bake_task_ref_payload_impl(
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
            task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
            dedup_obj_items=self._dedup_obj_items,
        )

    def _manual_predict_auto_flow_bake_targets(self, start_tree, start_node_name, scene, owner_node_name):
        return _manual_predict_auto_flow_bake_targets_impl(
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

    def _predict_auto_flow_bake_targets_resilient(self, start_tree, start_node_name, scene, owner_node_name):
        return _predict_auto_flow_bake_targets_resilient_impl(
            start_tree,
            start_node_name,
            scene,
            owner_node_name,
            flow_runner_cls=self.__class__,
            manual_predict_auto_flow_bake_targets=self._manual_predict_auto_flow_bake_targets,
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

    def _resolve_start_ref(self, node):
        linked_start_ref = self._get_linked_output(node, "Start Ref", "start_ref")
        if isinstance(linked_start_ref, dict):
            tree_name = str(
                linked_start_ref.get("tree_name", "")
                or getattr(getattr(node, "id_data", None), "name", self.node_tree.name)
            )
            start_node_name = str(linked_start_ref.get("start_node_name", "") or "")
            if tree_name and start_node_name:
                return {
                    "tree_name": tree_name,
                    "start_node_name": start_node_name,
                }

        tree_name = str(getattr(getattr(node, "id_data", None), "name", self.node_tree.name) or self.node_tree.name)
        start_node_name = str(getattr(node, "target_start_name", "") or "").strip()
        if not start_node_name or start_node_name == "__NONE__":
            raise FlowExecutionError("AF_E011", "Start Ref is not set", node.name)
        return {
            "tree_name": tree_name,
            "start_node_name": start_node_name,
        }

    def _ensure_auto_flow_bake_asset_id(self, node):
        bake_asset_id = str(getattr(node, "bake_asset_id", "") or "").strip()
        if bake_asset_id:
            return bake_asset_id
        bake_asset_id = uuid.uuid4().hex
        try:
            node.bake_asset_id = bake_asset_id
        except Exception:
            pass
        return bake_asset_id

    def _predict_auto_flow_bake_targets(self, start_tree, start_node_name, owner_node_name):
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

        for flow_node in list(getattr(child_runner, "nodes_in_order", []) or []):
            if str(getattr(flow_node, "bl_idname", "") or "") != "AFNodeRecordPropertyPackage":
                continue
            if bool(getattr(flow_node, "mute", False)):
                continue
            record_node_names.append(str(getattr(flow_node, "name", "") or ""))
            try:
                property_package = child_runner._get_linked_output(flow_node, "Prop Pack", "property_package")
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

        predicted_items = _dedup_obj_items_impl(list(predicted_by_id.values()), "NAME_ASC")
        return {
            "predicted_object_items": predicted_items,
            "predicted_component_paths": sorted(predicted_component_paths),
            "record_node_names": record_node_names,
            "object_scope_mode": "DYNAMIC" if prediction_dynamic else "STATIC",
        }

    def _build_auto_flow_bake_task_ref(self, node):
        start_ref = self._resolve_start_ref(node)
        start_tree_name = str(start_ref["tree_name"])
        start_node_name = str(start_ref["start_node_name"])
        start_tree = bpy.data.node_groups.get(start_tree_name)
        if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E011", f"Start tree '{start_tree_name}' was not found", node.name)
        frame_start = self._input_int(node, "Frame Start", int(getattr(self.scene, "frame_start", 1)))
        frame_end = self._input_int(node, "Frame End", int(getattr(self.scene, "frame_end", frame_start)))
        bake_asset_id = self._ensure_auto_flow_bake_asset_id(node)
        if self._is_flow_test_mode():
            predicted_targets = {
                "predicted_object_items": [],
                "predicted_component_paths": [],
                "record_node_names": [],
                "object_scope_mode": "DYNAMIC",
                "prediction_skipped": True,
                "prediction_reason": "flow_test",
            }
        else:
            predicted_targets = self._predict_auto_flow_bake_targets_resilient(
                start_tree,
                start_node_name,
                self.scene,
                node.name,
            )
        action_name = self._auto_flow_bake_action_name_from_task_ref(
            {
                "bake_asset_id": bake_asset_id,
                "source_tree_name": getattr(getattr(node, "id_data", None), "name", self.node_tree.name),
                "source_node": node.name,
            }
        )
        task_ref = self._make_auto_flow_bake_task_ref_payload(
            node=node,
            owner_tree_name=getattr(getattr(node, "id_data", None), "name", self.node_tree.name),
            start_tree_name=start_tree_name,
            start_node_name=start_node_name,
            frame_start=frame_start,
            frame_end=frame_end,
            bake_asset_id=bake_asset_id,
            action_name=action_name,
            predicted_targets=predicted_targets,
        )
        return self._embed_task_ref_status_payload(node, task_ref)


__all__ = ["RuntimeTaskRefAutoFlowMixin"]
