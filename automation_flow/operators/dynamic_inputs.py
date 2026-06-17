import bpy

from .editor_utils import _tag_flow_node_editor_redraw


class AF_OT_RemoveLastTaskPlanInput(bpy.types.Operator):
    bl_idname = "af.remove_last_task_plan_input"
    bl_label = "Remove Last Task Plan Input"
    bl_description = "Remove the last real Task Plan input from this Run Task Plan node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeRunTaskPlan":
            self.report({"ERROR"}, "Run Task Plan node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _remove_last_run_task_plan_input
        except Exception as exc:
            self.report({"ERROR"}, f"Task Plan input helpers unavailable: {exc}")
            return {"CANCELLED"}

        removed = _remove_last_run_task_plan_input(node)
        if not removed:
            self.report({"INFO"}, "Run Task Plan must keep at least one Task Plan input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_AddTaskPlanInput(bpy.types.Operator):
    bl_idname = "af.add_task_plan_input"
    bl_label = "Add Task Plan Input"
    bl_description = "Add a new Task Plan input to this Run Task Plan node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeRunTaskPlan":
            self.report({"ERROR"}, "Run Task Plan node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _add_run_task_plan_input
        except Exception as exc:
            self.report({"ERROR"}, f"Task Plan input helpers unavailable: {exc}")
            return {"CANCELLED"}

        if not _add_run_task_plan_input(node):
            self.report({"ERROR"}, "Failed to add Task Plan input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_RemoveLastPropertyAssignmentInput(bpy.types.Operator):
    bl_idname = "af.remove_last_property_assignment_input"
    bl_label = "Remove Last Prop Assign Input"
    bl_description = "Remove the last real Prop Assign input from this Create Prop Pack node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeCreatePropertyPackage":
            self.report({"ERROR"}, "Create Prop Pack node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _remove_last_create_property_package_assignment_input
        except Exception as exc:
            self.report({"ERROR"}, f"Property Assignment helpers unavailable: {exc}")
            return {"CANCELLED"}

        removed = _remove_last_create_property_package_assignment_input(node)
        if not removed:
            self.report({"INFO"}, "Create Prop Pack must keep at least one Prop Assign input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_AddPropertyAssignmentInput(bpy.types.Operator):
    bl_idname = "af.add_property_assignment_input"
    bl_label = "Add Prop Assign Input"
    bl_description = "Add a new Prop Assign input to this Create Prop Pack node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeCreatePropertyPackage":
            self.report({"ERROR"}, "Create Prop Pack node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _add_create_property_package_assignment_input
        except Exception as exc:
            self.report({"ERROR"}, f"Property Assignment helpers unavailable: {exc}")
            return {"CANCELLED"}

        if not _add_create_property_package_assignment_input(node):
            self.report({"ERROR"}, "Failed to add Property Assignment input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_RemoveLastIndexSwitchInput(bpy.types.Operator):
    bl_idname = "af.remove_last_index_switch_input"
    bl_label = "Remove Last Index Switch Input"
    bl_description = "Remove the last real value input from this Index Switch node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeIndexSwitch":
            self.report({"ERROR"}, "Index Switch node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _remove_last_index_switch_input
        except Exception as exc:
            self.report({"ERROR"}, f"Index Switch helpers unavailable: {exc}")
            return {"CANCELLED"}

        removed = _remove_last_index_switch_input(node)
        if not removed:
            self.report({"INFO"}, "Index Switch must keep at least one value input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


class AF_OT_AddIndexSwitchInput(bpy.types.Operator):
    bl_idname = "af.add_index_switch_input"
    bl_label = "Add Index Switch Input"
    bl_description = "Add a new value input to this Index Switch node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}

        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeIndexSwitch":
            self.report({"ERROR"}, "Index Switch node not found")
            return {"CANCELLED"}

        try:
            from ..nodes import _add_index_switch_input
        except Exception as exc:
            self.report({"ERROR"}, f"Index Switch helpers unavailable: {exc}")
            return {"CANCELLED"}

        if not _add_index_switch_input(node):
            self.report({"ERROR"}, "Failed to add Index Switch input")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(node_tree.name)
        return {"FINISHED"}


DYNAMIC_INPUT_OPERATOR_CLASSES = (
    AF_OT_AddTaskPlanInput,
    AF_OT_RemoveLastTaskPlanInput,
    AF_OT_AddPropertyAssignmentInput,
    AF_OT_RemoveLastPropertyAssignmentInput,
    AF_OT_RemoveLastIndexSwitchInput,
    AF_OT_AddIndexSwitchInput,
)
