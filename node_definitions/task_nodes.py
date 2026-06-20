import bpy

from ..i18n import af_iface


def build_task_node_classes(
    *,
    AFBaseNode,
    BAKE_TASK_BAKE_MODE_ITEMS,
    BAKE_TASK_BAKE_TARGET_ITEMS,
    DEPENDENCY_SCOPE_ITEMS,
    DEPENDENCY_STRATEGY_ITEMS,
    RENDER_MODE_ITEMS,
    RUN_TASK_PLAN_FAILURE_POLICY_ITEMS,
    _camera_object_poll,
    _hide_default_auxiliary_outputs,
    _new_property_package_bake_asset_id,
    _set_default_node_width,
    _set_node_color,
    _sync_bake_target_sockets,
    _sync_evaluate_task_dependencies_sockets,
    _sync_physics_bake_target_sockets,
    _sync_render_target_sockets,
    _sync_run_background_task_plan_sockets,
    _sync_run_task_plan_sockets,
    _sync_task_step_sockets,
    iface_,
):
    class AFNodeResolveTaskRef(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeResolveTaskRef"
        bl_label = "Resolve Task Ref"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketObjectList", "Task Objects")
            self.outputs.new("NodeSocketInt", "Frame Start")
            self.outputs.new("NodeSocketInt", "Frame End")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            status_socket = self.outputs.get("Status")
            if status_socket is not None:
                try:
                    status_socket.hide = False
                except Exception:
                    pass
            _set_node_color(self, "GEOMETRY")

    class AFNodeBakeTask(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBakeTask"
        bl_label = "GN Bake Target"
        bl_icon = "BLANK1"

        bake_task_path: bpy.props.StringProperty(name="Bake Task Path", default="")
        apply_settings_on_run: bpy.props.BoolProperty(name="Override Settings", default=True)
        free_before_bake: bpy.props.BoolProperty(name="Free Before Bake", default=False)
        bake_mode: bpy.props.EnumProperty(name="Bake Mode", items=BAKE_TASK_BAKE_MODE_ITEMS, default="ANIMATION")
        bake_target: bpy.props.EnumProperty(name="Bake Target", items=BAKE_TASK_BAKE_TARGET_ITEMS, default="INHERIT")
        use_custom_path: bpy.props.BoolProperty(name="Use Custom Path", default=False)
        directory: bpy.props.StringProperty(name="Directory", default="")
        use_custom_simulation_frame_range: bpy.props.BoolProperty(name="Use Custom Frame Range", default=True)

        def init(self, context):
            frame_start_socket = self.inputs.new("NodeSocketInt", "Frame Start")
            frame_end_socket = self.inputs.new("NodeSocketInt", "Frame End")
            frame_start_socket.default_value = 1
            frame_end_socket.default_value = 250
            self.outputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketObjectList", "Bake Objects")
            self.outputs.new("AFSocketReport", "Report")
            _sync_bake_target_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "bake_task_path", text="", placeholder="Bake Task Path")
            behavior_col = layout.column(align=True)
            override_row = behavior_col.row(align=True)
            override_row.prop(self, "apply_settings_on_run")
            override_op = override_row.operator("af.apply_gn_bake_target_settings", text=iface_("Override"))
            if override_op is not None:
                override_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                override_op.node_name = self.name
            free_row = behavior_col.row(align=True)
            free_row.prop(self, "free_before_bake")
            free_op = free_row.operator("af.free_gn_bake_cache", text=iface_("Free Cache"))
            if free_op is not None:
                free_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                free_op.node_name = self.name
            mode_row = layout.row(align=True)
            mode_row.prop(self, "bake_mode", expand=True)
            layout.prop(self, "bake_target", text="")
            path_col = layout.column(align=True)
            path_col.prop(self, "use_custom_path")
            if self.use_custom_path:
                directory_row = path_col.row(align=True)
                directory_row.prop(self, "directory", text="")
                browse_op = directory_row.operator("af.select_bake_directory", text="", icon="FILE_FOLDER")
                if browse_op is not None:
                    browse_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                    browse_op.node_name = self.name
            layout.prop(self, "use_custom_simulation_frame_range")

    class AFNodePropertyPackageBakeTarget(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePropertyPackageBakeTarget"
        bl_label = "Property Package Bake Target"
        bl_icon = "BLANK1"

        # Legacy field kept only so old data blocks still load; cache identity now lives on Record Property Package.
        bake_asset_id: bpy.props.StringProperty(name="Bake Asset ID", default="", options={"HIDDEN"})
        free_before_bake: bpy.props.BoolProperty(name="Free Before Bake", default=False)
        restore_current_frame: bpy.props.BoolProperty(
            name="Restore Current Frame",
            default=True,
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketTaskRef", "Task Ref")
            frame_start_socket = self.inputs.new("NodeSocketInt", "Frame Start")
            frame_end_socket = self.inputs.new("NodeSocketInt", "Frame End")
            frame_start_socket.default_value = 1
            frame_end_socket.default_value = 250
            self.outputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "TASK")

        def draw_label(self):
            return af_iface("Property Package Bake Target", compact=True)

        def draw_buttons(self, context, layout):
            del context
            behavior_col = layout.column(align=True)
            free_row = behavior_col.row(align=True)
            free_row.prop(self, "free_before_bake")
            free_op = free_row.operator("af.free_property_package_bake_cache", text=iface_("Free Cache"))
            if free_op is not None:
                free_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                free_op.node_name = self.name
            layout.prop(self, "restore_current_frame")

        def copy(self, node):
            del node
            self.bake_asset_id = ""

    class AFNodeTaskStep(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTaskStep"
        bl_label = "Task Step"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def update(self):
            _sync_task_step_sockets(self)

    class AFNodePhysicsBakeSettings(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePhysicsBakeSettings"
        bl_label = "Physics Bake Settings"
        bl_icon = "BLANK1"

        physics_task_path: bpy.props.StringProperty(name="Bake Task Path", default="")
        override_settings: bpy.props.BoolProperty(name="Override Settings", default=True)
        free_before_bake: bpy.props.BoolProperty(name="Free Before Bake", default=False)
        disk_cache: bpy.props.BoolProperty(name="Disk Cache", default=False)

        def init(self, context):
            frame_start_socket = self.inputs.new("NodeSocketInt", "Frame Start")
            frame_end_socket = self.inputs.new("NodeSocketInt", "Frame End")
            frame_start_socket.default_value = 1
            frame_end_socket.default_value = 250
            self.outputs.new("AFSocketPropertyPackage", "Physics Bake Settings")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            path_row = layout.row(align=True)
            path_row.prop(self, "physics_task_path", text="", placeholder="Bake Task Path")
            behavior_col = layout.column(align=True)
            override_row = behavior_col.row(align=True)
            override_row.prop(self, "override_settings")
            override_op = override_row.operator("af.apply_physics_bake_settings", text=iface_("Override"))
            if override_op is not None:
                override_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                override_op.node_name = self.name
            free_row = behavior_col.row(align=True)
            free_row.prop(self, "free_before_bake")
            free_op = free_row.operator("af.free_physics_bake_cache", text=iface_("Free Cache"))
            if free_op is not None:
                free_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                free_op.node_name = self.name
            behavior_col.prop(self, "disk_cache")

    class AFNodePhysicsBakeTask(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodePhysicsBakeTask"
        bl_label = "Physics Bake Target"
        bl_icon = "BLANK1"

        free_before_bake: bpy.props.BoolProperty(name="Free Before Bake", default=False)
        disk_cache: bpy.props.BoolProperty(name="Disk Cache", default=False)
        override_frame_range: bpy.props.BoolProperty(
            name="Override Frame Range",
            default=False,
            update=lambda self, context: self.sync_inputs(),
        )

        def init(self, context):
            frame_start_socket = self.inputs.new("NodeSocketInt", "Frame Start")
            frame_end_socket = self.inputs.new("NodeSocketInt", "Frame End")
            frame_start_socket.default_value = 1
            frame_end_socket.default_value = 250
            self.outputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketObjectList", "Bake Objects")
            self.outputs.new("AFSocketReport", "Report")
            _sync_physics_bake_target_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            free_row = layout.row(align=True)
            free_row.prop(self, "free_before_bake")
            free_op = free_row.operator("af.free_all_physics_bake_caches", text=iface_("Free All"))
            if free_op is not None:
                free_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                free_op.node_name = self.name
            layout.prop(self, "disk_cache")
            layout.prop(self, "override_frame_range")

        def sync_inputs(self):
            _sync_physics_bake_target_sockets(self)

    class AFNodeEvaluateTaskDependencies(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeEvaluateTaskDependencies"
        bl_label = "Evaluate Object Dependencies"
        bl_icon = "BLANK1"

        dependency_scope: bpy.props.EnumProperty(name="Scope", items=DEPENDENCY_SCOPE_ITEMS, default="FULL_CLOSURE")
        dependency_strategy: bpy.props.EnumProperty(
            name="Strategy",
            items=DEPENDENCY_STRATEGY_ITEMS,
            default="STATIC_PLUS_DEPSGRAPH",
        )
        include_self: bpy.props.BoolProperty(name="Include Self", default=True)

        def draw_label(self):
            try:
                language = str(getattr(getattr(bpy.context, "preferences", None), "view", None).language or "")
            except Exception:
                language = ""
            if language.startswith("zh"):
                return iface_("Evaluate Object Dependencies")
            return "Eval Dependencies"

        def init(self, context):
            self.inputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _sync_evaluate_task_dependencies_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            scope_row = layout.row(align=True)
            scope_row.prop(self, "dependency_scope", expand=True)
            layout.prop(self, "dependency_strategy", text="")
            layout.separator()
            layout.prop(self, "include_self")

    class AFNodeRunTaskPlan(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRunTaskPlan"
        bl_label = "Run Task"
        bl_icon = "BLANK1"

        failure_policy: bpy.props.EnumProperty(
            name="Failure Policy",
            items=RUN_TASK_PLAN_FAILURE_POLICY_ITEMS,
            default="STOP_ON_FAILURE",
        )

        def init(self, context):
            self.inputs.new("AFSocketFlow", "Flow In")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _sync_run_task_plan_sockets(self)
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "failure_policy", text="")

        def update(self):
            _sync_run_task_plan_sockets(self)

    class AFNodeRunBackgroundTaskPlan(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRunBackgroundTaskPlan"
        bl_label = "Run Background Task"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketTaskPlan", "Task Plan")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketTaskHandle", "Task Handle")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _sync_run_background_task_plan_sockets(self)
            _hide_default_auxiliary_outputs(self)

    class AFNodeSetActiveCamera(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSetActiveCamera"
        bl_label = "Set Active Camera"
        bl_icon = "BLANK1"

        target_scene: bpy.props.PointerProperty(type=bpy.types.Scene)
        camera_object: bpy.props.PointerProperty(type=bpy.types.Object, poll=_camera_object_poll)

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_scene", text="")
            layout.prop(self, "camera_object", text="")

    class AFNodeRenderTarget(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRenderTarget"
        bl_label = "Render Target"
        bl_icon = "BLANK1"

        target_scene: bpy.props.PointerProperty(type=bpy.types.Scene)
        render_mode: bpy.props.EnumProperty(name="Mode", items=RENDER_MODE_ITEMS, default="STILL")
        frame: bpy.props.IntProperty(name="Frame", default=1)
        override_frame_range: bpy.props.BoolProperty(name="Override Frame Range", default=False)
        frame_start: bpy.props.IntProperty(name="Frame Start", default=1)
        frame_end: bpy.props.IntProperty(name="Frame End", default=250)
        write_still: bpy.props.BoolProperty(name="Write Still", default=True)
        use_viewport: bpy.props.BoolProperty(name="Use Viewport", default=False)

        def init(self, context):
            del context
            _sync_render_target_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_scene", text="")
            layout.prop(self, "render_mode", text="")
            if self.render_mode == "STILL":
                layout.prop(self, "write_still")
            layout.prop(self, "use_viewport")

        def update(self):
            _sync_render_target_sockets(self)

    class AFNodeRenderTask(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRenderTask"
        bl_label = "Render Target"
        bl_icon = "BLANK1"

        target_scene: bpy.props.PointerProperty(type=bpy.types.Scene)
        render_mode: bpy.props.EnumProperty(name="Mode", items=RENDER_MODE_ITEMS, default="STILL")
        frame: bpy.props.IntProperty(name="Frame", default=1)
        override_frame_range: bpy.props.BoolProperty(name="Override Frame Range", default=False)
        frame_start: bpy.props.IntProperty(name="Frame Start", default=1)
        frame_end: bpy.props.IntProperty(name="Frame End", default=250)
        write_still: bpy.props.BoolProperty(name="Write Still", default=True)
        use_viewport: bpy.props.BoolProperty(name="Use Viewport", default=False)

        def init(self, context):
            del context
            _sync_render_target_sockets(self)
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_scene", text="")
            layout.prop(self, "render_mode", text="")
            if self.render_mode == "STILL":
                layout.prop(self, "write_still")
            layout.prop(self, "use_viewport")

        def update(self):
            _sync_render_target_sockets(self)

    class AFNodeWaitForTask(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeWaitForTask"
        bl_label = "Wait For Task"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketTaskHandle", "Task Handle")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

    class AFNodeDelayWait(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeDelayWait"
        bl_label = "Delay Wait"
        bl_icon = "BLANK1"

        delay_seconds: bpy.props.FloatProperty(name="Delay (sec)", default=0.0, min=0.0)
        poll_interval_ms: bpy.props.IntProperty(name="Poll Interval (ms)", default=0, min=0)

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.outputs.new("AFSocketFlow", "Flow Out")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "delay_seconds")
            layout.prop(self, "poll_interval_ms")

    class AFNodeReloadAfterTask(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeReloadAfterTask"
        bl_label = "Reload After Task"
        bl_icon = "BLANK1"

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketTaskHandle", "Task Handle")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("NodeSocketString", "Status")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

    return {
        "AFNodeResolveTaskRef": AFNodeResolveTaskRef,
        "AFNodeBakeTask": AFNodeBakeTask,
        "AFNodePropertyPackageBakeTarget": AFNodePropertyPackageBakeTarget,
        "AFNodeTaskStep": AFNodeTaskStep,
        "AFNodePhysicsBakeSettings": AFNodePhysicsBakeSettings,
        "AFNodePhysicsBakeTask": AFNodePhysicsBakeTask,
        "AFNodeEvaluateTaskDependencies": AFNodeEvaluateTaskDependencies,
        "AFNodeRunTaskPlan": AFNodeRunTaskPlan,
        "AFNodeRunBackgroundTaskPlan": AFNodeRunBackgroundTaskPlan,
        "AFNodeSetActiveCamera": AFNodeSetActiveCamera,
        "AFNodeRenderTarget": AFNodeRenderTarget,
        "AFNodeRenderTask": AFNodeRenderTask,
        "AFNodeWaitForTask": AFNodeWaitForTask,
        "AFNodeDelayWait": AFNodeDelayWait,
        "AFNodeReloadAfterTask": AFNodeReloadAfterTask,
    }
