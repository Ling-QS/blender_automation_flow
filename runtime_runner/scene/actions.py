from ...runtime_core.constants import FLOW_OK, FlowExecutionError


class RuntimeSceneActionsMixin:
    def _execute_scene_action_node(self, node, dry_run=False, flow_test=False):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeSetActiveCamera":
            return self._execute_set_active_camera_node(node, dry_run=dry_run)
        if node_type == "AFNodeRenderTask":
            return self._execute_render_task_node(node, dry_run=dry_run, flow_test=flow_test)
        return None

    def _execute_set_active_camera_node(self, node, dry_run=False):
        scene = node.target_scene or self.scene
        camera = node.camera_object
        if camera is None or getattr(camera, "type", "") != "CAMERA":
            raise FlowExecutionError("AF_E001", "Camera object is not set or is invalid", node.name)
        if not dry_run:
            scene.camera = camera
        report = {"scene": scene.name, "camera": camera.name}
        self._set_output(node, "report", report)
        return FLOW_OK, camera.name

    def _execute_render_task_node(self, node, dry_run=False, flow_test=False):
        task_ref = self._build_render_task_ref(node)
        if dry_run or flow_test:
            report = {
                "scene": task_ref["scene_name"],
                "mode": task_ref["render_mode"],
                "simulated": True,
            }
            if dry_run:
                report["dry_run"] = True
            if flow_test:
                report["flow_test"] = True
        else:
            report = self._invoke_render_task_for_scene_actions(task_ref, self.scene, node.name)
        self._set_output(node, "report", report)
        return FLOW_OK, report.get("frame", report.get("frame_end", task_ref.get("frame")))


__all__ = ["RuntimeSceneActionsMixin"]
