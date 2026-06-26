import uuid
from contextlib import contextmanager

import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..node_system.socket_aliases import (
    ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    ADD_PROPERTY_PACKAGE_SOCKET_NAME,
    BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME,
    BASE_PROPERTY_PACKAGE_SOCKET_NAME,
    PROPERTY_ASSIGNMENT_SOCKET_NAME,
    PROPERTY_DEFINITION_SOCKET_NAME,
    PROPERTY_PACKAGE_SOCKET_NAME,
)

_READ_PROPERTY_PACKAGE_TARGET_SYNC_GUARD = set()
_READ_PROPERTY_PACKAGE_TARGET_ENUM_CACHE = {}


def _zh_ui():
    try:
        language = str(getattr(getattr(bpy.context, "preferences", None), "view", None).language or "")
    except Exception:
        language = ""
    return language.startswith("zh")


def build_property_package_node_classes(
    *,
    AFBaseNode,
    APPLY_OBJECT_PROPERTIES_MODE_ITEMS,
    MISSING_POLICY_ITEMS,
    PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
    PROPERTY_PACKAGE_FILTER_MODE_ITEMS,
    REFRESH_PROPERTY_PACKAGE_RANGE_MODE_ITEMS,
    PROPERTY_PACKAGE_STORE_MODE_ITEMS,
    SORT_MODE_ITEMS,
    _has_stored_property_package,
    _hide_default_auxiliary_outputs,
    _normalized_preview_context,
    _set_node_color,
    _sync_apply_object_properties_sockets,
    _sync_create_property_package_sockets,
    _ui_runner_for_node,
):
    def _node_sync_guard_key(node):
        try:
            return int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node)
        except Exception:
            return id(node)

    @contextmanager
    def _guard_read_property_package_target_sync(node):
        guard_key = _node_sync_guard_key(node)
        _READ_PROPERTY_PACKAGE_TARGET_SYNC_GUARD.add(guard_key)
        try:
            yield
        finally:
            _READ_PROPERTY_PACKAGE_TARGET_SYNC_GUARD.discard(guard_key)

    def _read_property_package_target_sync_guarded(node):
        return _node_sync_guard_key(node) in _READ_PROPERTY_PACKAGE_TARGET_SYNC_GUARD

    def _refresh_property_package_dependents(
        node_or_tree,
        *,
        invalidate_active_runner=True,
        sync_dynamic_nodes=False,
    ):
        if getattr(node_or_tree, "bl_idname", "") == "AFNodeTreeType":
            node_tree = node_or_tree
        else:
            node_tree = getattr(node_or_tree, "id_data", None)
        try:
            if bool(sync_dynamic_nodes):
                from ..node_system.tree import _refresh_dynamic_node_dependents as _refresh_property_package_tree
            else:
                from ..node_system.tree import _refresh_runtime_data_dependents as _refresh_property_package_tree
        except Exception:
            return
        try:
            _refresh_property_package_tree(
                node_tree,
                invalidate_active_runner=bool(invalidate_active_runner),
            )
        except Exception:
            pass

    def _ensure_store_asset_id(node):
        if node is None or str(getattr(node, "bl_idname", "") or "") != "AFNodeStorePropertyPackage":
            return ""
        asset_id = str(getattr(node, "store_asset_id", "") or "").strip()
        if asset_id:
            return asset_id
        try:
            node.store_asset_id = uuid.uuid4().hex
        except Exception:
            return ""
        return str(getattr(node, "store_asset_id", "") or "").strip()

    def _iter_store_nodes_in_tree(node):
        node_tree = getattr(node, "id_data", None)
        if node_tree is None:
            return []
        return [
            candidate
            for candidate in getattr(node_tree, "nodes", [])
            if str(getattr(candidate, "bl_idname", "") or "") == "AFNodeStorePropertyPackage"
        ]

    def _find_store_node_by_asset_id(node, target_store_id):
        target_store_id = str(target_store_id or "").strip()
        if not target_store_id:
            return None
        for candidate in _iter_store_nodes_in_tree(node):
            if _ensure_store_asset_id(candidate) == target_store_id:
                return candidate
        return None

    def _store_slot_label(node):
        slot_name = str(getattr(node, "store_slot_name", "") or "").strip()
        if slot_name:
            return slot_name
        return iface_("Unnamed Slot")

    def _store_selector_item_label(node):
        return f"{_store_slot_label(node)} [{str(getattr(node, 'name', '') or '')}]"

    def _read_property_package_target_items(node):
        items = [
            ("0", iface_("Select Store"), "", 0),
            ("", iface_("Select Store"), "", 1),
        ]
        store_nodes = list(_iter_store_nodes_in_tree(node))
        for index, candidate in enumerate(store_nodes, start=2):
            asset_id = _ensure_store_asset_id(candidate)
            if not asset_id:
                continue
            items.append(
                (
                    asset_id,
                    _store_selector_item_label(candidate),
                    str(getattr(candidate, "name", "") or ""),
                    index,
                )
            )
        target_store_id = str(getattr(node, "target_store_id", "") or "").strip()
        if target_store_id and not any(str(item[0]) == target_store_id for item in items):
            target_store_name = str(getattr(node, "target_store_node_name", "") or "").strip()
            invalid_label = iface_("Invalid Target")
            if target_store_name:
                invalid_label = f"{invalid_label} [{target_store_name}]"
            items.append(
                (
                    target_store_id,
                    invalid_label,
                    iface_("Target Store Property Package is missing"),
                    max(1, len(items)),
                )
            )
        _READ_PROPERTY_PACKAGE_TARGET_ENUM_CACHE[_node_sync_guard_key(node)] = items
        return _READ_PROPERTY_PACKAGE_TARGET_ENUM_CACHE[_node_sync_guard_key(node)]

    def _sync_read_property_package_target(node, *, refresh_dependents=False):
        if node is None or str(getattr(node, "bl_idname", "") or "") != "AFNodeReadPropertyPackage":
            return None
        target_store_id = str(getattr(node, "target_store_id", "") or "").strip()
        if target_store_id == "0":
            target_store_id = ""
        target_store_name = str(getattr(node, "target_store_node_name", "") or "").strip()
        target_store_selector = str(getattr(node, "target_store_selector", "") or "").strip()
        if target_store_selector == "0":
            target_store_selector = ""
        matched_node = _find_store_node_by_asset_id(node, target_store_id)
        if matched_node is None and target_store_name:
            candidate = getattr(getattr(node, "id_data", None), "nodes", {}).get(target_store_name)
            if candidate is not None and str(getattr(candidate, "bl_idname", "") or "") == "AFNodeStorePropertyPackage":
                matched_node = candidate
        if matched_node is None:
            if target_store_id and target_store_selector != target_store_id:
                try:
                    with _guard_read_property_package_target_sync(node):
                        node.target_store_selector = target_store_id
                except Exception:
                    pass
            return None
        resolved_store_id = _ensure_store_asset_id(matched_node)
        changed = False
        desired_name = str(getattr(matched_node, "name", "") or "")
        desired_selector = resolved_store_id or target_store_selector
        updates = {}
        if str(getattr(node, "target_store_node_name", "") or "") != desired_name:
            updates["target_store_node_name"] = desired_name
        if resolved_store_id and str(getattr(node, "target_store_id", "") or "") != resolved_store_id:
            updates["target_store_id"] = resolved_store_id
        if desired_selector and str(getattr(node, "target_store_selector", "") or "") != desired_selector:
            updates["target_store_selector"] = desired_selector
        if updates:
            changed = True
            try:
                with _guard_read_property_package_target_sync(node):
                    for attr_name, attr_value in updates.items():
                        setattr(node, attr_name, attr_value)
            except Exception:
                pass
        if changed and bool(refresh_dependents):
            _refresh_property_package_dependents(node)
        return matched_node

    def _store_slot_name_updated(node, context):
        del context
        _refresh_property_package_dependents(node, invalidate_active_runner=False)

    def _read_property_package_target_name_updated(node, context):
        del context
        if _read_property_package_target_sync_guarded(node):
            return
        _sync_read_property_package_target(node)
        _refresh_property_package_dependents(node)

    def _read_property_package_target_selector_items(node, context):
        del context
        return _read_property_package_target_items(node)

    def _read_property_package_target_selector_updated(node, context):
        del context
        if _read_property_package_target_sync_guarded(node):
            return
        selected_store_id = str(getattr(node, "target_store_selector", "") or "").strip()
        matched_node = _find_store_node_by_asset_id(node, selected_store_id)
        target_store_name = str(getattr(node, "target_store_node_name", "") or "").strip()
        with _guard_read_property_package_target_sync(node):
            try:
                node.target_store_id = selected_store_id
            except Exception:
                pass
            try:
                node.target_store_node_name = str(getattr(matched_node, "name", "") or "") if matched_node is not None else ("" if not selected_store_id else target_store_name)
            except Exception:
                pass
        _sync_read_property_package_target(node)
        _refresh_property_package_dependents(node)

    @contextmanager
    def _runtime_sync_suspended_during_node_init():
        suspend_runtime_sync = None
        resume_runtime_sync = None
        try:
            from ..node_system.tree import resume_runtime_sync, suspend_runtime_sync
        except Exception:
            suspend_runtime_sync = None
            resume_runtime_sync = None
        if suspend_runtime_sync is not None:
            suspend_runtime_sync()
        try:
            yield
        finally:
            if resume_runtime_sync is not None:
                resume_runtime_sync()

    class AFNodeParsePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeParsePropertyPackage"
        bl_label = "Parse Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Parse Prop Pack")

        sort_mode: bpy.props.EnumProperty(name="Sort Mode", items=SORT_MODE_ITEMS, default="NAME_ASC")

        def init(self, context):
            with _runtime_sync_suspended_during_node_init():
                self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
                self.outputs.new("AFSocketObjectList", "Object List")
                self.outputs.new("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME)
                self.outputs.new("AFSocketReport", "Report")
                _hide_default_auxiliary_outputs(self)
                _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "sort_mode", text="")

    class AFNodeMergePropertyAssignments(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMergePropertyAssignments"
        bl_label = "Merge Property Assignments"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Merge Prop Assigns")

        conflict_policy: bpy.props.EnumProperty(
            name="Conflict Policy",
            items=PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
            default="LAST_WINS",
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketPropertyAssignment", BASE_PROPERTY_ASSIGNMENT_SOCKET_NAME)
            self.inputs.new("AFSocketPropertyAssignment", ADD_PROPERTY_ASSIGNMENT_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyAssignment", PROPERTY_ASSIGNMENT_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "conflict_policy", text="")

    class AFNodeFilterPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeFilterPropertyPackage"
        bl_label = "Filter Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Filter Prop Pack")

        filter_mode: bpy.props.EnumProperty(
            name="Filter Mode",
            items=PROPERTY_PACKAGE_FILTER_MODE_ITEMS,
            default="KEEP_MATCHED",
        )

        def init(self, context):
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "filter_mode", text="")

    class AFNodeMergePropertyPackages(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeMergePropertyPackages"
        bl_label = "Merge Property Packages"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Merge Prop Packs")

        conflict_policy: bpy.props.EnumProperty(
            name="Conflict Policy",
            items=PROPERTY_PACKAGE_CONFLICT_POLICY_ITEMS,
            default="LAST_WINS",
        )

        def init(self, context):
            self.inputs.new("AFSocketPropertyPackage", BASE_PROPERTY_PACKAGE_SOCKET_NAME)
            self.inputs.new("AFSocketPropertyPackage", ADD_PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            layout.prop(self, "conflict_policy", text="")

    class AFNodeCreatePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeCreatePropertyPackage"
        bl_label = "Create Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Create Prop Pack")

        def init(self, context):
            del context
            self.inputs.new("AFSocketObjectList", "Object List")
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            self._sync_sockets()
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context

        def _sync_sockets(self):
            _sync_create_property_package_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeRefreshPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRefreshPropertyPackage"
        bl_label = "Refresh Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Refresh Prop Pack")

        range_mode: bpy.props.EnumProperty(
            name="Range",
            items=REFRESH_PROPERTY_PACKAGE_RANGE_MODE_ITEMS,
            default="IN_SCOPE",
        )
        refresh_values: bpy.props.BoolProperty(name="Refresh Values", default=True)
        prune_items: bpy.props.BoolProperty(name="Prune Items", default=False)

        def init(self, context):
            del context
            with _runtime_sync_suspended_during_node_init():
                self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
                self.inputs.new("AFSocketObjectList", "Object List")
                self.inputs.new("AFSocketPropertyDefinition", PROPERTY_DEFINITION_SOCKET_NAME)
                self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
                self.outputs.new("AFSocketReport", "Report")
                _hide_default_auxiliary_outputs(self)
                _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "range_mode", text="")
            row = layout.row(align=True)
            row.prop(self, "refresh_values", toggle=True)
            row.prop(self, "prune_items", toggle=True)

    class AFNodeStorePropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeStorePropertyPackage"
        bl_label = "Store Property Package"
        bl_icon = "BLANK1"

        store_asset_id: bpy.props.StringProperty(name="Store Asset ID", default="", options={"HIDDEN"})
        store_slot_name: bpy.props.StringProperty(
            name="Slot Name",
            default="",
            update=_store_slot_name_updated,
        )

        def draw_label(self):
            return iface_("Store Prop Pack")

        store_mode: bpy.props.EnumProperty(
            name="Mode",
            items=PROPERTY_PACKAGE_STORE_MODE_ITEMS,
            default="STORE_AND_OUTPUT",
        )

        def init(self, context):
            del context
            _ensure_store_asset_id(self)
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            _ensure_store_asset_id(self)
            layout.prop(self, "store_slot_name", text="", placeholder="\u69fd\u540d")
            owner = None
            has_stored_package = False
            try:
                preview_context = _normalized_preview_context(context)
                runner = _ui_runner_for_node(self, preview_context)
                owner = runner._stored_property_package_owner(self) if runner is not None else None
            except Exception:
                owner = None
            try:
                has_stored_package = bool(_has_stored_property_package(self, owner=owner))
            except Exception:
                has_stored_package = bool(_has_stored_property_package(self))
            row = layout.row(align=True)
            row.prop(self, "store_mode", expand=True)
            clear_row = row.row(align=True)
            clear_row.enabled = has_stored_package
            clear_op = clear_row.operator("af.clear_stored_property_package", text="", icon="TRASH")
            if clear_op is not None:
                clear_op.node_tree_name = getattr(getattr(self, "id_data", None), "name", "")
                clear_op.node_name = self.name

        def copy(self, node):
            del node
            self.store_asset_id = uuid.uuid4().hex

    class AFNodeReadPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeReadPropertyPackage"
        bl_label = "Read Property Package"
        bl_icon = "BLANK1"

        target_store_node_name: bpy.props.StringProperty(
            name="Store",
            default="",
            options={"HIDDEN"},
            update=_read_property_package_target_name_updated,
        )
        target_store_id: bpy.props.StringProperty(name="Target Store ID", default="", options={"HIDDEN"})
        target_store_selector: bpy.props.EnumProperty(
            name="Store",
            items=_read_property_package_target_selector_items,
            update=_read_property_package_target_selector_updated,
        )

        def draw_label(self):
            return iface_("Read Prop Pack")

        def init(self, context):
            del context
            self.outputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)
            _set_node_color(self, "GEOMETRY")

        def draw_buttons(self, context, layout):
            del context
            self._sync_target_store_binding()
            layout.prop(self, "target_store_selector", text="")

        def _sync_target_store_binding(self):
            _sync_read_property_package_target(self)

        def update(self):
            self._sync_target_store_binding()

    class AFNodeApplyObjectProperties(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeApplyObjectProperties"
        bl_label = "Apply Object Properties"
        bl_icon = "BLANK1"

        def draw_label(self):
            if _zh_ui():
                return iface_("Apply Object Properties")
            return iface_("Apply Properties")

        apply_mode: bpy.props.EnumProperty(
            name="Mode",
            items=APPLY_OBJECT_PROPERTIES_MODE_ITEMS,
            default="PACKAGE",
            update=lambda self, context: self._sync_sockets(),
        )

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketObjectList", "Object List")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            self._sync_sockets()
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "apply_mode", expand=True)

        def _sync_sockets(self):
            _sync_apply_object_properties_sockets(self)

        def update(self):
            self._sync_sockets()

    class AFNodeApplyPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeApplyPropertyPackage"
        bl_label = "Apply Property Package"
        bl_icon = "BLANK1"

        def draw_label(self):
            return iface_("Apply Prop Pack")

        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "missing_policy", text="")

    class AFNodeRecordPropertyPackage(AFBaseNode, bpy.types.Node):
        bl_idname = "AFNodeRecordPropertyPackage"
        bl_label = "Record Property Package"
        bl_icon = "BLANK1"

        record_asset_id: bpy.props.StringProperty(name="Record Asset ID", default="", options={"HIDDEN"})

        def draw_label(self):
            return iface_("Record Prop Pack")

        missing_policy: bpy.props.EnumProperty(name="Missing Policy", items=MISSING_POLICY_ITEMS, default="WARN_AND_SKIP")

        def init(self, context):
            del context
            if not str(getattr(self, "record_asset_id", "") or "").strip():
                self.record_asset_id = uuid.uuid4().hex
            self.inputs.new("AFSocketFlow", "Flow In")
            self.inputs.new("AFSocketPropertyPackage", PROPERTY_PACKAGE_SOCKET_NAME)
            self.outputs.new("AFSocketFlow", "Flow Out")
            self.outputs.new("AFSocketTaskRef", "Task Ref")
            self.outputs.new("AFSocketReport", "Report")
            _hide_default_auxiliary_outputs(self)

        def draw_buttons(self, context, layout):
            del context
            layout.prop(self, "missing_policy", text="")

        def copy(self, node):
            del node
            self.record_asset_id = uuid.uuid4().hex

    return {
        "AFNodeParsePropertyPackage": AFNodeParsePropertyPackage,
        "AFNodeMergePropertyAssignments": AFNodeMergePropertyAssignments,
        "AFNodeFilterPropertyPackage": AFNodeFilterPropertyPackage,
        "AFNodeMergePropertyPackages": AFNodeMergePropertyPackages,
        "AFNodeCreatePropertyPackage": AFNodeCreatePropertyPackage,
        "AFNodeRefreshPropertyPackage": AFNodeRefreshPropertyPackage,
        "AFNodeStorePropertyPackage": AFNodeStorePropertyPackage,
        "AFNodeReadPropertyPackage": AFNodeReadPropertyPackage,
        "AFNodeApplyObjectProperties": AFNodeApplyObjectProperties,
        "AFNodeApplyPropertyPackage": AFNodeApplyPropertyPackage,
        "AFNodeRecordPropertyPackage": AFNodeRecordPropertyPackage,
    }
