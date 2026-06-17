import os
import json
import subprocess
import tempfile
import time

import bpy

from ...runtime_core.constants import (
    FLOW_OK,
    TASK_KIND_AUTO_FLOW_BAKE,
    TASK_KIND_RENDER,
    FlowExecutionError,
)
from ...runtime_persistence.serialization import _serialize_runtime_state_value
from .cleanup import RuntimeBackgroundProcessCleanupMixin
from .paths import _automation_flow_package_dir
from .scripts import RuntimeBackgroundProcessScriptsMixin


class RuntimeBackgroundProcessHelpersMixin(
    RuntimeBackgroundProcessCleanupMixin,
    RuntimeBackgroundProcessScriptsMixin,
):

    def _start_external_render_task(self, node, task_ref, blend_copy_path):
        task_handle = self._create_task_handle(node, task_ref)
        task_handle["report"] = {"task_kind": TASK_KIND_RENDER, "external_process": True}
        if self.settings.run_mode == "DRY_RUN":
            task_handle["status"] = "DONE"
            task_handle["finished_at"] = time.monotonic()
            task_handle["report"]["dry_run"] = True
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        blender_binary = str(getattr(bpy.app, "binary_path", "") or "")
        if not blender_binary or not os.path.exists(blender_binary):
            raise FlowExecutionError("AF_E001", "Blender executable path is unavailable for background render", node.name)
        if not blend_copy_path or not os.path.exists(blend_copy_path):
            raise FlowExecutionError("AF_E001", "Background render temporary .blend copy is missing", node.name)

        temp_dir = tempfile.mkdtemp(prefix="af_bg_render_")
        script_path = os.path.join(temp_dir, "background_render.py")
        status_path = os.path.join(temp_dir, "status.json")
        log_path = os.path.join(temp_dir, "render.log")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(self._background_render_script_text())

        args = [
            blender_binary,
            "--background",
            "--factory-startup",
            blend_copy_path,
            "--python",
            script_path,
            "--",
            status_path,
            str(task_ref.get("scene_name", "")),
            str(task_ref.get("render_mode", "STILL")),
            str(int(task_ref.get("frame", 1))),
            str(int(task_ref.get("frame_start", 1))),
            str(int(task_ref.get("frame_end", 1))),
            "1" if bool(task_ref.get("write_still", True)) else "0",
            "1" if bool(task_ref.get("use_viewport", False)) else "0",
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            stdout_handle = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                args,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to launch background render: {exc}", node.name)

        task_id = str(task_handle["task_id"])
        self.background_processes[task_id] = {
            "process": process,
            "stdout_handle": stdout_handle,
            "status_path": status_path,
            "script_path": script_path,
            "log_path": log_path,
            "temp_dir": temp_dir,
            "blend_copy_path": blend_copy_path,
        }
        interval_ms = self.settings.poll_interval_ms if self.settings.poll_interval_ms > 0 else 200
        interval_ms = max(50, int(interval_ms))
        task_handle["status"] = "WAITING"
        task_handle["report"].update(
            {
                "scene": str(task_ref.get("scene_name", "")),
                "mode": str(task_ref.get("render_mode", "STILL")),
                "log_path": log_path,
                "blend_copy_path": blend_copy_path,
            }
        )
        wait_state = {
            "wait_type": "external_process",
            "task_handle": task_handle,
            "task_id": task_id,
            "status_path": status_path,
            "log_path": log_path,
            "blend_copy_path": blend_copy_path,
            "started_at": time.monotonic(),
            "poll_interval_ms": interval_ms,
            "next_poll_at": time.monotonic(),
        }
        return {"finished": False, "task_handle": task_handle, "wait_state": wait_state}

    def _start_external_background_task_step(self, node, task_ref, step_ref, blend_copy_path):
        task_handle = self._create_task_handle(node, task_ref)
        task_kind = str(task_ref.get("task_kind", TASK_KIND_RENDER))
        task_handle["report"] = {"task_kind": task_kind, "external_process": True}
        if self.settings.run_mode == "DRY_RUN":
            task_handle["status"] = "DONE"
            task_handle["finished_at"] = time.monotonic()
            task_handle["report"]["dry_run"] = True
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        blender_binary = str(getattr(bpy.app, "binary_path", "") or "")
        if not blender_binary or not os.path.exists(blender_binary):
            raise FlowExecutionError("AF_E001", "Blender executable path is unavailable for background task execution", node.name)
        if not blend_copy_path or not os.path.exists(blend_copy_path):
            raise FlowExecutionError("AF_E001", "Background task temporary .blend copy is missing", node.name)

        temp_dir = tempfile.mkdtemp(prefix="af_bg_task_step_")
        script_path = os.path.join(temp_dir, "background_task_step.py")
        status_path = os.path.join(temp_dir, "status.json")
        log_path = os.path.join(temp_dir, "task_step.log")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(self._background_task_step_script_text())

        step_ref_json = json.dumps(step_ref or {}, ensure_ascii=True)
        package_dir = _automation_flow_package_dir()
        args = [
            blender_binary,
            "--background",
            "--factory-startup",
            blend_copy_path,
            "--python",
            script_path,
            "--",
            status_path,
            package_dir,
            step_ref_json,
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            stdout_handle = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                args,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to launch background task: {exc}", node.name)

        task_id = str(task_handle["task_id"])
        self.background_processes[task_id] = {
            "process": process,
            "stdout_handle": stdout_handle,
            "status_path": status_path,
            "script_path": script_path,
            "log_path": log_path,
            "temp_dir": temp_dir,
            "blend_copy_path": blend_copy_path,
            "task_kind": task_kind,
        }
        interval_ms = self.settings.poll_interval_ms if self.settings.poll_interval_ms > 0 else 200
        interval_ms = max(50, int(interval_ms))
        task_handle["status"] = "WAITING"
        task_handle["report"].update(
            {
                "log_path": log_path,
                "blend_copy_path": blend_copy_path,
            }
        )
        wait_state = {
            "wait_type": "external_process",
            "task_handle": task_handle,
            "task_id": task_id,
            "status_path": status_path,
            "log_path": log_path,
            "blend_copy_path": blend_copy_path,
            "started_at": time.monotonic(),
            "poll_interval_ms": interval_ms,
            "next_poll_at": time.monotonic(),
        }
        return {"finished": False, "task_handle": task_handle, "wait_state": wait_state}

    def _start_external_auto_flow_bake_task(self, node, task_ref, blend_copy_path, temp_dir=None, task_handle=None):
        task_handle = task_handle or self._create_task_handle(node, task_ref)
        task_handle["report"] = {"task_kind": TASK_KIND_AUTO_FLOW_BAKE, "external_process": True}
        if self.settings.run_mode == "DRY_RUN":
            task_handle["status"] = "DONE"
            task_handle["finished_at"] = time.monotonic()
            task_handle["report"]["dry_run"] = True
            return {"finished": True, "task_handle": task_handle, "wait_state": None}

        blender_binary = str(getattr(bpy.app, "binary_path", "") or "")
        if not blender_binary or not os.path.exists(blender_binary):
            raise FlowExecutionError("AF_E001", "Blender executable path is unavailable for background Auto Flow Bake", node.name)
        if not blend_copy_path or not os.path.exists(blend_copy_path):
            raise FlowExecutionError("AF_E001", "Background Auto Flow Bake temporary .blend copy is missing", node.name)

        temp_dir = temp_dir or tempfile.mkdtemp(prefix="af_bg_auto_flow_bake_")
        script_path = os.path.join(temp_dir, "background_auto_flow_bake.py")
        status_path = os.path.join(temp_dir, "status.json")
        log_path = os.path.join(temp_dir, "auto_flow_bake.log")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(self._background_auto_flow_bake_script_text())

        task_ref_json = json.dumps(_serialize_runtime_state_value(task_ref), ensure_ascii=True)
        package_dir = _automation_flow_package_dir()
        args = [
            blender_binary,
            "--background",
            "--factory-startup",
            blend_copy_path,
            "--python",
            script_path,
            "--",
            status_path,
            package_dir,
            task_ref_json,
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            stdout_handle = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                args,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to launch background Auto Flow Bake: {exc}", node.name)

        task_id = str(task_handle["task_id"])
        self.background_processes[task_id] = {
            "process": process,
            "stdout_handle": stdout_handle,
            "status_path": status_path,
            "script_path": script_path,
            "log_path": log_path,
            "temp_dir": temp_dir,
            "blend_copy_path": blend_copy_path,
            "task_kind": TASK_KIND_AUTO_FLOW_BAKE,
        }
        interval_ms = self.settings.poll_interval_ms if self.settings.poll_interval_ms > 0 else 200
        interval_ms = max(50, int(interval_ms))
        task_handle["status"] = "WAITING"
        task_handle["report"].update(
            {
                "blend_copy_path": blend_copy_path,
                "log_path": log_path,
                "action_name": str(task_ref.get("action_name", "") or ""),
                "bake_asset_id": str(task_ref.get("bake_asset_id", "") or ""),
            }
        )
        wait_state = {
            "wait_type": "external_process",
            "task_handle": task_handle,
            "task_id": task_id,
            "status_path": status_path,
            "log_path": log_path,
            "blend_copy_path": blend_copy_path,
            "started_at": time.monotonic(),
            "poll_interval_ms": interval_ms,
            "next_poll_at": time.monotonic(),
        }
        return {"finished": False, "task_handle": task_handle, "wait_state": wait_state}

    def _start_external_background_task_plan_process(self, node, task_plan, task_handle, blend_copy_path, temp_dir):
        if self.settings.run_mode == "DRY_RUN":
            task_handle["status"] = "DONE"
            task_handle["finished_at"] = time.monotonic()
            task_handle["report"] = {
                "plan_uid": str(task_plan.get("plan_uid", "")),
                "step_count": int(task_plan.get("step_count", 0)),
                "completed_step_count": int(task_plan.get("step_count", 0)),
                "status": "DONE",
                "dry_run": True,
                "external_process": True,
                "blend_copy_path": "",
            }
            return {"finished": True, "wait_state": None}

        blender_binary = str(getattr(bpy.app, "binary_path", "") or "")
        if not blender_binary or not os.path.exists(blender_binary):
            raise FlowExecutionError("AF_E001", "Blender executable path is unavailable for background task execution", node.name)
        if not blend_copy_path or not os.path.exists(blend_copy_path):
            raise FlowExecutionError("AF_E001", "Background task temporary .blend copy is missing", node.name)

        script_path = os.path.join(temp_dir, "background_task_plan.py")
        status_path = os.path.join(temp_dir, "status.json")
        log_path = os.path.join(temp_dir, "background_task_plan.log")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(self._background_task_plan_script_text())

        launcher_ref = self._make_step_ref(node)
        launcher_ref_json = json.dumps(launcher_ref, ensure_ascii=True)
        task_plan_json = json.dumps(_serialize_runtime_state_value(task_plan), ensure_ascii=True)
        package_dir = _automation_flow_package_dir()
        poll_interval_ms = self.settings.poll_interval_ms if self.settings.poll_interval_ms > 0 else 200
        args = [
            blender_binary,
            "--background",
            "--factory-startup",
            blend_copy_path,
            "--python",
            script_path,
            "--",
            status_path,
            package_dir,
            launcher_ref_json,
            task_plan_json,
            str(max(50, int(poll_interval_ms))),
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            stdout_handle = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                args,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to launch background task plan: {exc}", node.name)

        task_id = str(task_handle["task_id"])
        self.background_processes[task_id] = {
            "process": process,
            "stdout_handle": stdout_handle,
            "status_path": status_path,
            "script_path": script_path,
            "log_path": log_path,
            "temp_dir": temp_dir,
            "blend_copy_path": blend_copy_path,
            "task_kind": "TASK_PLAN",
        }
        interval_ms = max(50, int(poll_interval_ms))
        task_handle["status"] = "RUNNING"
        task_handle["report"] = {
            "plan_uid": str(task_plan.get("plan_uid", "")),
            "step_count": int(task_plan.get("step_count", 0)),
            "completed_step_count": 0,
            "status": "RUNNING",
            "external_process": True,
            "blend_copy_path": blend_copy_path,
            "log_path": log_path,
        }
        wait_state = {
            "wait_type": "external_process",
            "task_handle": task_handle,
            "task_id": task_id,
            "status_path": status_path,
            "log_path": log_path,
            "blend_copy_path": blend_copy_path,
            "started_at": time.monotonic(),
            "poll_interval_ms": interval_ms,
            "next_poll_at": time.monotonic(),
        }
        return {"finished": False, "wait_state": wait_state}

    def _poll_external_process_wait_state(self, wait):
        if wait is None or wait.get("wait_type") != "external_process":
            return None
        now = time.monotonic()
        if now < wait["next_poll_at"]:
            return {"finished": False, "failed": False, "payload": None, "wait_state": wait}
        wait["next_poll_at"] = now + (wait["poll_interval_ms"] / 1000.0)
        task_id = str(wait.get("task_id", "") or "")
        entry = self.background_processes.get(task_id)
        process = entry.get("process") if entry is not None else None
        status_payload = {}
        status_path = str(wait.get("status_path", "") or "")
        if status_path and os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as handle:
                    status_payload = json.load(handle)
            except Exception:
                status_payload = {}
        exit_code = process.poll() if process is not None else None
        if process is None and isinstance(status_payload, dict) and status_payload:
            payload_state = str(status_payload.get("state", "") or "")
            if payload_state == "DONE" or "success" in status_payload:
                exit_code = 0 if bool(status_payload.get("success", True)) else 1
        if exit_code is None:
            task_handle = wait["task_handle"]
            running_state = str(status_payload.get("state", "") or "")
            task_handle["status"] = "WAITING" if running_state == "WAITING" else "RUNNING"
            return {
                "finished": False,
                "failed": False,
                "payload": None,
                "wait_state": wait,
                "status_payload": status_payload,
            }

        payload = dict(status_payload or {})

        task_handle = wait["task_handle"]
        task_handle["finished_at"] = time.monotonic()
        process_entry = self.background_processes.get(task_id, {})
        blend_copy_path = str(process_entry.get("blend_copy_path", "") or "")
        task_kind = str(process_entry.get("task_kind", task_handle.get("task_kind", "TASK")) or "TASK")
        if int(exit_code) == 0 and bool(payload.get("success", True)):
            merged_report = dict(task_handle.get("report", {}) or {})
            merged_report.update(dict(payload.get("report", {}) or {}))
            if task_kind == TASK_KIND_AUTO_FLOW_BAKE:
                try:
                    merged_report.update(self._import_background_auto_flow_bake_result(task_handle, payload, blend_copy_path))
                except FlowExecutionError as exc:
                    self._cleanup_background_process(task_id, keep_artifacts=True)
                    task_handle["status"] = "FAILED"
                    task_handle["report"] = {
                        "error_code": exc.code,
                        "error_message": exc.message,
                        "node_name": exc.node_name,
                        "log_path": str(wait.get("log_path", "") or ""),
                        "blend_copy_path": blend_copy_path,
                    }
                    return {
                        "finished": True,
                        "failed": True,
                        "payload": task_id,
                        "wait_state": None,
                        "status_payload": payload,
                    }
            if bool(payload.get("skipped", False)):
                merged_report["skipped"] = True
            task_handle["report"] = merged_report
            task_handle["skipped"] = bool(payload.get("skipped", False) or merged_report.get("skipped", False))
            task_handle["status"] = "SKIPPED" if bool(task_handle.get("skipped", False)) else "DONE"
            task_handle["report"]["status"] = str(task_handle["status"])
            self._cleanup_background_process(task_id, keep_artifacts=False)
            return {
                "finished": True,
                "failed": False,
                "payload": task_id,
                "wait_state": None,
                "status_payload": payload,
            }

        self._cleanup_background_process(task_id, keep_artifacts=True)
        task_handle["status"] = "FAILED"
        task_handle["report"] = {
            "error_code": str(payload.get("error_code", "AF_E005")),
            "error_message": str(
                payload.get("error_message", f"Background {task_kind} process exited with code {exit_code}")
            ),
            "traceback": str(payload.get("traceback", "") or ""),
            "log_path": str(wait.get("log_path", "") or ""),
            "blend_copy_path": blend_copy_path,
        }
        return {
            "finished": True,
            "failed": True,
            "payload": task_id,
            "wait_state": None,
            "status_payload": payload,
        }
