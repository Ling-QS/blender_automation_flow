import bpy
from bpy.app.translations import pgettext_iface as iface_


def build_flow_node_classes(
    *,
    AFBaseNode,
    _group_tree_poll,
    _group_tree_updated,
    _hide_default_auxiliary_outputs,
    _initialize_start_node,
    _start_node_active_updated,
    _start_node_auto_order_updated,
    _start_node_auto_follow_updated,
    _sync_group_node_sockets,
    _ui_runner_for_node,
):
    class AFNodeGroup(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeGroup"
        bl_label = "Group"
        bl_icon = "NODETREE"

        group_tree: bpy.props.PointerProperty(
            name="Group Tree",
            type=bpy.types.NodeTree,
            poll=_group_tree_poll,
            update=_group_tree_updated,
        )

        def init(self, context):
            del context
            _sync_group_node_sockets(self)

        def draw_buttons(self, context, layout):
            del context
            row = layout.row()
            row.template_ID(self, "group_tree")

        def draw_buttons_ext(self, context, layout):
            self.draw_buttons(context, layout)

        def draw_label(self):
            if self.group_tree is not None and str(self.group_tree.name).strip():
                return self.group_tree.name
            return self.bl_label

    class AFNodeStart(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeStart"
        bl_label = "Start"
        bl_icon = "BLANK1"

        is_active_start: bpy.props.BoolProperty(
            name="Enabled",
            default=True,
            update=_start_node_active_updated,
        )
        auto_follow_enabled: bpy.props.BoolProperty(
            name="Auto Follow",
            default=False,
            update=_start_node_auto_follow_updated,
        )
        auto_order: bpy.props.IntProperty(
            name="Auto Order",
            description="Lower values run earlier when multiple Auto starts are waiting",
            default=0,
            soft_min=-99,
            soft_max=99,
            update=_start_node_auto_order_updated,
        )
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.outputs.new("AFSocketFlow", "Flow Out")
            _initialize_start_node(self)

        def draw_buttons(self, context, layout):
            row = layout.row(align=True)
            dry_run_op = row.operator("af.run_start_node", text="", icon="CONSOLE")
            if dry_run_op is not None:
                dry_run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                dry_run_op.start_node_name = self.name
                dry_run_op.run_mode_override = "DRY_RUN"
            flow_test_op = row.operator("af.run_start_node", text="", icon="MOD_SIMPLIFY")
            if flow_test_op is not None:
                flow_test_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                flow_test_op.start_node_name = self.name
                flow_test_op.run_mode_override = "FLOW_TEST"
            manual_row = row.row(align=True)
            manual_row.enabled = not bool(getattr(self, "auto_follow_enabled", False))
            manual_row.prop(self, "is_active_start", text="", toggle=True, icon="CHECKMARK")
            row.prop(self, "auto_follow_enabled", text="", toggle=True, icon="FILE_REFRESH")
            run_op = row.operator("af.run_start_node", text="", icon="PLAY")
            if run_op is not None:
                run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                run_op.start_node_name = self.name
                run_op.run_mode_override = "NORMAL"
            if bool(getattr(self, "auto_follow_enabled", False)):
                order_row = layout.row(align=True)
                order_row.prop(self, "auto_order", text="Auto Order")

    class AFNodeFlowToggle(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeFlowToggle"
        bl_label = "FlowToggle"
        bl_icon = "BLANK1"

        default_value: bpy.props.BoolProperty(
            name="Initial State",
            default=False,
        )
        current_state_display: bpy.props.BoolProperty(
            name="Current State",
            get=lambda self: self._ui_current_state_value(),
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Trigger")
            self.outputs.new("NodeSocketBool", "State")

        def draw_buttons(self, context, layout):
            row = layout.row(align=True)
            row.prop(self, "default_value", text=iface_("Initial"), toggle=True)
            current_value = bool(self._ui_current_state_value())
            current_op = row.operator(
                "af.clear_flow_toggle_state",
                text=iface_("Current"),
                depress=current_value,
            )
            if current_op is not None:
                current_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                current_op.node_name = self.name

        def _ui_current_state_value(self):
            try:
                runner = _ui_runner_for_node(self, bpy.context)
                if runner is not None:
                    return bool(runner._read_flow_toggle_state(self, getattr(runner, "current_group_path", None)))
            except Exception:
                pass
            return bool(getattr(self, "default_value", False))

    class AFNodeRepeatStart(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRepeatStart"
        bl_label = "Repeat Start"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            count_socket = self.inputs.new("NodeSocketInt", "Count")
            count_socket.default_value = 1
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("NodeSocketInt", "Index")

    class AFNodeRepeatEnd(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRepeatEnd"
        bl_label = "Repeat End"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.outputs.new("AFSocketFlow", "Flow Out")

    class AFNodeSubflowStart(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSubflowStart"
        bl_label = "Subflow Start"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.outputs.new("AFSocketFlow", "Subflow")

        def draw_buttons(self, context, layout):
            del context
            row = layout.row(align=True)
            dry_run_op = row.operator("af.run_subflow_start", text="", icon="CONSOLE")
            if dry_run_op is not None:
                dry_run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                dry_run_op.subflow_start_name = self.name
                dry_run_op.run_mode_override = "DRY_RUN"
            flow_test_op = row.operator("af.run_subflow_start", text="", icon="MOD_SIMPLIFY")
            if flow_test_op is not None:
                flow_test_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                flow_test_op.subflow_start_name = self.name
                flow_test_op.run_mode_override = "FLOW_TEST"
            run_op = row.operator("af.run_subflow_start", text="", icon="PLAY")
            if run_op is not None:
                run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                run_op.subflow_start_name = self.name
                run_op.run_mode_override = "NORMAL"

    class AFNodeSubflowJoin(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSubflowJoin"
        bl_label = "Subflow Join"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            trigger_socket = self.inputs.new("NodeSocketBool", "Trigger")
            trigger_socket.default_value = False
            self.inputs.new("AFSocketFlow", "Subflow")
            self.outputs.new("AFSocketFlow", "Flow Out")

    class AFNodeBranchStart(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBranchStart"
        bl_label = "Branch Start"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            trigger_socket = self.inputs.new("NodeSocketBool", "Trigger")
            trigger_socket.default_value = False
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketFlow", "Branch Flow")

        def draw_buttons(self, context, layout):
            del context
            row = layout.row(align=True)
            dry_run_op = row.operator("af.run_branch_start", text="", icon="CONSOLE")
            if dry_run_op is not None:
                dry_run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                dry_run_op.branch_start_name = self.name
                dry_run_op.run_mode_override = "DRY_RUN"
            flow_test_op = row.operator("af.run_branch_start", text="", icon="MOD_SIMPLIFY")
            if flow_test_op is not None:
                flow_test_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                flow_test_op.branch_start_name = self.name
                flow_test_op.run_mode_override = "FLOW_TEST"
            run_op = row.operator("af.run_branch_start", text="", icon="PLAY")
            if run_op is not None:
                run_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                run_op.branch_start_name = self.name
                run_op.run_mode_override = "NORMAL"

    class AFNodeBranchEnd(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeBranchEnd"
        bl_label = "Branch End"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Branch Flow")
            status_input = self.inputs.new("NodeSocketString", "Status")
            try:
                status_input.hide_value = True
            except Exception:
                pass

    class AFNodeEnd(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeEnd"
        bl_label = "End"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")

    class AFNodeTaskStart(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTaskStart"
        bl_label = "Task Start"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.outputs.new("AFSocketFlow", "Flow Out")

    class AFNodeTaskOutput(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeTaskOutput"
        bl_label = "Task Output"
        bl_icon = "BLANK1"
        af_pair_id: bpy.props.StringProperty(name="Pair ID", default="", options={"HIDDEN"})
        af_pair_auto_managed: bpy.props.BoolProperty(name="Auto Pair", default=False, options={"HIDDEN"})
        af_pair_duplicate_pending: bpy.props.BoolProperty(name="Pair Duplicate Pending", default=False, options={"HIDDEN"})
        af_pair_duplicate_offset: bpy.props.FloatVectorProperty(
            name="Pair Duplicate Offset",
            size=2,
            default=(0.0, 0.0),
            options={"HIDDEN"},
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            status_input = self.inputs.new("NodeSocketString", "Status")
            try:
                status_input.hide_value = True
            except Exception:
                pass
            self.outputs.new("AFSocketTaskPlan", "Task Plan")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

    return {
        "AFNodeGroup": AFNodeGroup,
        "AFNodeStart": AFNodeStart,
        "AFNodeFlowToggle": AFNodeFlowToggle,
        "AFNodeRepeatStart": AFNodeRepeatStart,
        "AFNodeRepeatEnd": AFNodeRepeatEnd,
        "AFNodeSubflowStart": AFNodeSubflowStart,
        "AFNodeSubflowJoin": AFNodeSubflowJoin,
        "AFNodeBranchStart": AFNodeBranchStart,
        "AFNodeBranchEnd": AFNodeBranchEnd,
        "AFNodeEnd": AFNodeEnd,
        "AFNodeTaskStart": AFNodeTaskStart,
        "AFNodeTaskOutput": AFNodeTaskOutput,
    }
