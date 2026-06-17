import os
from pathlib import Path

import bpy

from ..runtime_bake import (
    _apply_geometry_bake_entry_settings,
    _apply_temporary_geometry_bake_settings,
    _call_operator_with_override,
    _clear_geometry_bake_tracked_packed_cache_state,
    _find_geometry_bake_entry_for_task,
    _restore_geometry_bake_entry_settings,
)
from ..runtime_core.constants import FlowExecutionError
from ..runtime_runner.core import FlowRunner
from ..runtime_state.cache import (
    _auto_flow_bake_action_has_cached_data,
    _find_auto_flow_bake_action_for_node,
)
from .editor_utils import _tag_flow_node_editor_redraw
from .bake_helpers import (
    _bake_task_int_input_value,
    _build_geometry_bake_task_ref_from_node,
    _build_physics_bake_task_ref_from_node,
    _find_supported_physics_modifier,
    _free_physics_cache_for_task_ref,
    _physics_context_modifier,
    _resolve_auto_flow_bake_target_node,
    _resolve_bake_task_node,
    _resolve_physics_bake_settings_node,
    _resolve_physics_bake_target_node,
    _resolve_physics_bake_task_path_from_context,
)


class AF_OT_CopyBakeTaskPath(bpy.types.Operator):
    bl_idname = "af.copy_bake_task_path"
    bl_label = "Copy Bake Task Path"
    bl_description = "Copy bake task path as ObjectName/ModifierName/BakeNodeName"

    task_path: bpy.props.StringProperty(name="Bake Task Path", default="")

    def execute(self, context):
        task_path = str(self.task_path or "").strip()
        if not task_path:
            self.report({"ERROR"}, "Bake task path is empty")
            return {"CANCELLED"}
        context.window_manager.clipboard = task_path
        self.report({"INFO"}, f"Copied Bake Task Path: {task_path}")
        return {"FINISHED"}


class AF_OT_CopyPhysicsBakeTaskPath(bpy.types.Operator):
    bl_idname = "af.copy_physics_bake_task_path"
    bl_label = "Copy Physics Bake Path"
    bl_description = "Copy physics bake path as ObjectName/ModifierName"

    object_name: bpy.props.StringProperty(name="Object Name", default="")
    modifier_name: bpy.props.StringProperty(name="Modifier Name", default="")

    @classmethod
    def poll(cls, context):
        return _physics_context_modifier(context) is not None or (
            bool(getattr(context, "object", None))
            and bool(getattr(getattr(context.object, "modifiers", None), "active", None))
        )

    def execute(self, context):
        task_path = _resolve_physics_bake_task_path_from_context(
            context,
            object_name=self.object_name,
            modifier_name=self.modifier_name,
        )
        if not task_path:
            self.report({"ERROR"}, "Supported physics bake modifier not found")
            return {"CANCELLED"}
        context.window_manager.clipboard = task_path
        self.report({"INFO"}, f"Copied Physics Bake Path: {task_path}")
        return {"FINISHED"}


class AF_OT_SelectBakeDirectory(bpy.types.Operator):
    bl_idname = "af.select_bake_directory"
    bl_label = "Select Bake Directory"
    bl_description = "Choose a directory for Geometry Nodes bake output"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")
    directory: bpy.props.StringProperty(name="Directory", subtype="DIR_PATH", default="")
    relative_path: bpy.props.BoolProperty(name="Use Relative Path", default=True)
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})
    filter_glob: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    filemode: bpy.props.IntProperty(default=8, options={"HIDDEN", "SKIP_SAVE"})

    def _resolve_target_node(self):
        return _resolve_bake_task_node(self.node_tree_name, self.node_name)

    def invoke(self, context, event):
        del event
        _node_tree, node = self._resolve_target_node()
        if node is None:
            self.report({"ERROR"}, "GN Bake Target node not found")
            return {"CANCELLED"}

        current_directory = str(getattr(node, "directory", "") or "").strip()
        if current_directory:
            browse_directory = bpy.path.abspath(current_directory)
            self.relative_path = current_directory.startswith("//")
        else:
            blend_filepath = str(getattr(bpy.data, "filepath", "") or "")
            browse_directory = os.path.dirname(blend_filepath) if blend_filepath else str(Path.home())
            self.relative_path = bool(blend_filepath)
        browse_directory = browse_directory or str(Path.home())
        browse_directory = os.path.normpath(browse_directory)
        if browse_directory and not browse_directory.endswith(os.sep):
            browse_directory += os.sep
        self.directory = browse_directory
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        del context
        self.layout.prop(self, "relative_path")

    def execute(self, context):
        del context
        _node_tree, node = self._resolve_target_node()
        if node is None:
            self.report({"ERROR"}, "GN Bake Target node not found")
            return {"CANCELLED"}

        selected_directory = str(self.directory or "").strip()
        if not selected_directory:
            self.report({"ERROR"}, "Bake directory is empty")
            return {"CANCELLED"}

        normalized_directory = os.path.normpath(bpy.path.abspath(selected_directory))
        if self.relative_path and str(getattr(bpy.data, "filepath", "") or "").strip():
            stored_directory = bpy.path.relpath(normalized_directory)
        else:
            stored_directory = normalized_directory
        node.directory = stored_directory
        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        return {"FINISHED"}


class AF_OT_ApplyGNBakeTargetSettings(bpy.types.Operator):
    bl_idname = "af.apply_gn_bake_target_settings"
    bl_label = "Apply GN Bake Target Settings"
    bl_description = "Apply this node's settings to the target Geometry Nodes bake node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        del context
        _node_tree, node = _resolve_bake_task_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "GN Bake Target node not found")
            return {"CANCELLED"}

        try:
            task_ref = _build_geometry_bake_task_ref_from_node(node)
            bake_entry = _find_geometry_bake_entry_for_task(task_ref, "applying GN Bake Target settings")
            _apply_geometry_bake_entry_settings(bake_entry, task_ref)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to apply GN Bake Target settings: {exc}")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        self.report({"INFO"}, "Applied GN Bake Target settings")
        return {"FINISHED"}


class AF_OT_FreeGNBakeCache(bpy.types.Operator):
    bl_idname = "af.free_gn_bake_cache"
    bl_label = "Free GN Bake Cache"
    bl_description = "Delete cache from the target Geometry Nodes bake node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        _node_tree, node = _resolve_bake_task_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "GN Bake Target node not found")
            return {"CANCELLED"}

        try:
            task_ref = _build_geometry_bake_task_ref_from_node(node)
            object_ref = task_ref["object_ref"]
            bake_entry = _find_geometry_bake_entry_for_task(task_ref, "freeing GN Bake cache")
            temporary_override = None
            original_state = None
            if bool(task_ref.get("apply_settings_on_run", False)):
                temporary_override, original_state = _apply_temporary_geometry_bake_settings(task_ref)
                bake_entry = temporary_override
            override = {
                "object": object_ref,
                "active_object": object_ref,
                "selected_objects": [object_ref],
                "selected_editable_objects": [object_ref],
                "scene": getattr(context, "scene", None) or bpy.context.scene,
                "view_layer": getattr(context, "view_layer", None) or bpy.context.view_layer,
            }
            payload = {
                "session_uid": int(object_ref.session_uid),
                "modifier_name": str(task_ref["modifier_name"]),
                "bake_id": int(task_ref["bake_id"]),
            }
            free_operators = ("object.geometry_node_bake_delete_single", "object.geometry_nodes_bake_delete_single")
            last_tokens = set()
            executed = False
            try:
                for op_path in free_operators:
                    namespace, name = op_path.split(".")
                    group = getattr(bpy.ops, namespace, None)
                    if group is None or not hasattr(group, name):
                        continue
                    operator = getattr(group, name)
                    try:
                        _result, tokens = _call_operator_with_override(operator, override, payload)
                    except Exception:
                        continue
                    last_tokens = set(tokens)
                    if "POLL_FAILED" in last_tokens:
                        continue
                    executed = True
                    if "FINISHED" in last_tokens:
                        _clear_geometry_bake_tracked_packed_cache_state(task_ref)
                        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
                        self.report({"INFO"}, "Freed GN Bake cache")
                        return {"FINISHED"}
                    if "CANCELLED" in last_tokens:
                        break
                if executed and "CANCELLED" in last_tokens:
                    _clear_geometry_bake_tracked_packed_cache_state(task_ref)
                    self.report({"INFO"}, "No GN Bake cache to free")
                    return {"CANCELLED"}
                self.report({"ERROR"}, "Failed to free GN Bake cache")
                return {"CANCELLED"}
            finally:
                if temporary_override is not None and original_state is not None:
                    _restore_geometry_bake_entry_settings(temporary_override, original_state)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to free GN Bake cache: {exc}")
            return {"CANCELLED"}


class AF_OT_FreeAutoFlowBakeCache(bpy.types.Operator):
    bl_idname = "af.free_auto_flow_bake_cache"
    bl_label = "Free Auto Flow Bake Cache"
    bl_description = "Delete recorded cache from the target Auto Flow Bake node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        del context
        _node_tree, node = _resolve_auto_flow_bake_target_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "Auto Flow Bake Target node not found")
            return {"CANCELLED"}

        try:
            action = _find_auto_flow_bake_action_for_node(node)
            if not _auto_flow_bake_action_has_cached_data(action):
                self.report({"INFO"}, "No Auto Flow Bake cache to free")
                return {"CANCELLED"}
            runner = FlowRunner(getattr(node, "id_data", None), getattr(bpy.context, "scene", None) or bpy.context.scene)
            runner._clear_auto_flow_bake_action_contents(action)
            _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
            self.report({"INFO"}, "Freed Auto Flow Bake cache")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to free Auto Flow Bake cache: {exc}")
            return {"CANCELLED"}


class AF_OT_ApplyPhysicsBakeSettings(bpy.types.Operator):
    bl_idname = "af.apply_physics_bake_settings"
    bl_label = "Apply Physics Bake Settings"
    bl_description = "Apply this node's frame range settings to the target physics modifier"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        del context
        _node_tree, node = _resolve_physics_bake_settings_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "Physics Bake Settings node not found")
            return {"CANCELLED"}
        try:
            task_ref = _build_physics_bake_task_ref_from_node(node)
            modifier = task_ref["object_ref"].modifiers.get(task_ref["modifier_name"])
            if modifier is None:
                self.report({"ERROR"}, "Supported physics bake modifier not found")
                return {"CANCELLED"}
            if str(task_ref["physics_type"]) in {"CLOTH", "SOFT_BODY"}:
                modifier.point_cache.frame_start = int(task_ref["frame_start"])
                modifier.point_cache.frame_end = int(task_ref["frame_end"])
            elif str(task_ref["physics_type"]) == "DYNAMIC_PAINT":
                canvas_settings = getattr(modifier, "canvas_settings", None)
                if canvas_settings is None:
                    self.report({"ERROR"}, "Supported physics bake modifier not found")
                    return {"CANCELLED"}
                for surface in canvas_settings.canvas_surfaces:
                    surface.frame_start = int(task_ref["frame_start"])
                    surface.frame_end = int(task_ref["frame_end"])
            else:
                self.report({"ERROR"}, "Supported physics bake modifier not found")
                return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to apply Physics Bake Settings: {exc}")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        self.report({"INFO"}, "Applied Physics Bake Settings")
        return {"FINISHED"}


class AF_OT_FreePhysicsBakeCache(bpy.types.Operator):
    bl_idname = "af.free_physics_bake_cache"
    bl_label = "Free Physics Bake Cache"
    bl_description = "Delete cache from the target physics modifier"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        _node_tree, node = _resolve_physics_bake_settings_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "Physics Bake Settings node not found")
            return {"CANCELLED"}
        try:
            task_ref = _build_physics_bake_task_ref_from_node(node)
            status, message = _free_physics_cache_for_task_ref(task_ref, context)
            if status == "NO_CACHE":
                self.report({"INFO"}, message)
                return {"CANCELLED"}
            if status == "UNSUPPORTED":
                self.report({"INFO"}, message)
                return {"CANCELLED"}
            if status != "FINISHED":
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to free Physics Bake cache: {exc}")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        self.report({"INFO"}, "Freed Physics Bake cache")
        return {"FINISHED"}


class AF_OT_FreeAllPhysicsBakeCaches(bpy.types.Operator):
    bl_idname = "af.free_all_physics_bake_caches"
    bl_label = "Free All Physics Caches"
    bl_description = "Delete cache from every linked target physics modifier"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree, node = _resolve_physics_bake_target_node(self.node_tree_name, self.node_name)
        if node is None:
            self.report({"ERROR"}, "Physics Bake Target node not found")
            return {"CANCELLED"}

        scene = getattr(context, "scene", None) or bpy.context.scene
        runner = FlowRunner(node_tree, scene) if scene is not None else None
        if runner is None:
            self.report({"ERROR"}, "Supported physics bake modifier not found")
            return {"CANCELLED"}

        try:
            payloads = runner._collect_physics_settings_payloads(node)
        except FlowExecutionError as exc:
            self.report({"ERROR"}, str(exc.message or exc))
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to collect Physics Bake Settings: {exc}")
            return {"CANCELLED"}

        if not payloads:
            self.report({"INFO"}, "No linked Physics Bake Settings to free")
            return {"CANCELLED"}

        freed_count = 0
        last_info_message = ""
        for task_ref in payloads:
            status, message = _free_physics_cache_for_task_ref(task_ref, context)
            last_info_message = message
            if status == "FINISHED":
                freed_count += 1
                continue
            if status in {"NO_CACHE", "UNSUPPORTED"}:
                continue
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        if freed_count > 0:
            self.report({"INFO"}, "Freed Physics Bake cache")
            return {"FINISHED"}
        if last_info_message:
            self.report({"INFO"}, last_info_message)
        else:
            self.report({"INFO"}, "No Physics Bake cache to free")
        return {"CANCELLED"}


BAKE_OPERATOR_CLASSES = (
    AF_OT_CopyBakeTaskPath,
    AF_OT_CopyPhysicsBakeTaskPath,
    AF_OT_SelectBakeDirectory,
    AF_OT_ApplyGNBakeTargetSettings,
    AF_OT_FreeGNBakeCache,
    AF_OT_FreeAutoFlowBakeCache,
    AF_OT_ApplyPhysicsBakeSettings,
    AF_OT_FreePhysicsBakeCache,
    AF_OT_FreeAllPhysicsBakeCaches,
)
