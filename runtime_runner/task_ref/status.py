import uuid

from ...runtime_core.constants import (
    PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE,
    FlowExecutionError,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ...runtime_state.cache import (
    _property_package_bake_action_frame_range,
    _property_package_bake_action_has_cached_data,
)
from ...runtime_task_target import (
    _geometry_bake_has_existing_cache as _geometry_bake_has_existing_cache_impl,
    _geometry_bake_has_existing_cache_for_current_entry as _geometry_bake_has_existing_cache_for_current_entry_impl,
    _physics_bake_all_has_pending_work as _physics_bake_all_has_pending_work_impl,
    _physics_task_has_existing_cache as _physics_task_has_existing_cache_impl,
)


class RuntimeTaskRefStatusMixin:
    def _geometry_bake_has_existing_cache(self, task_ref, scene, bake_entry):
        return _geometry_bake_has_existing_cache_impl(
            task_ref,
            scene,
            bake_entry,
            get_geometry_bake_tracked_packed_cache_status=self._get_geometry_bake_tracked_packed_cache_status,
        )

    def _geometry_bake_has_existing_cache_for_current_entry(self, task_ref, scene, bake_entry):
        return _geometry_bake_has_existing_cache_for_current_entry_impl(
            task_ref,
            scene,
            bake_entry,
            get_geometry_bake_tracked_packed_cache_status=self._get_geometry_bake_tracked_packed_cache_status,
        )

    def _physics_task_has_existing_cache(self, task_ref):
        return _physics_task_has_existing_cache_impl(
            task_ref,
            point_cache_has_existing_cache=self._point_cache_has_existing_cache,
        )

    def _physics_bake_all_has_pending_work(self, task_ref):
        return _physics_bake_all_has_pending_work_impl(
            task_ref,
            physics_task_has_existing_cache=self._physics_task_has_existing_cache,
        )

    def _embed_task_ref_status_payload(self, node, task_ref):
        task_ref = self._rehydrate_task_ref_object_references(task_ref, scene=self.scene)
        task_ref = self._raise_if_invalid_task_ref(task_ref, node.name)
        task_ref = self._validate_task_ref_object_targets(task_ref, node.name)
        task_kind = str(task_ref.get("task_kind", TASK_KIND_GEOMETRY) or TASK_KIND_GEOMETRY)
        supported_kinds = {
            TASK_KIND_GEOMETRY,
            TASK_KIND_PHYSICS,
            TASK_KIND_PHYSICS_BAKE_ALL,
            TASK_KIND_RENDER,
            TASK_KIND_PROPERTY_PACKAGE_BAKE,
        }
        if task_kind not in supported_kinds:
            raise FlowExecutionError("AF_E011", f"Task kind '{task_kind}' is not supported", node.name)

        frame_start, frame_end = self._frame_range_from_task_ref(task_ref, self.scene)
        if task_kind == TASK_KIND_PROPERTY_PACKAGE_BAKE and bool(task_ref.get("prediction_skipped", False)):
            object_count = int(len(list(task_ref.get("predicted_object_items", []) or [])))
        else:
            object_list = self._object_list_from_task_ref(task_ref, "NAME_ASC", self.scene)
            object_count = int(object_list.get("count", 0))
        status_value = "READY"
        report = {
            "status": status_value,
            "task_kind": task_kind,
            "object_count": int(object_count or 0),
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
        }

        if task_kind == TASK_KIND_GEOMETRY:
            bake_entry = self._find_geometry_bake_entry_for_task(task_ref, "building task ref status")
            if not bool(task_ref.get("free_before_bake", False)):
                if bool(task_ref.get("apply_settings_on_run", False)):
                    if self._geometry_bake_has_existing_cache(task_ref, self.scene, bake_entry):
                        status_value = "SKIPPED"
                elif self._geometry_bake_has_existing_cache_for_current_entry(task_ref, self.scene, bake_entry):
                    status_value = "SKIPPED"
        elif task_kind == TASK_KIND_PHYSICS:
            if not bool(task_ref.get("free_before_bake", False)) and self._physics_task_has_existing_cache(task_ref):
                status_value = "SKIPPED"
        elif task_kind == TASK_KIND_PHYSICS_BAKE_ALL:
            if not self._physics_bake_all_has_pending_work(task_ref):
                status_value = "SKIPPED"
        elif task_kind == TASK_KIND_PROPERTY_PACKAGE_BAKE:
            if int(frame_end) < int(frame_start):
                raise FlowExecutionError("AF_E020", "Frame End cannot be less than Frame Start", node.name)
            ref_role = str(task_ref.get("property_package_bake_ref_role", "") or "").strip().upper()
            if ref_role != PROPERTY_PACKAGE_BAKE_TASK_REF_ROLE_SOURCE:
                existing_action = self._find_property_package_bake_action(
                    str(task_ref.get("bake_asset_id", "") or ""),
                    str(task_ref.get("action_name", "") or ""),
                )
                if not bool(task_ref.get("free_before_bake", False)) and _property_package_bake_action_has_cached_data(existing_action):
                    status_value = "SKIPPED"
                    cache_frame_range = _property_package_bake_action_frame_range(existing_action)
                    if cache_frame_range is not None:
                        report["cache_frame_start"] = int(cache_frame_range[0])
                        report["cache_frame_end"] = int(cache_frame_range[1])
        elif task_kind == TASK_KIND_RENDER and task_ref.get("scene_ref") is None:
            raise FlowExecutionError("AF_E001", "Target scene is missing", node.name)

        report["status"] = status_value
        if status_value == "SKIPPED":
            report["skipped"] = True
        task_ref["status"] = status_value
        task_ref["report"] = report
        return task_ref

    def _task_kind_for_task_ref_node(self, node):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeBakeTask":
            return TASK_KIND_GEOMETRY
        if node_type == "AFNodePhysicsBakeTask":
            return TASK_KIND_PHYSICS_BAKE_ALL
        if node_type in {"AFNodeRenderTarget", "AFNodeRenderTask"}:
            return TASK_KIND_RENDER
        if node_type in {"AFNodePropertyPackageBakeTarget", "AFNodeRecordPropertyPackage"}:
            return TASK_KIND_PROPERTY_PACKAGE_BAKE
        return ""

    def _task_ref_source_tree_name(self, node):
        return str(getattr(getattr(node, "id_data", None), "name", self.node_tree.name) or self.node_tree.name)

    def _task_ref_frame_range_fallback(self, node, task_kind):
        fallback_start = int(getattr(self.scene, "frame_start", 1))
        fallback_end = int(getattr(self.scene, "frame_end", fallback_start))
        try:
            if task_kind == TASK_KIND_GEOMETRY:
                return (
                    int(self._input_int(node, "Frame Start", 1)),
                    int(self._input_int(node, "Frame End", 250)),
                )
            if task_kind == TASK_KIND_PROPERTY_PACKAGE_BAKE:
                frame_start = int(self._input_int(node, "Frame Start", fallback_start))
                frame_end = int(self._input_int(node, "Frame End", getattr(self.scene, "frame_end", frame_start)))
                return frame_start, frame_end
            if task_kind == TASK_KIND_RENDER:
                return (
                    int(self._input_int(node, "Frame Start", int(getattr(node, "frame_start", fallback_start)))),
                    int(self._input_int(node, "Frame End", int(getattr(node, "frame_end", fallback_end)))),
                )
            if task_kind == TASK_KIND_PHYSICS_BAKE_ALL and bool(getattr(node, "override_frame_range", False)):
                return (
                    int(self._input_int(node, "Frame Start", fallback_start)),
                    int(self._input_int(node, "Frame End", fallback_end)),
                )
        except Exception:
            pass
        return fallback_start, fallback_end

    def _make_invalid_task_ref_payload(self, node, error):
        task_kind = self._task_kind_for_task_ref_node(node)
        frame_start, frame_end = self._task_ref_frame_range_fallback(node, task_kind)
        if isinstance(error, FlowExecutionError):
            error_code = str(error.code or "AF_E011")
            error_message = str(error.message or "Task Ref is invalid")
        else:
            error_code = "AF_E009"
            error_message = str(error or "Task Ref is invalid")
        report = {
            "status": "INVALID",
            "task_kind": task_kind,
            "object_count": 0,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
            "error_code": error_code,
            "error_message": error_message,
        }
        return {
            "task_kind": task_kind,
            "task_uid": str(uuid.uuid4()),
            "source_node": str(getattr(node, "name", "") or ""),
            "source_tree_name": self._task_ref_source_tree_name(node),
            "status": "INVALID",
            "report": report,
            "frame_start": int(frame_start),
            "frame_end": int(frame_end),
        }


__all__ = ["RuntimeTaskRefStatusMixin"]
