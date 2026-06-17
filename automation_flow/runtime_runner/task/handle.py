import bpy
import time
import uuid

from ...runtime_core.constants import (
    FlowExecutionError,
    OBJECT_PERSISTENT_UUID_PROP,
    TASK_KIND_AUTO_FLOW_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ...runtime_refs.objects import (
    _dedup_obj_items,
    _find_object_by_item,
    _normalize_object_item_reference,
    _obj_item,
    _object_list_from_task_ref,
    _object_reference_identity,
)
from ...runtime_persistence.serialization import (
    _copy_runtime_state_value,
    _copy_task_ref_payload,
    _ensure_object_persistent_uuid,
)
from ...runtime_task_ref.helpers import _frame_range_from_task_ref
from ...runtime_task_ref.refs import (
    _raise_if_invalid_task_ref,
    _rehydrate_task_ref_object_references,
    _validate_task_ref_object_targets,
)
from ...runtime_task_target import _task_operator_result_is_skipped


class RuntimeTaskHandleMixin:
    def _object_ref_identity(self, object_id, object_name, object_uuid="", object_resolver=None):
        return _object_reference_identity(
            object_id,
            object_name,
            object_uuid=object_uuid,
            object_resolver=object_resolver,
            find_object_by_item=lambda item: _find_object_by_item(item, OBJECT_PERSISTENT_UUID_PROP),
            ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid(obj, OBJECT_PERSISTENT_UUID_PROP),
        )

    def _normalize_task_ref_object_item(self, item, object_resolver=None):
        return _normalize_object_item_reference(
            item,
            object_resolver=object_resolver,
            object_reference_identity=self._object_ref_identity,
        )

    def _task_ref_obj_item(self, obj):
        return _obj_item(obj, lambda target: _ensure_object_persistent_uuid(target, OBJECT_PERSISTENT_UUID_PROP))

    def _rehydrate_task_ref_payload(self, task_ref, object_resolver=None, scene=None):
        return _rehydrate_task_ref_object_references(
            task_ref,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_physics=TASK_KIND_PHYSICS,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
            copy_task_ref_payload=_copy_task_ref_payload,
            copy_runtime_state_value=_copy_runtime_state_value,
            ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid(obj, OBJECT_PERSISTENT_UUID_PROP),
            find_object_by_item=lambda item: _find_object_by_item(item, OBJECT_PERSISTENT_UUID_PROP),
            dedup_obj_items=lambda items, sort_mode, object_resolver=None: _dedup_obj_items(
                items,
                sort_mode,
                object_resolver=object_resolver,
                normalize_object_item_reference=self._normalize_task_ref_object_item,
            ),
            scene=scene,
            object_resolver=object_resolver,
        )

    def _raise_invalid_task_ref_issue(self, task_ref, fallback_node_name):
        return _raise_if_invalid_task_ref(
            task_ref,
            fallback_node_name,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _validate_task_ref_targets(self, task_ref, node_name):
        return _validate_task_ref_object_targets(
            task_ref,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_physics=TASK_KIND_PHYSICS,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        )

    def _task_ref_object_list(self, task_ref, sort_mode="NAME_ASC", scene=None):
        return _object_list_from_task_ref(
            task_ref,
            sort_mode=sort_mode,
            scene=scene,
            rehydrate_task_ref_object_references=self._rehydrate_task_ref_payload,
            rehydrate_auto_flow_bake_predicted_items=self._rehydrate_auto_flow_bake_predicted_items,
            copy_runtime_state_value=_copy_runtime_state_value,
            dedup_obj_items=lambda items, current_sort_mode, object_resolver=None: _dedup_obj_items(
                items,
                current_sort_mode,
                object_resolver=object_resolver,
                normalize_object_item_reference=self._normalize_task_ref_object_item,
            ),
            obj_item=self._task_ref_obj_item,
            ensure_object_persistent_uuid=lambda obj: _ensure_object_persistent_uuid(obj, OBJECT_PERSISTENT_UUID_PROP),
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        )

    def _task_ref_frame_range(self, task_ref, scene):
        return _frame_range_from_task_ref(
            task_ref,
            scene,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_auto_flow_bake=TASK_KIND_AUTO_FLOW_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
            task_kind_geometry=TASK_KIND_GEOMETRY,
        )

    def _rehydrate_auto_flow_bake_predicted_items(self, task_ref, scene):
        if not isinstance(task_ref, dict) or scene is None:
            return []
        start_tree_name = str(task_ref.get("start_tree_name", "") or task_ref.get("source_tree_name", "") or "")
        start_node_name = str(task_ref.get("start_node_name", "") or "").strip()
        if not start_tree_name or not start_node_name:
            return []
        start_tree = bpy.data.node_groups.get(start_tree_name)
        if start_tree is None or getattr(start_tree, "bl_idname", "") != "AFNodeTreeType":
            return []
        owner_node_name = str(task_ref.get("source_node", "") or "")
        try:
            targets = self._predict_auto_flow_bake_targets(start_tree, start_node_name, owner_node_name)
        except Exception:
            return []
        return list(dict(targets or {}).get("predicted_object_items", []) or [])

    def _create_task_handle(self, node, task_ref):
        task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY))
        task_handle = {
            "task_id": f"task_{len(self.tasks) + 1}",
            "task_uid": task_ref["task_uid"],
            "task_kind": task_kind,
            "status": "PENDING",
            "skipped": False,
            "node_name": node.name,
            "started_at": time.monotonic(),
            "finished_at": None,
        }
        self.tasks[task_handle["task_id"]] = task_handle
        self.vars["last_task_handle"] = task_handle
        self.vars["last_task_id"] = task_handle["task_id"]
        return task_handle

    def _run_mode(self):
        return str(getattr(self.settings, "run_mode", "NORMAL") or "NORMAL")

    def _is_dry_run_mode(self):
        return self._run_mode() == "DRY_RUN"

    def _is_flow_test_mode(self):
        return self._run_mode() == "FLOW_TEST"

    def _is_task_simulation_mode(self):
        return self._run_mode() in {"DRY_RUN", "FLOW_TEST"}

    def _mark_task_handle_simulated(self, task_handle, extra_report=None):
        run_mode = self._run_mode()
        report = dict(task_handle.get("report") or {})
        if isinstance(extra_report, dict):
            report.update(extra_report)
        report["simulated"] = True
        if run_mode == "DRY_RUN":
            report["dry_run"] = True
        if run_mode == "FLOW_TEST":
            report["flow_test"] = True
        task_handle["status"] = "DONE"
        task_handle["finished_at"] = time.monotonic()
        task_handle["simulated"] = True
        task_handle["flow_test"] = (run_mode == "FLOW_TEST")
        task_handle["report"] = report
        return task_handle

    def _create_background_plan_handle(self, node, task_plan):
        task_handle = {
            "task_id": f"task_{len(self.tasks) + 1}",
            "task_uid": str(task_plan.get("plan_uid", str(uuid.uuid4()))),
            "task_kind": "TASK_PLAN",
            "status": "PENDING",
            "skipped": False,
            "node_name": node.name,
            "started_at": time.monotonic(),
            "finished_at": None,
            "step_count": int(task_plan.get("step_count", 0)),
            "plan_uid": str(task_plan.get("plan_uid", "")),
            "output_node": str(task_plan.get("output_node", "")),
            "is_background_plan": True,
        }
        self.tasks[task_handle["task_id"]] = task_handle
        self.vars["last_task_handle"] = task_handle
        self.vars["last_task_id"] = task_handle["task_id"]
        return task_handle

    def _create_skipped_background_plan_handle(self, node, reason=""):
        task_handle = self._create_background_plan_handle(node, {})
        task_handle["status"] = "SKIPPED"
        task_handle["skipped"] = True
        task_handle["finished_at"] = time.monotonic()
        report = {
            "status": "SKIPPED",
            "skipped": True,
            "step_count": 0,
        }
        if reason:
            report["reason"] = str(reason)
        task_handle["report"] = report
        return task_handle

    def _task_handle_is_skipped(self, task_handle):
        if not isinstance(task_handle, dict):
            return False
        if bool(task_handle.get("skipped", False)):
            return True
        report = dict(task_handle.get("report") or {})
        if bool(report.get("skipped", False)):
            return True
        operator_result = task_handle.get("operator_result")
        return _task_operator_result_is_skipped(operator_result)

    def _task_handle_display_status(self, task_handle, default="DONE"):
        if self._task_handle_is_skipped(task_handle):
            return "SKIPPED"
        fallback = str(default or "DONE").strip().upper() or "DONE"
        if not isinstance(task_handle, dict):
            return fallback
        status_value = str(task_handle.get("status", fallback) or fallback).strip().upper()
        return status_value or fallback

    def _resolve_task_ref_status_payload(self, node, task_ref):
        fallback_start = int(getattr(self.scene, "frame_start", 1))
        fallback_end = int(getattr(self.scene, "frame_end", fallback_start))
        empty_object_list = {"items": [], "count": 0, "sort_mode": "NAME_ASC"}
        invalid_report = {
            "status": "INVALID",
            "object_count": 0,
            "frame_start": int(fallback_start),
            "frame_end": int(fallback_end),
        }
        if isinstance(task_ref, dict):
            invalid_report["task_kind"] = str(task_ref.get("task_kind", "") or "")
        if task_ref is None:
            invalid_report["error_code"] = "AF_E011"
            invalid_report["error_message"] = "Task Ref input is not linked"
            return empty_object_list, int(fallback_start), int(fallback_end), "INVALID", invalid_report

        try:
            task_ref = self._rehydrate_task_ref_payload(task_ref, scene=self.scene)
            task_ref = self._raise_invalid_task_ref_issue(task_ref, node.name)
            task_ref = self._validate_task_ref_targets(task_ref, node.name)
            task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY) or TASK_KIND_GEOMETRY)
            supported_kinds = {
                TASK_KIND_GEOMETRY,
                TASK_KIND_PHYSICS,
                TASK_KIND_PHYSICS_BAKE_ALL,
                TASK_KIND_RENDER,
                TASK_KIND_AUTO_FLOW_BAKE,
            }
            if task_kind not in supported_kinds:
                raise FlowExecutionError("AF_E011", f"Task kind '{task_kind}' is not supported", node.name)

            object_list = self._task_ref_object_list(task_ref, "NAME_ASC", self.scene)
            frame_start, frame_end = self._task_ref_frame_range(task_ref, self.scene)
            status_value = str(task_ref.get("status", "READY") or "READY").strip().upper() or "READY"
            report = dict(task_ref.get("report") or {})
            if not report:
                report = {}
            report.setdefault("status", status_value)
            report.setdefault("task_kind", task_kind)
            report.setdefault("object_count", int(object_list.get("count", 0)))
            report.setdefault("frame_start", int(frame_start))
            report.setdefault("frame_end", int(frame_end))
            if status_value == "SKIPPED":
                report.setdefault("skipped", True)
            return object_list, int(frame_start), int(frame_end), status_value, report
        except FlowExecutionError as exc:
            invalid_report["error_code"] = str(exc.code or "")
            invalid_report["error_message"] = str(exc.message or "")
            return empty_object_list, int(fallback_start), int(fallback_end), "INVALID", invalid_report
        except Exception as exc:
            invalid_report["error_code"] = "AF_E009"
            invalid_report["error_message"] = str(exc or "")
            return empty_object_list, int(fallback_start), int(fallback_end), "INVALID", invalid_report


__all__ = ["RuntimeTaskHandleMixin"]
