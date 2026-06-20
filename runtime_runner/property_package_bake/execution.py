import copy
import os

import bpy

from ...runtime_core.constants import (
    PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE,
    STATUS_RELOADING,
    STATUS_SUCCESS,
    STATUS_WAITING,
    FlowExecutionError,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
)
from ...runtime_refs.objects import _find_object_by_name
from ...runtime_persistence.serialization import _copy_task_ref_payload
from ...runtime_state.cache import (
    _property_package_bake_action_frame_range,
    _property_package_bake_action_has_cached_data,
    _property_package_bake_action_name_from_task_ref,
)


class RuntimePropertyPackageBakeExecutionMixin:
    def _build_property_package_bake_report_base(self, task_ref, *, start_tree_name, start_node_name, frame_start, frame_end):
        return {
            "task_kind": TASK_KIND_PROPERTY_PACKAGE_BAKE,
            "start_tree_name": str(start_tree_name or ""),
            "start_node_name": str(start_node_name or ""),
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "restored_frame": bool(task_ref.get("restore_current_frame", True)),
            "bake_asset_id": str(task_ref.get("bake_asset_id", "") or ""),
            "predicted_object_items": copy.deepcopy(list(task_ref.get("predicted_object_items", []) or [])),
            "predicted_component_paths": copy.deepcopy(list(task_ref.get("predicted_component_paths", []) or [])),
            "object_scope_mode": str(task_ref.get("object_scope_mode", "STATIC") or "STATIC"),
        }

    def _import_background_property_package_bake_result(self, task_handle, payload, blend_copy_path):
        report = dict(payload.get("report") or {})
        result_blend_path = str(report.get("result_blend_path", "") or blend_copy_path or "")
        if not result_blend_path or not os.path.exists(result_blend_path):
            raise FlowExecutionError("AF_E005", "Background Property Package Bake result blend is missing", str(task_handle.get("node_name", "") or ""))

        action_name = str(report.get("action_name", "") or "")
        bake_asset_id = str(report.get("bake_asset_id", "") or "")
        if not action_name:
            action_name = _property_package_bake_action_name_from_task_ref(report)

        with bpy.data.libraries.load(result_blend_path, link=False) as (data_from, data_to):
            available_actions = set(getattr(data_from, "actions", []) or [])
            if action_name not in available_actions:
                raise FlowExecutionError("AF_E005", f"Background Property Package Bake action '{action_name}' was not found in result blend", str(task_handle.get("node_name", "") or ""))
            data_to.actions = [action_name]
        imported_actions = [action for action in list(getattr(data_to, "actions", []) or []) if action is not None]
        if not imported_actions:
            raise FlowExecutionError("AF_E005", f"Failed to import background Property Package Bake action '{action_name}'", str(task_handle.get("node_name", "") or ""))
        imported_action = imported_actions[0]

        existing_action = self._find_property_package_bake_action(bake_asset_id, action_name)
        if existing_action is not None and existing_action != imported_action:
            for obj in bpy.data.objects:
                anim_data = getattr(obj, "animation_data", None)
                if anim_data is None or getattr(anim_data, "action", None) != existing_action:
                    continue
                try:
                    anim_data.action = None
                except Exception:
                    pass
                try:
                    anim_data.action_slot = None
                except Exception:
                    pass
            try:
                existing_action.use_fake_user = False
            except Exception:
                pass
            try:
                bpy.data.actions.remove(existing_action)
            except Exception:
                pass
            if action_name and imported_action.name != action_name and bpy.data.actions.get(action_name) is None:
                try:
                    imported_action.name = action_name
                except Exception:
                    pass

        self._tag_property_package_bake_action(imported_action, report)
        rebound_items = []
        object_items = list(report.get("touched_object_items", []) or report.get("predicted_object_items", []) or [])
        slot_identifiers_by_object_name = dict(report.get("slot_identifiers_by_object_name", {}) or {})
        imported_slots_by_identifier = {
            str(getattr(slot, "identifier", "") or ""): slot
            for slot in list(getattr(imported_action, "slots", []) or [])
        }
        for obj_item in object_items:
            obj = _find_object_by_name(obj_item.get("name")) if isinstance(obj_item, dict) else None
            if obj is None and isinstance(obj_item, dict):
                obj = self._find_object_by_item(obj_item)
            if obj is None:
                continue
            try:
                anim_data = obj.animation_data_create()
                anim_data.action = imported_action
                slot_identifier = str(slot_identifiers_by_object_name.get(str(getattr(obj, "name", "") or ""), "") or "")
                slot = imported_slots_by_identifier.get(slot_identifier) if slot_identifier else None
                if slot is None:
                    slot = self._ensure_property_package_bake_action_slot(imported_action, obj)
                try:
                    anim_data.action_slot = slot
                except Exception:
                    pass
            except Exception:
                continue
            rebound_items.append(self._property_package_bake_record_obj_item(obj))
        report["action_name"] = str(getattr(imported_action, "name", action_name) or action_name)
        report["result_blend_path"] = result_blend_path
        if rebound_items:
            report["touched_object_items"] = rebound_items
        report["imported_result"] = True
        return report

    def _run_property_package_bake_once(self, start_tree, start_node_name, task_ref, frame, owner_node_name, bake_tracking=None):
        child_runner = type(self)(
            start_tree,
            self.scene,
            ui_context=dict(self.ui_context or {}),
            start_node_name=str(start_node_name or ""),
            auto_follow=False,
        )
        property_package_bake_context = {
            "task_ref": _copy_task_ref_payload(task_ref),
            "frame": int(frame),
            "owner_node_name": str(owner_node_name or ""),
            "shared_action": None,
            "target_record_tree_name": str(task_ref.get("record_tree_name", "") or ""),
            "target_record_node_name": str(task_ref.get("record_node_name", "") or ""),
            "target_record_group_path": copy.deepcopy(list(task_ref.get("record_group_path", []) or [])),
        }
        if isinstance(bake_tracking, dict):
            property_package_bake_context.update(bake_tracking)
        child_runner.property_package_bake_context = property_package_bake_context
        child_runner.start()
        unsupported_types = {
            "AFNodeTaskStep",
            "AFNodeRunTaskPlan",
            "AFNodeRunBackgroundTaskPlan",
            "AFNodeWaitForTask",
            "AFNodeDelayWait",
            "AFNodeReloadAfterTask",
        }
        for flow_node in list(getattr(child_runner, "nodes_in_order", []) or []):
            if str(getattr(flow_node, "bl_idname", "") or "") in unsupported_types:
                raise FlowExecutionError("AF_E005", f"Property Package Bake does not support '{flow_node.bl_label}'", owner_node_name)
        guard = 0
        while True:
            guard += 1
            if guard > 4096:
                raise FlowExecutionError("AF_E005", "Property Package Bake exceeded the maximum frame-step budget", owner_node_name)
            finished = child_runner.tick(max_immediate_steps=None)
            if finished:
                if str(getattr(child_runner, "status", "") or "") != STATUS_SUCCESS:
                    raise FlowExecutionError("AF_E005", "Property Package Bake child flow did not finish successfully", owner_node_name)
                return child_runner
            if child_runner.current_wait is not None or str(getattr(child_runner, "status", "") or "") in {STATUS_WAITING, STATUS_RELOADING}:
                raise FlowExecutionError("AF_E005", "Property Package Bake target flow cannot wait, reload, or run asynchronous tasks", owner_node_name)

    def _invoke_property_package_bake_task(self, node, task_ref):
        task_ref = self._rehydrate_task_ref_object_references(task_ref, scene=self.scene)
        if str(task_ref.get("property_package_bake_ref_role", "") or "").strip().upper() == PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE:
            raise FlowExecutionError("AF_E011", "Property Package source Task Ref must be used through Property Package Bake Target", node.name)
        start_tree_name = str(task_ref.get("start_tree_name", "") or "")
        start_node_name = str(task_ref.get("start_node_name", "") or "")
        record_tree_name = str(task_ref.get("record_tree_name", "") or "")
        record_node_name = str(task_ref.get("record_node_name", "") or "")
        start_tree = bpy.data.node_groups.get(start_tree_name)
        if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E011", f"Start tree '{start_tree_name}' was not found", node.name)
        start_node = start_tree.nodes.get(start_node_name)
        if start_node is None or getattr(start_node, "bl_idname", "") != "AFNodeStart":
            raise FlowExecutionError("AF_E011", f"Start node '{start_node_name}' was not found", node.name)
        record_tree = bpy.data.node_groups.get(record_tree_name)
        if record_tree is None or getattr(record_tree, "bl_idname", "") != "AFNodeTreeType":
            raise FlowExecutionError("AF_E011", f"Record tree '{record_tree_name}' was not found", node.name)
        record_node = record_tree.nodes.get(record_node_name)
        if record_node is None or getattr(record_node, "bl_idname", "") != "AFNodeRecordPropertyPackage":
            raise FlowExecutionError("AF_E011", f"Record Property Package node '{record_node_name}' was not found", node.name)
        frame_start = int(task_ref.get("frame_start", getattr(self.scene, "frame_start", 1)))
        frame_end = int(task_ref.get("frame_end", getattr(self.scene, "frame_end", frame_start)))
        if frame_end < frame_start:
            raise FlowExecutionError("AF_E020", "Frame End cannot be less than Frame Start", node.name)

        existing_action = self._find_property_package_bake_action(
            str(task_ref.get("bake_asset_id", "") or ""),
            str(task_ref.get("action_name", "") or ""),
        )
        report_base = self._build_property_package_bake_report_base(
            task_ref,
            start_tree_name=start_tree_name,
            start_node_name=start_node_name,
            frame_start=frame_start,
            frame_end=frame_end,
        )
        if not bool(task_ref.get("free_before_bake", False)) and _property_package_bake_action_has_cached_data(existing_action):
            return {
                **report_base,
                "frame_count": 0,
                "action_name": str(getattr(existing_action, "name", task_ref.get("action_name", "")) or task_ref.get("action_name", "")),
                "touched_object_items": self._dedup_obj_items(list(task_ref.get("predicted_object_items", []) or []), "NAME_ASC"),
                "touched_component_paths": sorted({str(path) for path in set(task_ref.get("predicted_component_paths", []) or []) if str(path)}),
                "skipped": True,
                "cache_frame_range": _property_package_bake_action_frame_range(existing_action),
            }

        previous_frame = int(getattr(self.scene, "frame_current", frame_start))
        frame_count = 0
        shared_action = self._ensure_property_package_bake_action(task_ref, clear_existing=True)
        bake_tracking = {
            "shared_action": shared_action,
            "touched_object_items": {},
            "touched_component_paths": set(),
        }
        from ... import operators as operators_module

        suspend_fn = getattr(operators_module, "_suspend_auto_follow_notifications", None)
        resume_fn = getattr(operators_module, "_resume_auto_follow_notifications", None)
        if suspend_fn is not None:
            suspend_fn()
        try:
            for frame in range(frame_start, frame_end + 1):
                self.scene.frame_set(int(frame))
                self._run_property_package_bake_once(start_tree, start_node_name, task_ref, frame, node.name, bake_tracking=bake_tracking)
                frame_count += 1
        finally:
            if bool(task_ref.get("restore_current_frame", True)):
                try:
                    self.scene.frame_set(int(previous_frame))
                except Exception:
                    pass
            if resume_fn is not None:
                resume_fn()

        return {
            **report_base,
            "frame_count": int(frame_count),
            "action_name": str(getattr(shared_action, "name", task_ref.get("action_name", "")) or task_ref.get("action_name", "")),
            "touched_object_items": self._dedup_obj_items(list(dict(bake_tracking.get("touched_object_items", {}) or {}).values()), "NAME_ASC"),
            "touched_component_paths": sorted({str(path) for path in set(bake_tracking.get("touched_component_paths", set()) or set()) if str(path)}),
            "slot_identifiers_by_object_name": {
                str(obj.name): str(getattr(getattr(getattr(obj, "animation_data", None), "action_slot", None), "identifier", "") or "")
                for obj in bpy.data.objects
                if getattr(getattr(obj, "animation_data", None), "action", None) == shared_action
            },
        }


__all__ = ["RuntimePropertyPackageBakeExecutionMixin"]
