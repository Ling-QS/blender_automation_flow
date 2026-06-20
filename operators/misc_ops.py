import bpy

from .editor_utils import _tag_flow_node_editor_redraw
from .flow_run import _get_active_runner
from ..runtime_state.cache import _clear_flow_toggle_state


class AF_OT_StopFlow(bpy.types.Operator):
    bl_idname = "af.stop_flow"
    bl_label = "Stop Automation Flow"
    bl_description = "Request stop for current running flow"

    def execute(self, context):
        runner = _get_active_runner()
        if runner is None:
            self.report({"INFO"}, "No running flow")
            return {"CANCELLED"}
        runner.request_stop()
        return {"FINISHED"}


class AF_OT_ClearLogs(bpy.types.Operator):
    bl_idname = "af.clear_logs"
    bl_label = "Clear Flow Logs"
    bl_description = "Clear Automation Flow logs in the current scene"

    def execute(self, context):
        context.scene.af_flow_logs.clear()
        return {"FINISHED"}


class AF_OT_FocusNode(bpy.types.Operator):
    bl_idname = "af.focus_node"
    bl_label = "Focus Node"
    bl_description = "Focus the specified node in the current Automation Flow tree"

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        if not self.node_tree_name or not self.node_name:
            self.report({"ERROR"}, "Node tree or node name is missing")
            return {"CANCELLED"}

        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None:
            self.report({"ERROR"}, f"Node tree '{self.node_tree_name}' not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None:
            self.report({"ERROR"}, f"Node '{self.node_name}' not found")
            return {"CANCELLED"}

        target_area = None
        target_region = None
        target_space = None
        screen = context.screen
        if screen is None:
            self.report({"ERROR"}, "No active screen found")
            return {"CANCELLED"}

        for area in screen.areas:
            if area.type != "NODE_EDITOR":
                continue
            for space in area.spaces:
                if space.type != "NODE_EDITOR":
                    continue
                target_area = area
                target_space = space
                break
            if target_area is not None:
                break

        if target_area is None or target_space is None:
            self.report({"ERROR"}, "Open a Node Editor first")
            return {"CANCELLED"}

        for region in target_area.regions:
            if region.type == "WINDOW":
                target_region = region
                break
        if target_region is None:
            self.report({"ERROR"}, "Node Editor window region not found")
            return {"CANCELLED"}

        target_space.node_tree = node_tree
        for scan_node in node_tree.nodes:
            scan_node.select = False
        node.select = True
        node_tree.nodes.active = node

        try:
            with context.temp_override(
                window=context.window,
                screen=screen,
                area=target_area,
                region=target_region,
                space_data=target_space,
            ):
                bpy.ops.node.view_selected()
        except Exception:
            pass

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_ClearFlowToggleState(bpy.types.Operator):
    bl_idname = "af.clear_flow_toggle_state"
    bl_label = "Reset Flow Toggle State"
    bl_description = "Clear stored toggle state from this node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeFlowToggle":
            self.report({"ERROR"}, "Flow Toggle node not found")
            return {"CANCELLED"}

        scene = getattr(context, "scene", None) or bpy.context.scene
        if scene is None:
            self.report({"ERROR"}, "Scene is not available")
            return {"CANCELLED"}

        cleared_count = int(
            _clear_flow_toggle_state(
                scene,
                getattr(node_tree, "name", ""),
                getattr(node, "name", ""),
                clear_all_paths=True,
            )
            or 0
        )
        _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
        if cleared_count <= 0:
            self.report({"INFO"}, "No stored Flow Toggle state to clear")
            return {"FINISHED"}
        self.report({"INFO"}, "Cleared stored Flow Toggle state")
        return {"FINISHED"}


MISC_OPERATOR_CLASSES = (
    AF_OT_StopFlow,
    AF_OT_ClearLogs,
    AF_OT_FocusNode,
    AF_OT_ClearFlowToggleState,
)
