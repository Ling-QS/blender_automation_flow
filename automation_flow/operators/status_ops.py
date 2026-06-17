import bpy


class AF_OT_SetStatusInputValue(bpy.types.Operator):
    bl_idname = "af.set_status_input_value"
    bl_label = "Set Status Input Value"
    bl_description = "Set the Status Input node value"

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")
    status_value: bpy.props.StringProperty(name="Status Value", default="")

    def execute(self, context):
        del context
        node_tree = bpy.data.node_groups.get(str(self.node_tree_name or "").strip())
        if node_tree is None:
            self.report({"ERROR"}, f"Node tree '{self.node_tree_name}' not found")
            return {"CANCELLED"}
        node = node_tree.nodes.get(str(self.node_name or "").strip())
        if node is None:
            self.report({"ERROR"}, f"Node '{self.node_name}' not found")
            return {"CANCELLED"}
        if getattr(node, "bl_idname", "") != "AFNodeStatusInput":
            self.report({"ERROR"}, "Target node is not a Status Input node")
            return {"CANCELLED"}
        try:
            node.status_value = str(self.status_value or "DONE")
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to set status value: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


STATUS_OPERATOR_CLASSES = (AF_OT_SetStatusInputValue,)
