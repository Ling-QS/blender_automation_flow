import bpy

from .editor_utils import (
    _get_active_flow_tree,
    _invoke_node_translate_attach,
    _node_editor_cursor_location,
    _select_active_node,
    _set_node_editor_cursor_from_event,
    _tag_flow_node_editor_redraw,
)
from .group_assets import _ensure_group_asset_tree
from .group_helpers import (
    GROUP_FORBIDDEN_NODE_TYPES,
    _clone_node_to_tree,
    _find_group_node_socket_by_identifier,
    _find_interface_socket_by_identifier,
    _unique_interface_name,
)


class AF_OT_CreateFlowTree(bpy.types.Operator):
    bl_idname = "af.create_flow_tree"
    bl_label = "Create Automation Flow Tree"
    bl_description = "Create a new Automation Flow node tree"

    tree_name: bpy.props.StringProperty(name="Name", default="AutomationFlow")

    def execute(self, context):
        tree = bpy.data.node_groups.new(self.tree_name, "AFNodeTreeType")
        tree.use_fake_user = True
        space = context.space_data
        if space and space.type == "NODE_EDITOR":
            space.node_tree = tree
        return {"FINISHED"}


class AF_OT_AddGroupAssetNode(bpy.types.Operator):
    bl_idname = "af.add_group_asset_node"
    bl_label = "Add Group Asset"
    bl_description = "Add a built-in Automation Flow group asset node"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: bpy.props.StringProperty(name="Asset ID", default="")

    @classmethod
    def poll(cls, context):
        return _get_active_flow_tree(context) is not None

    def invoke(self, context, event):
        _set_node_editor_cursor_from_event(context, event)
        result = self.execute(context)
        if result != {"FINISHED"}:
            return result
        return _invoke_node_translate_attach()

    def execute(self, context):
        tree = _get_active_flow_tree(context)
        if tree is None:
            self.report({"ERROR"}, "Open an Automation Flow node tree first")
            return {"CANCELLED"}

        group_tree = _ensure_group_asset_tree(self.asset_id)
        if group_tree is None:
            self.report({"ERROR"}, "Group asset is unavailable")
            return {"CANCELLED"}

        from ..nodes import _sync_group_node_sockets

        group_node = tree.nodes.new("AFNodeGroup")
        group_node.location = _node_editor_cursor_location(context)
        group_node.group_tree = group_tree
        if str(group_tree.name).strip():
            group_node.name = str(group_tree.name)
        _sync_group_node_sockets(group_node)
        _select_active_node(tree, group_node)
        _tag_flow_node_editor_redraw(tree.name)
        return {"FINISHED"}


class AF_OT_AddPairedFlowNode(bpy.types.Operator):
    bl_idname = "af.add_paired_flow_node"
    bl_label = "Add Paired Flow Node"
    bl_description = "Add a paired Automation Flow node and its counterpart"
    bl_options = {"REGISTER", "UNDO"}

    node_type: bpy.props.StringProperty(name="Node Type", default="")

    @classmethod
    def poll(cls, context):
        return _get_active_flow_tree(context) is not None

    def invoke(self, context, event):
        _set_node_editor_cursor_from_event(context, event)
        result = self.execute(context)
        if result != {"FINISHED"}:
            return result
        return _invoke_node_translate_attach()

    def execute(self, context):
        tree = _get_active_flow_tree(context)
        if tree is None:
            self.report({"ERROR"}, "Open an Automation Flow node tree first")
            return {"CANCELLED"}

        from ..nodes import _PAIR_NODE_SYNC_GUARD, _create_missing_pair_node, _is_pair_managed_node
        from ..node_system.tree import _queue_group_tree_sync, _queue_tree_reroute_sync, resume_runtime_sync, suspend_runtime_sync

        node_type = str(self.node_type or "").strip()
        if not node_type:
            self.report({"ERROR"}, "Node type is missing")
            return {"CANCELLED"}

        tree_key = int(tree.as_pointer()) if hasattr(tree, "as_pointer") else id(tree)
        node = None
        pair_node = None
        _PAIR_NODE_SYNC_GUARD.add(tree_key)
        suspend_runtime_sync()
        try:
            node = tree.nodes.new(node_type)
            if not _is_pair_managed_node(node):
                tree.nodes.remove(node)
                self.report({"ERROR"}, f"Unsupported paired node type '{node_type}'")
                return {"CANCELLED"}

            node.location = _node_editor_cursor_location(context)
            pair_node = _create_missing_pair_node(tree, node)
            if pair_node is None:
                tree.nodes.remove(node)
                self.report({"ERROR"}, "Failed to create paired node counterpart")
                return {"CANCELLED"}
        finally:
            resume_runtime_sync()
            _PAIR_NODE_SYNC_GUARD.discard(tree_key)

        _queue_tree_reroute_sync(tree)
        _queue_group_tree_sync(tree)
        for other in getattr(tree, "nodes", []):
            other.select = False
        node.select = True
        pair_node.select = True
        tree.nodes.active = node
        _tag_flow_node_editor_redraw(tree.name)
        return {"FINISHED"}


class AF_OT_CreateGroupFromSelection(bpy.types.Operator):
    bl_idname = "af.create_group_from_selection"
    bl_label = "Create Group From Selection"
    bl_description = "Create an editable AF group from the selected nodes"
    bl_options = {"REGISTER", "UNDO"}

    group_name: bpy.props.StringProperty(name="Group Name", default="AFGroup")

    @classmethod
    def poll(cls, context):
        tree = _get_active_flow_tree(context)
        if tree is None:
            return False
        selected = [node for node in tree.nodes if node.select]
        return len(selected) > 0

    def invoke(self, context, event):
        del event
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        tree = _get_active_flow_tree(context)
        if tree is None:
            self.report({"ERROR"}, "Open an Automation Flow node tree first")
            return {"CANCELLED"}

        selected_nodes = [node for node in tree.nodes if node.select]
        if not selected_nodes:
            self.report({"ERROR"}, "Select at least one node")
            return {"CANCELLED"}

        invalid = [node.name for node in selected_nodes if getattr(node, "bl_idname", "") in GROUP_FORBIDDEN_NODE_TYPES]
        if invalid:
            self.report({"ERROR"}, f"These nodes cannot be grouped: {', '.join(invalid)}")
            return {"CANCELLED"}

        selected_set = set(selected_nodes)
        internal_links = []
        inbound_links = []
        outbound_links = []
        for link in tree.links:
            from_selected = link.from_node in selected_set
            to_selected = link.to_node in selected_set
            if from_selected and to_selected:
                internal_links.append(link)
            elif not from_selected and to_selected:
                inbound_links.append(link)
            elif from_selected and not to_selected:
                outbound_links.append(link)

        try:
            from ..nodes import _sync_group_node_sockets
            from ..node_system.tree import suspend_runtime_sync, resume_runtime_sync
        except Exception as exc:
            self.report({"ERROR"}, f"Group helpers unavailable: {exc}")
            return {"CANCELLED"}
        from ..node_system.tree import _queue_group_tree_sync, _queue_tree_reroute_sync

        group_tree = None
        group_node = None
        suspend_runtime_sync()
        try:
            group_tree = bpy.data.node_groups.new(self.group_name, "AFNodeTreeType")
            group_tree.use_fake_user = True

            input_names = set()
            output_names = set()
            inbound_interface_map = {}
            outbound_interface_map = {}

            try:
                for link in inbound_links:
                    socket_type = str(getattr(link.to_socket, "bl_idname", "") or "")
                    name = _unique_interface_name(link.to_socket.name, input_names)
                    item = group_tree.interface.new_socket(name, socket_type=socket_type, in_out="INPUT")
                    inbound_interface_map[link] = str(item.identifier)
                for link in outbound_links:
                    source_key = (int(link.from_node.as_pointer()), str(link.from_socket.name), str(getattr(link.from_socket, "bl_idname", "")))
                    if source_key in outbound_interface_map:
                        continue
                    socket_type = str(getattr(link.from_socket, "bl_idname", "") or "")
                    name = _unique_interface_name(link.from_socket.name, output_names)
                    item = group_tree.interface.new_socket(name, socket_type=socket_type, in_out="OUTPUT")
                    outbound_interface_map[source_key] = str(item.identifier)
            except Exception as exc:
                bpy.data.node_groups.remove(group_tree)
                self.report({"ERROR"}, f"Failed to build group interface: {exc}")
                return {"CANCELLED"}

            group_input = group_tree.nodes.new("NodeGroupInput")
            group_output = group_tree.nodes.new("NodeGroupOutput")

            node_map = {}
            min_x = min(node.location.x for node in selected_nodes)
            min_y = min(node.location.y for node in selected_nodes)
            for source_node in selected_nodes:
                node_map[source_node] = _clone_node_to_tree(source_node, group_tree)
                try:
                    source_x = float(getattr(source_node.location, "x", source_node.location[0]))
                    source_y = float(getattr(source_node.location, "y", source_node.location[1]))
                except Exception:
                    source_x = float(min_x)
                    source_y = float(min_y)
                node_map[source_node].location = (
                    source_x - float(min_x) + 120.0,
                    source_y - float(min_y),
                )

            group_input.location = (min(node.location.x for node in node_map.values()) - 320.0, 0.0)
            group_output.location = (max(node.location.x for node in node_map.values()) + 320.0, 0.0)

            for link in internal_links:
                try:
                    from_index = list(link.from_node.outputs).index(link.from_socket)
                    to_index = list(link.to_node.inputs).index(link.to_socket)
                    group_tree.links.new(node_map[link.from_node].outputs[from_index], node_map[link.to_node].inputs[to_index])
                except Exception:
                    continue

            for link in inbound_links:
                identifier = inbound_interface_map.get(link)
                if not identifier:
                    continue
                group_socket = _find_interface_socket_by_identifier(group_input, identifier, "INPUT")
                if group_socket is None:
                    continue
                try:
                    to_index = list(link.to_node.inputs).index(link.to_socket)
                    group_tree.links.new(group_socket, node_map[link.to_node].inputs[to_index])
                except Exception:
                    continue

            for link in outbound_links:
                source_key = (int(link.from_node.as_pointer()), str(link.from_socket.name), str(getattr(link.from_socket, "bl_idname", "")))
                identifier = outbound_interface_map.get(source_key)
                if not identifier:
                    continue
                group_socket = _find_interface_socket_by_identifier(group_output, identifier, "OUTPUT")
                if group_socket is None:
                    continue
                try:
                    from_index = list(link.from_node.outputs).index(link.from_socket)
                    group_tree.links.new(node_map[link.from_node].outputs[from_index], group_socket)
                except Exception:
                    continue

            center_x = sum(node.location.x for node in selected_nodes) / len(selected_nodes)
            center_y = sum(node.location.y for node in selected_nodes) / len(selected_nodes)
            group_node = tree.nodes.new("AFNodeGroup")
            group_node.location = (center_x, center_y)
            group_node.group_tree = group_tree
            _sync_group_node_sockets(group_node)

            # Snapshot reconnection targets before removing selected nodes.
            # Blender frees the original link RNA as soon as participating nodes
            # are removed, so accessing outbound/inbound link objects after that
            # point can crash instead of raising a Python exception.
            inbound_restore_records = []
            for link in inbound_links:
                identifier = inbound_interface_map.get(link)
                from_socket = getattr(link, "from_socket", None)
                if not identifier or from_socket is None:
                    continue
                inbound_restore_records.append(
                    {
                        "identifier": str(identifier),
                        "from_socket": from_socket,
                    }
                )

            outbound_restore_records = []
            for link in outbound_links:
                source_key = (int(link.from_node.as_pointer()), str(link.from_socket.name), str(getattr(link.from_socket, "bl_idname", "")))
                identifier = outbound_interface_map.get(source_key)
                to_socket = getattr(link, "to_socket", None)
                if not identifier or to_socket is None:
                    continue
                outbound_restore_records.append(
                    {
                        "identifier": str(identifier),
                        "to_socket": to_socket,
                    }
                )

            for node in selected_nodes:
                tree.nodes.remove(node)

            for record in inbound_restore_records:
                identifier = str(record.get("identifier", "") or "")
                from_socket = record.get("from_socket")
                socket = _find_group_node_socket_by_identifier(group_node, identifier, "INPUT")
                if socket is None or from_socket is None:
                    continue
                try:
                    tree.links.new(from_socket, socket)
                except Exception:
                    continue

            for record in outbound_restore_records:
                identifier = str(record.get("identifier", "") or "")
                to_socket = record.get("to_socket")
                socket = _find_group_node_socket_by_identifier(group_node, identifier, "OUTPUT")
                if socket is None or to_socket is None:
                    continue
                try:
                    tree.links.new(socket, to_socket)
                except Exception:
                    continue

            for node in tree.nodes:
                node.select = False
            group_node.select = True
            tree.nodes.active = group_node
        finally:
            resume_runtime_sync()

        if group_tree is not None:
            _queue_tree_reroute_sync(group_tree)
            _queue_group_tree_sync(group_tree)
        _queue_tree_reroute_sync(tree)
        _queue_group_tree_sync(tree)
        _tag_flow_node_editor_redraw(tree.name)
        return {"FINISHED"}


NODE_ADD_OPERATOR_CLASSES = (
    AF_OT_CreateFlowTree,
    AF_OT_AddGroupAssetNode,
    AF_OT_AddPairedFlowNode,
    AF_OT_CreateGroupFromSelection,
)
