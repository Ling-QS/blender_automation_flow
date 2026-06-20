import glob
import os
import shutil
import uuid

import bpy

from ...runtime_core.constants import FlowExecutionError
from ...runtime_state.cache import _operator_result_tokens


class RuntimeBackgroundProcessCleanupMixin:
    def _background_blendcache_dir(self, blend_path):
        filepath = str(blend_path or "").strip()
        if not filepath:
            return ""
        directory = os.path.dirname(filepath)
        stem = os.path.splitext(os.path.basename(filepath))[0]
        if not stem:
            return ""
        return os.path.join(directory, f"blendcache_{stem}")

    def _source_blend_path_for_background_copy(self, blend_copy_path):
        filepath = str(blend_copy_path or "").strip()
        if not filepath:
            return ""
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        stem, ext = os.path.splitext(filename)
        if ".af_bg_" not in stem:
            return ""
        source_stem = stem.split(".af_bg_", 1)[0].strip()
        if not source_stem:
            return ""
        return os.path.join(directory, f"{source_stem}{ext or '.blend'}")

    def _merge_background_cache_tree(self, source_path, destination_path):
        moved_files = 0
        moved_dirs = 0
        if not source_path or not os.path.exists(source_path):
            return moved_files, moved_dirs
        if os.path.isdir(source_path):
            os.makedirs(destination_path, exist_ok=True)
            moved_dirs += 1
            try:
                entries = list(os.scandir(source_path))
            except Exception:
                entries = []
            for entry in entries:
                child_source = entry.path
                child_destination = os.path.join(destination_path, entry.name)
                child_files, child_dirs = self._merge_background_cache_tree(child_source, child_destination)
                moved_files += int(child_files)
                moved_dirs += int(child_dirs)
            try:
                os.rmdir(source_path)
            except Exception:
                pass
            return moved_files, moved_dirs

        destination_parent = os.path.dirname(destination_path)
        if destination_parent:
            os.makedirs(destination_parent, exist_ok=True)
        try:
            if os.path.isdir(destination_path):
                shutil.rmtree(destination_path, ignore_errors=True)
            elif os.path.exists(destination_path):
                os.remove(destination_path)
        except Exception:
            pass
        shutil.move(source_path, destination_path)
        return 1, 0

    def _handoff_background_blend_cache(self, blend_copy_path):
        background_blendcache_dir = self._background_blendcache_dir(blend_copy_path)
        if not background_blendcache_dir or not os.path.isdir(background_blendcache_dir):
            return {}
        source_blend_path = self._source_blend_path_for_background_copy(blend_copy_path)
        if not source_blend_path or not os.path.exists(source_blend_path):
            return {}
        source_blendcache_dir = self._background_blendcache_dir(source_blend_path)
        if not source_blendcache_dir:
            return {}
        moved_files, moved_dirs = self._merge_background_cache_tree(background_blendcache_dir, source_blendcache_dir)
        if moved_files <= 0:
            return {}
        return {
            "imported_background_cache": True,
            "background_cache_source_dir": background_blendcache_dir,
            "background_cache_target_dir": source_blendcache_dir,
            "background_cache_moved_files": int(moved_files),
            "background_cache_moved_dirs": int(moved_dirs),
        }

    def _background_blend_sidecar_paths(self, blend_path):
        filepath = str(blend_path or "").strip()
        if not filepath:
            return []
        directory = os.path.dirname(filepath)
        stem = os.path.splitext(os.path.basename(filepath))[0]
        paths = [filepath]
        paths.extend(glob.glob(f"{filepath}[0-9]*"))
        if stem:
            paths.append(os.path.join(directory, f"blendcache_{stem}"))
        paths.append(f"{filepath}.af_reload_resume.json")
        return list(dict.fromkeys(path for path in paths if path))

    def _remove_background_blend_sidecars(self, blend_path):
        for path in self._background_blend_sidecar_paths(blend_path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                elif os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def _save_temporary_background_blend_copy(self, node, temp_dir):
        current_blend_path = str(getattr(bpy.data, "filepath", "") or "")
        has_saved_source = bool(current_blend_path) and os.path.exists(current_blend_path)
        if has_saved_source:
            source_dir = os.path.dirname(current_blend_path)
            source_stem = os.path.splitext(os.path.basename(current_blend_path))[0] or "automation_flow"
            temp_blend_path = os.path.join(source_dir, f"{source_stem}.af_bg_{uuid.uuid4().hex[:8]}.blend")
        else:
            temp_blend_path = os.path.join(temp_dir, f"automation_flow_background_{uuid.uuid4().hex[:8]}.blend")

        save_kwargs = {
            "filepath": temp_blend_path,
            "check_existing": False,
            "copy": True,
            "compress": False,
        }
        try:
            context_override = {key: value for key, value in self.ui_context.items() if value is not None}
            if context_override:
                with bpy.context.temp_override(**context_override):
                    result = bpy.ops.wm.save_as_mainfile(**save_kwargs)
            else:
                result = bpy.ops.wm.save_as_mainfile(**save_kwargs)
        except Exception as exc:
            raise FlowExecutionError("AF_E005", f"Failed to save temporary background .blend copy: {exc}", node.name)

        if "FINISHED" not in _operator_result_tokens(result):
            raise FlowExecutionError("AF_E005", "Failed to save temporary background .blend copy", node.name)
        if not os.path.exists(temp_blend_path):
            raise FlowExecutionError("AF_E005", "Temporary background .blend copy was not created", node.name)
        return temp_blend_path

    def _cleanup_background_task_plan_blend_copy(self, state, keep_artifacts=False):
        if not isinstance(state, dict):
            return
        handle = state.get("handle") or {}
        task_id = str(handle.get("task_id", "") or "")
        if task_id:
            process_entry = self.background_processes.get(task_id)
            if process_entry is not None:
                self._cleanup_background_process(task_id, keep_artifacts=keep_artifacts)
                if keep_artifacts:
                    return
        blend_copy_path = str(state.get("blend_copy_path", "") or "")
        if keep_artifacts:
            return
        if blend_copy_path:
            self._remove_background_blend_sidecars(blend_copy_path)
        temp_dir = str(state.get("temp_dir", "") or "")
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _cleanup_background_process(self, task_id, keep_artifacts=False):
        entry = self.background_processes.pop(str(task_id), None)
        if entry is None:
            return
        stdout_handle = entry.get("stdout_handle")
        if stdout_handle is not None:
            try:
                stdout_handle.close()
            except Exception:
                pass
        if keep_artifacts:
            return
        blend_copy_path = str(entry.get("blend_copy_path", "") or "")
        if blend_copy_path:
            self._remove_background_blend_sidecars(blend_copy_path)
        temp_dir = str(entry.get("temp_dir", "") or "")
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            return
        for key in ("script_path", "status_path", "log_path"):
            path = str(entry.get(key, "") or "")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
