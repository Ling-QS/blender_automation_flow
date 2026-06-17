import bpy


def build_object_node_classes(
    *,
    AFBaseNode,
    COLLECTION_LINK_MODE_ITEMS,
    CREATE_OBJECT_TYPE_ITEMS,
    DUPLICATE_DATA_MODE_ITEMS,
    LIGHT_TYPE_ITEMS,
    MISSING_POLICY_ITEMS,
    OBJECT_TYPE_FILTER_ITEMS,
    SORT_MODE_ITEMS,
    _hide_default_auxiliary_outputs,
    _set_default_node_width,
    _set_node_color,
):
    class AFNodeCollectionList(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCollectionList"
        bl_label = "Collection List"
        bl_icon = "BLANK1"

        target_collection: bpy.props.PointerProperty(type=bpy.types.Collection)

        def init(self, context):
            self.inputs.new("AFSocketCollectionList", "Add Collections")
            self.inputs.new("AFSocketCollectionList", "Remove Collections")
            self.outputs.new("AFSocketCollectionList", "Collection List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            layout.prop(self, "target_collection", text="")

    class AFNodeCollectionExpand(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCollectionExpand"
        bl_label = "Collection Expand"
        bl_icon = "BLANK1"

        target_collection: bpy.props.PointerProperty(type=bpy.types.Collection)
        recursive_collections: bpy.props.BoolProperty(name="Recursive", default=True)
        include_hidden_objects: bpy.props.BoolProperty(name="Include Hidden", default=True)
        object_type_filter: bpy.props.EnumProperty(name="Object Type", items=OBJECT_TYPE_FILTER_ITEMS, default="ALL")
        sort_mode: bpy.props.EnumProperty(name="Sort Mode", items=SORT_MODE_ITEMS, default="NAME_ASC")

        def init(self, context):
            self.inputs.new("AFSocketCollectionList", "Collection List")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "target_collection", text="")
            layout.prop(self, "recursive_collections")
            layout.prop(self, "include_hidden_objects")
            layout.prop(self, "object_type_filter", text="")
            layout.prop(self, "sort_mode", text="")

    class AFNodeObjectList(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeObjectList"
        bl_label = "Object List"
        bl_icon = "BLANK1"

        sort_mode: bpy.props.EnumProperty(name="Sort Mode", items=SORT_MODE_ITEMS, default="NAME_ASC")

        def init(self, context):
            self.inputs.new("AFSocketObjectList", "Base Objects")
            self.inputs.new("AFSocketObjectList", "Add Objects")
            self.inputs.new("AFSocketObjectList", "Remove Objects")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "sort_mode", text="")

    class AFNodeSceneObjectList(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeSceneObjectList"
        bl_label = "Scene Object List"
        bl_icon = "BLANK1"

        target_scene: bpy.props.PointerProperty(type=bpy.types.Scene)
        recursive_collections: bpy.props.BoolProperty(name="Recursive", default=True)
        include_hidden_objects: bpy.props.BoolProperty(name="Include Hidden", default=True)
        object_type_filter: bpy.props.EnumProperty(name="Object Type", items=OBJECT_TYPE_FILTER_ITEMS, default="ALL")
        sort_mode: bpy.props.EnumProperty(name="Sort Mode", items=SORT_MODE_ITEMS, default="NAME_ASC")

        def init(self, context):
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            layout.prop(self, "target_scene", text="")
            layout.prop(self, "recursive_collections")
            layout.prop(self, "include_hidden_objects")
            layout.prop(self, "object_type_filter", text="")
            layout.prop(self, "sort_mode", text="")

    class AFNodeObjectInfo(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeObjectInfo"
        bl_label = "Object Info"
        bl_icon = "BLANK1"

        target_object: bpy.props.PointerProperty(type=bpy.types.Object)

        def init(self, context):
            del context
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("NodeSocketVector", "Location")
            self.outputs.new("NodeSocketRotation", "Rotation")
            self.outputs.new("NodeSocketVector", "Scale")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "INPUT")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_object", text="")

    class AFNodeCreateCollection(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCreateCollection"
        bl_label = "Create Collection"
        bl_icon = "BLANK1"

        collection_name: bpy.props.StringProperty(name="Collection Name", default="Collection")
        reuse_existing: bpy.props.BoolProperty(name="Reuse Existing", default=True)
        parent_collection: bpy.props.PointerProperty(type=bpy.types.Collection)

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketCollectionList", "Parent Collections")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketCollectionList", "Collection List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "collection_name", text="")
            layout.prop(self, "reuse_existing")
            layout.prop(self, "parent_collection", text="")

    class AFNodeAddToCollection(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeAddToCollection"
        bl_label = "Add To Collection"
        bl_icon = "BLANK1"

        target_collection: bpy.props.PointerProperty(type=bpy.types.Collection)
        link_mode: bpy.props.EnumProperty(name="Mode", items=COLLECTION_LINK_MODE_ITEMS, default="LINK_ONLY")
        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketCollectionList", "Collection List")
            count_socket = self.inputs.new("NodeSocketInt", "Count")
            if hasattr(count_socket, "default_value"):
                count_socket.default_value = 1
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "target_collection", text="")
            layout.prop(self, "link_mode", expand=True)
            layout.prop(self, "missing_policy", text="")

    class AFNodeCreateObject(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCreateObject"
        bl_label = "Create Object"
        bl_icon = "BLANK1"

        object_name: bpy.props.StringProperty(name="Object Name", default="Object")
        object_type: bpy.props.EnumProperty(name="Object Type", items=CREATE_OBJECT_TYPE_ITEMS, default="EMPTY")
        light_type: bpy.props.EnumProperty(name="Light Type", items=LIGHT_TYPE_ITEMS, default="POINT")
        target_collection: bpy.props.PointerProperty(type=bpy.types.Collection)

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketCollectionList", "Collection List")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "object_name", text="")
            layout.prop(self, "object_type", text="")
            if str(getattr(self, "object_type", "EMPTY") or "EMPTY") == "LIGHT":
                layout.prop(self, "light_type", text="")
            layout.prop(self, "target_collection", text="")

    class AFNodeDuplicateObject(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeDuplicateObject"
        bl_label = "Duplicate Object"
        bl_icon = "BLANK1"

        target_collection: bpy.props.PointerProperty(type=bpy.types.Collection)
        data_mode: bpy.props.EnumProperty(name="Data Mode", items=DUPLICATE_DATA_MODE_ITEMS, default="LINKED_DATA")
        name_suffix: bpy.props.StringProperty(name="Name Suffix", default="_Copy")
        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketCollectionList", "Collection List")
            count_socket = self.inputs.new("NodeSocketInt", "Count")
            if hasattr(count_socket, "default_value"):
                count_socket.default_value = 1
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "data_mode", text="")
            layout.prop(self, "name_suffix", text="")
            layout.prop(self, "target_collection", text="")
            layout.prop(self, "missing_policy", text="")

    class AFNodeDeleteObject(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeDeleteObject"
        bl_label = "Delete Object"
        bl_icon = "BLANK1"

        delete_data_if_orphaned: bpy.props.BoolProperty(name="Delete Data If Orphaned", default=False)
        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_default_node_width(self, multiplier=(4.0 / 3.0))

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "delete_data_if_orphaned")
            layout.prop(self, "missing_policy", text="")

    return {
        "AFNodeCollectionList": AFNodeCollectionList,
        "AFNodeCollectionExpand": AFNodeCollectionExpand,
        "AFNodeObjectList": AFNodeObjectList,
        "AFNodeSceneObjectList": AFNodeSceneObjectList,
        "AFNodeObjectInfo": AFNodeObjectInfo,
        "AFNodeCreateCollection": AFNodeCreateCollection,
        "AFNodeAddToCollection": AFNodeAddToCollection,
        "AFNodeCreateObject": AFNodeCreateObject,
        "AFNodeDuplicateObject": AFNodeDuplicateObject,
        "AFNodeDeleteObject": AFNodeDeleteObject,
    }
