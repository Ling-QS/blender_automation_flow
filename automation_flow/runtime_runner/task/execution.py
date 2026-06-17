import json
import time

import bpy

from ...runtime_core.constants import (
    BAKE_JOB_TYPE,
    FLOW_OK,
    FLOW_WAIT,
    FlowExecutionError,
    GN_PACKED_CACHE_STATE_PROP,
    STATUS_RUNNING,
    STATUS_WAITING,
    TASK_KIND_AUTO_FLOW_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ...runtime_persistence.serialization import _copy_task_ref_payload
from ...runtime_state.cache import (
    _capture_scene_frame_state,
    _is_bake_job_running,
    _operator_result_tokens,
    _restore_scene_frame_state,
    _tag_all_node_editor_redraw,
)
from ...runtime_task_target import (
    _apply_geometry_bake_entry_settings as _apply_geometry_bake_entry_settings_impl,
    _apply_temporary_geometry_bake_settings as _apply_temporary_geometry_bake_settings_impl,
    _call_operator_with_override as _call_operator_with_override_impl,
    _capture_geometry_bake_entry_settings as _capture_geometry_bake_entry_settings_impl,
    _clear_geometry_bake_tracked_packed_cache_state as _clear_geometry_bake_tracked_packed_cache_state_impl,
    _compose_bake_override as _compose_bake_override_impl,
    _ensure_operator_finished as _ensure_operator_finished_impl,
    _geometry_bake_disk_cache_exists as _geometry_bake_disk_cache_exists_impl,
    _geometry_bake_disk_cache_root_dir as _geometry_bake_disk_cache_root_dir_impl,
    _geometry_bake_entry_cached_frame_range as _geometry_bake_entry_cached_frame_range_impl,
    _geometry_bake_entry_has_cached_data as _geometry_bake_entry_has_cached_data_impl,
    _geometry_bake_has_existing_cache as _geometry_bake_has_existing_cache_impl,
    _geometry_bake_has_existing_cache_for_current_entry as _geometry_bake_has_existing_cache_for_current_entry_impl,
    _get_geometry_bake_tracked_packed_cache_status as _get_geometry_bake_tracked_packed_cache_status_impl,
    _invoke_geometry_nodes_bake_task as _invoke_geometry_nodes_bake_task_impl,
    _invoke_physics_bake_all_task as _invoke_physics_bake_all_task_impl,
    _invoke_physics_bake_task as _invoke_physics_bake_task_impl,
    _invoke_render_task as _invoke_render_task_impl,
    _iter_geometry_bake_disk_cache_candidate_roots as _iter_geometry_bake_disk_cache_candidate_roots_impl,
    _read_geometry_bake_tracked_packed_cache_state as _read_geometry_bake_tracked_packed_cache_state_impl,
    _refresh_geometry_bake_cache_state_after_completion as _refresh_geometry_bake_cache_state_after_completion_impl,
    _resolve_geometry_task_effective_bake_target as _resolve_geometry_task_effective_bake_target_impl,
    _resolve_geometry_task_source_node as _resolve_geometry_task_source_node_impl,
    _restore_geometry_bake_entry_settings as _restore_geometry_bake_entry_settings_impl,
    _restore_waiting_bake_cleanup as _restore_waiting_bake_cleanup_impl,
    _schedule_geometry_bake_cache_refresh as _schedule_geometry_bake_cache_refresh_impl,
    _start_geometry_nodes_bake_task as _start_geometry_nodes_bake_task_impl,
    _start_named_operator as _start_named_operator_impl,
    _start_physics_bake_all_task as _start_physics_bake_all_task_impl,
    _start_physics_bake_task as _start_physics_bake_task_impl,
    _task_operator_result_is_skipped as _task_operator_result_is_skipped_impl,
    _write_geometry_bake_tracked_packed_cache_state as _write_geometry_bake_tracked_packed_cache_state_impl,
)


class RuntimeTaskExecutionMixin:
    def _ensure_operator_finished(self, result, error_code, operator_label, node_name):
        return _ensure_operator_finished_impl(
            result,
            error_code,
            operator_label,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _resolve_geometry_task_effective_bake_target(self, task_ref):
        return _resolve_geometry_task_effective_bake_target_impl(
            task_ref,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
        )

    def _capture_geometry_bake_entry_settings(self, bake_entry):
        return _capture_geometry_bake_entry_settings_impl(bake_entry)

    def _apply_geometry_bake_entry_settings(self, bake_entry, task_ref):
        return _apply_geometry_bake_entry_settings_impl(bake_entry, task_ref)

    def _restore_geometry_bake_entry_settings(self, bake_entry, state):
        return _restore_geometry_bake_entry_settings_impl(bake_entry, state)

    def _resolve_geometry_task_source_node(self, task_ref):
        return _resolve_geometry_task_source_node_impl(task_ref)

    def _read_geometry_bake_tracked_packed_cache_state(self, node):
        return _read_geometry_bake_tracked_packed_cache_state_impl(
            node,
            gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
            json_module=json,
        )

    def _write_geometry_bake_tracked_packed_cache_state(self, task_ref, frame_range=None):
        return _write_geometry_bake_tracked_packed_cache_state_impl(
            task_ref,
            frame_range=frame_range,
            resolve_geometry_task_source_node=self._resolve_geometry_task_source_node,
            gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
            json_module=json,
        )

    def _clear_geometry_bake_tracked_packed_cache_state(self, task_ref):
        return _clear_geometry_bake_tracked_packed_cache_state_impl(
            task_ref,
            resolve_geometry_task_source_node=self._resolve_geometry_task_source_node,
            gn_packed_cache_state_prop=GN_PACKED_CACHE_STATE_PROP,
        )

    def _get_geometry_bake_tracked_packed_cache_status(self, task_ref):
        return _get_geometry_bake_tracked_packed_cache_status_impl(
            task_ref,
            resolve_geometry_task_source_node=self._resolve_geometry_task_source_node,
            read_geometry_bake_tracked_packed_cache_state=self._read_geometry_bake_tracked_packed_cache_state,
        )

    def _geometry_bake_entry_has_cached_data(self, bake_entry):
        return _geometry_bake_entry_has_cached_data_impl(bake_entry)

    def _geometry_bake_disk_cache_root_dir(self, task_ref, bake_entry=None):
        return _geometry_bake_disk_cache_root_dir_impl(
            task_ref,
            bake_entry=bake_entry,
            bpy_module=bpy,
            require_payload_object_ref=self._require_payload_object_ref,
        )

    def _iter_geometry_bake_disk_cache_candidate_roots(self, task_ref, bake_entry=None):
        return _iter_geometry_bake_disk_cache_candidate_roots_impl(
            task_ref,
            bake_entry=bake_entry,
            geometry_bake_disk_cache_root_dir=self._geometry_bake_disk_cache_root_dir,
        )

    def _geometry_bake_disk_cache_exists(self, task_ref, bake_entry=None):
        return _geometry_bake_disk_cache_exists_impl(
            task_ref,
            bake_entry=bake_entry,
            geometry_bake_disk_cache_candidate_roots=self._iter_geometry_bake_disk_cache_candidate_roots,
        )

    def _geometry_bake_has_existing_cache(self, task_ref, scene, bake_entry):
        return _geometry_bake_has_existing_cache_impl(
            task_ref,
            scene,
            bake_entry,
            geometry_bake_entry_has_cached_data=self._geometry_bake_entry_has_cached_data,
            get_geometry_bake_tracked_packed_cache_status=self._get_geometry_bake_tracked_packed_cache_status,
            geometry_bake_disk_cache_exists=self._geometry_bake_disk_cache_exists,
        )

    def _geometry_bake_has_existing_cache_for_current_entry(self, task_ref, scene, bake_entry):
        return _geometry_bake_has_existing_cache_for_current_entry_impl(
            task_ref,
            scene,
            bake_entry,
            geometry_bake_entry_has_cached_data=self._geometry_bake_entry_has_cached_data,
            geometry_bake_disk_cache_exists=self._geometry_bake_disk_cache_exists,
        )

    def _refresh_geometry_bake_cache_state_after_completion(self, task_ref, scene=None):
        return _refresh_geometry_bake_cache_state_after_completion_impl(
            task_ref,
            scene=scene if scene is not None else getattr(bpy.context, "scene", None),
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
            geometry_bake_entry_has_cached_data=self._geometry_bake_entry_has_cached_data,
            geometry_bake_entry_cached_frame_range=_geometry_bake_entry_cached_frame_range_impl,
            resolve_geometry_task_effective_bake_target=self._resolve_geometry_task_effective_bake_target,
            tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
        )

    def _schedule_geometry_bake_cache_refresh(self, task_ref, scene=None, retries=24, interval=0.12):
        return _schedule_geometry_bake_cache_refresh_impl(
            task_ref,
            scene=scene,
            retries=retries,
            interval=interval,
            refresh_geometry_bake_cache_state_after_completion=self._refresh_geometry_bake_cache_state_after_completion,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
            geometry_bake_entry_has_cached_data=self._geometry_bake_entry_has_cached_data,
            geometry_bake_disk_cache_exists=self._geometry_bake_disk_cache_exists,
            tag_all_node_editor_redraw=_tag_all_node_editor_redraw,
        )

    def _task_operator_result_is_skipped(self, result):
        return _task_operator_result_is_skipped_impl(result)

    def _apply_temporary_geometry_bake_settings(self, task_ref):
        return _apply_temporary_geometry_bake_settings_impl(
            task_ref,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
            capture_geometry_bake_entry_settings=self._capture_geometry_bake_entry_settings,
            apply_geometry_bake_entry_settings=self._apply_geometry_bake_entry_settings,
        )

    def _compose_bake_override(self, base_override, ui_context=None):
        return _compose_bake_override_impl(base_override, ui_context=ui_context)

    def _call_operator_with_override(self, operator, override, payload=None, invoke_async=False):
        return _call_operator_with_override_impl(
            operator,
            override,
            payload=payload,
            invoke_async=invoke_async,
            operator_result_tokens=_operator_result_tokens,
        )

    def _start_named_operator(self, operator_paths, override, payload, source_node, invoke_async=False):
        return _start_named_operator_impl(
            operator_paths,
            override,
            payload,
            source_node,
            invoke_async=invoke_async,
            flow_execution_error_cls=FlowExecutionError,
            call_operator_with_override=self._call_operator_with_override,
        )

    def _restore_waiting_bake_cleanup(self, wait_state, bake_completed):
        return _restore_waiting_bake_cleanup_impl(
            wait_state,
            bake_completed,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_physics=TASK_KIND_PHYSICS,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
            restore_geometry_bake_entry_settings=self._restore_geometry_bake_entry_settings,
            restore_scene_frame_state=_restore_scene_frame_state,
        )

    def _start_geometry_nodes_bake_task(self, task_ref, scene, ui_context=None):
        return _start_geometry_nodes_bake_task_impl(
            task_ref,
            scene,
            ui_context=ui_context,
            bpy_module=bpy,
            require_payload_object_ref=self._require_payload_object_ref,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
            compose_bake_override=self._compose_bake_override,
            capture_scene_frame_state=_capture_scene_frame_state,
            geometry_bake_has_existing_cache_for_current_entry=self._geometry_bake_has_existing_cache_for_current_entry,
            geometry_bake_has_existing_cache=self._geometry_bake_has_existing_cache,
            apply_temporary_geometry_bake_settings=self._apply_temporary_geometry_bake_settings,
            clear_geometry_bake_tracked_packed_cache_state=self._clear_geometry_bake_tracked_packed_cache_state,
            call_operator_with_override=self._call_operator_with_override,
            start_named_operator=self._start_named_operator,
            restore_waiting_bake_cleanup=self._restore_waiting_bake_cleanup,
            bake_job_type=BAKE_JOB_TYPE,
            task_kind_geometry=TASK_KIND_GEOMETRY,
        )

    def _start_physics_bake_task(self, task_ref, scene, ui_context=None):
        return _start_physics_bake_task_impl(
            task_ref,
            scene,
            ui_context=ui_context,
            bpy_module=bpy,
            flow_execution_error_cls=FlowExecutionError,
            require_payload_object_ref=self._require_payload_object_ref,
            capture_scene_frame_state=_capture_scene_frame_state,
            physics_task_has_existing_cache=self._physics_task_has_existing_cache,
            compose_bake_override=self._compose_bake_override,
            start_named_operator=self._start_named_operator,
            restore_waiting_bake_cleanup=self._restore_waiting_bake_cleanup,
            bake_job_type=BAKE_JOB_TYPE,
            task_kind_physics=TASK_KIND_PHYSICS,
        )

    def _start_physics_bake_all_task(self, task_ref, scene, ui_context=None):
        return _start_physics_bake_all_task_impl(
            task_ref,
            scene,
            ui_context=ui_context,
            bpy_module=bpy,
            flow_execution_error_cls=FlowExecutionError,
            require_payload_object_ref=self._require_payload_object_ref,
            capture_scene_frame_state=_capture_scene_frame_state,
            physics_bake_all_has_pending_work=self._physics_bake_all_has_pending_work,
            compose_bake_override=self._compose_bake_override,
            start_named_operator=self._start_named_operator,
            restore_waiting_bake_cleanup=self._restore_waiting_bake_cleanup,
            bake_job_type=BAKE_JOB_TYPE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        )

    def _invoke_geometry_nodes_bake_task(self, task_ref, scene):
        return _invoke_geometry_nodes_bake_task_impl(
            task_ref,
            scene,
            bpy_module=bpy,
            require_payload_object_ref=self._require_payload_object_ref,
            find_geometry_bake_entry_for_task=self._find_geometry_bake_entry_for_task,
            capture_scene_frame_state=_capture_scene_frame_state,
            geometry_bake_has_existing_cache_for_current_entry=self._geometry_bake_has_existing_cache_for_current_entry,
            geometry_bake_has_existing_cache=self._geometry_bake_has_existing_cache,
            apply_temporary_geometry_bake_settings=self._apply_temporary_geometry_bake_settings,
            clear_geometry_bake_tracked_packed_cache_state=self._clear_geometry_bake_tracked_packed_cache_state,
            call_operator_with_override=self._call_operator_with_override,
            start_named_operator=self._start_named_operator,
            refresh_geometry_bake_cache_state_after_completion=self._refresh_geometry_bake_cache_state_after_completion,
            resolve_geometry_task_effective_bake_target=self._resolve_geometry_task_effective_bake_target,
            write_geometry_bake_tracked_packed_cache_state=self._write_geometry_bake_tracked_packed_cache_state,
            ensure_operator_finished=self._ensure_operator_finished,
            restore_geometry_bake_entry_settings=self._restore_geometry_bake_entry_settings,
            restore_scene_frame_state=_restore_scene_frame_state,
        )

    def _invoke_physics_bake_task(self, task_ref, scene):
        return _invoke_physics_bake_task_impl(
            task_ref,
            scene,
            bpy_module=bpy,
            flow_execution_error_cls=FlowExecutionError,
            require_payload_object_ref=self._require_payload_object_ref,
            capture_scene_frame_state=_capture_scene_frame_state,
            physics_task_has_existing_cache=self._physics_task_has_existing_cache,
            start_named_operator=self._start_named_operator,
            ensure_operator_finished=self._ensure_operator_finished,
            restore_scene_frame_state=_restore_scene_frame_state,
        )

    def _invoke_physics_bake_all_task(self, task_ref, scene):
        return _invoke_physics_bake_all_task_impl(
            task_ref,
            scene,
            bpy_module=bpy,
            flow_execution_error_cls=FlowExecutionError,
            require_payload_object_ref=self._require_payload_object_ref,
            capture_scene_frame_state=_capture_scene_frame_state,
            physics_bake_all_has_pending_work=self._physics_bake_all_has_pending_work,
            start_named_operator=self._start_named_operator,
            ensure_operator_finished=self._ensure_operator_finished,
            restore_scene_frame_state=_restore_scene_frame_state,
        )

    def _invoke_render_task(self, task_ref, fallback_scene, node_name):
        return _invoke_render_task_impl(
            task_ref,
            fallback_scene,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            capture_scene_frame_state=_capture_scene_frame_state,
            start_named_operator=self._start_named_operator,
            ensure_operator_finished=self._ensure_operator_finished,
            restore_scene_frame_state=_restore_scene_frame_state,
        )

    def _run_task_ref_now(self, node, task_ref, task_handle=None):
        task_ref = self._rehydrate_task_ref_object_references(task_ref, scene=self.scene)
        task_ref = self._raise_if_invalid_task_ref(task_ref, node.name)
        task_ref = self._validate_task_ref_object_targets(task_ref, node.name)
        dry_run = self._is_dry_run_mode()
        flow_test = self._is_flow_test_mode()
        task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY))
        task_handle = task_handle or self._create_task_handle(node, task_ref)
        if dry_run or flow_test:
            self._mark_task_handle_simulated(
                task_handle,
                extra_report={"task_kind": task_kind},
            )
            if flow_test:
                self.log("INFO", "Flow-test: simulated task execution", node.name)
            else:
                self.log("INFO", "Dry-run: skipped task execution", node.name)
        else:
            task_handle["status"] = "RUNNING"
            if task_kind == TASK_KIND_PHYSICS:
                result = self._invoke_physics_bake_task(task_ref, self.scene)
                task_handle["report"] = {"task_kind": task_kind}
            elif task_kind == TASK_KIND_PHYSICS_BAKE_ALL:
                result = self._invoke_physics_bake_all_task(task_ref, self.scene)
                task_handle["report"] = {"task_kind": task_kind}
            elif task_kind == TASK_KIND_AUTO_FLOW_BAKE:
                auto_flow_report = self._invoke_auto_flow_bake_task(node, task_ref)
                task_handle["report"] = dict(auto_flow_report)
                result = {"SKIPPED"} if bool(auto_flow_report.get("skipped", False)) else {"FINISHED"}
            elif task_kind == TASK_KIND_RENDER:
                result = self._invoke_render_task(task_ref, self.scene, node.name)
                task_handle["report"] = result
            else:
                result = self._invoke_geometry_nodes_bake_task(task_ref, self.scene)
                task_handle["report"] = {"task_kind": task_kind}
            task_handle["status"] = "DONE"
            task_handle["operator_result"] = str(result)
            if self._task_operator_result_is_skipped(result):
                task_handle["skipped"] = True
                task_handle["report"]["skipped"] = True
            elif bool(dict(task_handle.get("report") or {}).get("skipped", False)):
                task_handle["skipped"] = True
        if not (dry_run or flow_test):
            task_handle["finished_at"] = time.monotonic()
        return task_handle

    def _supports_async_bake(self):
        return not bpy.app.background and self.ui_context.get("window") is not None

    def _start_task_ref_async(self, node, task_ref, object_list, assign_wait=True):
        task_ref = self._rehydrate_task_ref_object_references(task_ref, scene=self.scene)
        task_ref = self._raise_if_invalid_task_ref(task_ref, node.name)
        task_ref = self._validate_task_ref_object_targets(task_ref, node.name)
        task_handle = self._create_task_handle(node, task_ref)
        if self._is_task_simulation_mode():
            task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY))
            self._mark_task_handle_simulated(
                task_handle,
                extra_report={"task_kind": task_kind},
            )
            if self._is_flow_test_mode():
                self.log("INFO", "Flow-test: simulated task execution", node.name)
            else:
                self.log("INFO", "Dry-run: skipped task execution", node.name)
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY))
        if task_kind in {TASK_KIND_RENDER, TASK_KIND_AUTO_FLOW_BAKE} or not self._supports_async_bake():
            task_handle = self._run_task_ref_now(node, task_ref, task_handle=task_handle)
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        task_handle["status"] = "RUNNING"
        if task_kind == TASK_KIND_PHYSICS:
            start_result = self._start_physics_bake_task(task_ref, self.scene, ui_context=self.ui_context)
        elif task_kind == TASK_KIND_PHYSICS_BAKE_ALL:
            start_result = self._start_physics_bake_all_task(task_ref, self.scene, ui_context=self.ui_context)
        else:
            start_result = self._start_geometry_nodes_bake_task(task_ref, self.scene, ui_context=self.ui_context)

        task_handle["operator_result"] = str(start_result.get("operator_result"))
        if start_result["completed"]:
            task_handle["status"] = "DONE"
            task_handle["finished_at"] = time.monotonic()
            task_handle["report"] = {"task_kind": task_kind}
            if self._task_operator_result_is_skipped(start_result.get("operator_result")):
                task_handle["skipped"] = True
                task_handle["report"]["skipped"] = True
            self._restore_waiting_bake_cleanup(start_result["wait_state"], bake_completed=True)
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        interval_ms = self.settings.poll_interval_ms if self.settings.poll_interval_ms > 0 else 200
        interval_ms = max(50, int(interval_ms))
        wait_state = dict(start_result["wait_state"])
        wait_state.update(
            {
                "wait_type": "bake_task",
                "node_name": node.name,
                "node_identity": self._node_identity(node),
                "task_ref": _copy_task_ref_payload(task_ref),
                "task_handle": task_handle,
                "object_list": object_list,
                "started_at": time.monotonic(),
                "poll_interval_ms": interval_ms,
                "next_poll_at": time.monotonic(),
                "operator_path": start_result.get("operator_path", ""),
            }
        )
        task_handle["status"] = "WAITING"
        if assign_wait:
            self.current_wait = wait_state
            self.set_status(STATUS_WAITING)
        return {"finished": False, "task_handle": task_handle, "wait_state": wait_state}

    def _poll_bake_wait_state(self, node, wait):
        if wait is None or wait.get("wait_type") != "bake_task" or wait.get("node_identity") != self._node_identity(node):
            return None
        now = time.monotonic()
        if now < wait["next_poll_at"]:
            return {"finished": False, "flow_result": FLOW_WAIT, "payload": None, "wait_state": wait}
        wait["next_poll_at"] = now + (wait["poll_interval_ms"] / 1000.0)
        if _is_bake_job_running():
            task_handle = wait["task_handle"]
            task_handle["status"] = "WAITING"
            return {"finished": False, "flow_result": FLOW_WAIT, "payload": None, "wait_state": wait}

        task_handle = wait["task_handle"]
        task_ref = dict(wait.get("task_ref") or {})
        if str(task_ref.get("task_kind", "")) == TASK_KIND_GEOMETRY:
            frame_range = self._refresh_geometry_bake_cache_state_after_completion(task_ref, self.scene)
            if self._resolve_geometry_task_effective_bake_target(task_ref) == "PACKED":
                self._write_geometry_bake_tracked_packed_cache_state(task_ref, frame_range=frame_range)
            if frame_range is not None:
                task_handle.setdefault("report", {})
                task_handle["report"]["frame_start"] = int(frame_range[0])
                task_handle["report"]["frame_end"] = int(frame_range[1])
            self._schedule_geometry_bake_cache_refresh(task_ref, self.scene)
        task_handle["status"] = "DONE"
        task_handle["finished_at"] = time.monotonic()
        self._restore_waiting_bake_cleanup(wait, bake_completed=True)
        return {"finished": True, "flow_result": FLOW_OK, "payload": task_handle["task_id"], "wait_state": None}

    def _poll_bake_wait(self, node):
        wait = self.current_wait
        result = self._poll_bake_wait_state(node, wait)
        if result is None:
            return None
        task_handle = wait["task_handle"]
        display_status = self._task_handle_display_status(task_handle)
        self._set_output(node, "status", display_status)
        report = {
            "task_id": task_handle["task_id"],
            "task_kind": str(task_handle.get("task_kind", "")),
            "target_count": wait["object_list"]["count"],
            "status": display_status,
        }
        report.update(dict(task_handle.get("report") or {}))
        if bool(task_handle.get("skipped", False)):
            report["skipped"] = True
        self._set_output(node, "report", report)
        if result["finished"]:
            self.current_wait = None
            self.set_status(STATUS_RUNNING)
        return result["flow_result"], result["payload"]

    def _poll_delay_wait_state(self, wait):
        if wait is None or wait.get("wait_type") != "delay":
            return None
        now = time.monotonic()
        elapsed = now - wait["started_at"]
        if elapsed >= wait["delay_seconds"]:
            return {"finished": True, "flow_result": FLOW_OK, "payload": "DONE", "wait_state": None, "elapsed": elapsed}
        if now < wait["next_poll_at"]:
            return {"finished": False, "flow_result": FLOW_WAIT, "payload": None, "wait_state": wait, "elapsed": elapsed}
        wait["next_poll_at"] = now + (wait["poll_interval_ms"] / 1000.0)
        return {"finished": False, "flow_result": FLOW_WAIT, "payload": None, "wait_state": wait, "elapsed": elapsed}

    def _run_task_ref(self, node, task_ref):
        return self._run_task_ref_now(node, task_ref)

    def _resolve_live_task_handle(self, task_handle_payload):
        if not isinstance(task_handle_payload, dict):
            return None
        task_id = str(task_handle_payload.get("task_id", "") or "")
        if not task_id:
            return None
        live_handle = self.tasks.get(task_id)
        if live_handle is not None:
            return live_handle
        return task_handle_payload


__all__ = ["RuntimeTaskExecutionMixin"]
