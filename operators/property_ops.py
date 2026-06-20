import copy
import json

import bpy
from bpy.app.translations import pgettext_iface as iface_

from ..node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME
from ..runtime_runner.core import FlowRunner
from ..runtime_core.constants import FlowExecutionError, PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_SCOPE_MODIFIER
from ..runtime_property.api import (
    _iter_property_package_entries,
    _property_package_item_count,
    _validate_property_package,
)
from ..runtime_state.cache import _clear_stored_property_package
from .editor_utils import _get_active_flow_tree, _tag_flow_node_editor_redraw
from .flow_run import (
    _capture_runtime_ui_context,
    _get_active_runner,
    _resume_auto_follow_notifications,
    _suspend_auto_follow_notifications,
)


_QUICK_RUN_NODE_TYPES = {
    "AFNodeStorePropertyPackage",
    "AFNodeApplyObjectProperties",
    "AFNodeApplyPropertyPackage",
    "AFNodeRecordPropertyPackage",
}


def _decode_group_path_json(raw_value):
    raw_value = str(raw_value or "").strip()
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    group_path = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        group_path.append(
            {
                "tree_name": str(item.get("tree_name", "") or ""),
                "node_name": str(item.get("node_name", "") or ""),
            }
        )
    return group_path


def _resolve_quick_run_node(node_tree_name, node_name):
    node_tree = bpy.data.node_groups.get(str(node_tree_name or "").strip())
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None, None
    node = node_tree.nodes.get(str(node_name or "").strip())
    if node is None or getattr(node, "bl_idname", "") not in _QUICK_RUN_NODE_TYPES:
        return node_tree, None
    return node_tree, node


def _build_quick_run_runner(node_tree, scene, context, root_tree_name="", group_path_json=""):
    if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
        return None
    root_tree = bpy.data.node_groups.get(str(root_tree_name or "").strip())
    if root_tree is None or getattr(root_tree, "bl_idname", "") != "AFNodeTreeType":
        root_tree = node_tree
    runner = FlowRunner(root_tree, scene, ui_context=_capture_runtime_ui_context(context)) if scene is not None else None
    if runner is not None:
        runner.current_group_path = _decode_group_path_json(group_path_json)
    return runner


def _quick_run_store_property_package(runner, node):
    property_package = runner._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
    if property_package is None:
        raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
    _validate_property_package(property_package, node.name)
    runner._write_stored_property_package(node, property_package)
    if any(
        str(entry.get("package_role", "") or "") == PROPERTY_PACKAGE_ROLE_SNAPSHOT
        and str(entry.get("scope_kind", "") or "") == PROPERTY_PACKAGE_SCOPE_MODIFIER
        for entry in _iter_property_package_entries(property_package, node.name)
    ):
        runner.last_snapshot_package = copy.deepcopy(property_package)
    runner._set_output(node, "property_package", copy.deepcopy(property_package))
    report = {
        "package_role": str(property_package.get("package_role", "") or ""),
        "scope_kind": str(property_package.get("scope_kind", "") or ""),
        "count": _property_package_item_count(property_package),
        "mode": "MANUAL_STORE",
        "dry_run": False,
    }
    runner._set_output(node, "report", report)
    return report, "Stored Property Package"


def _quick_run_apply_property_package(runner, node):
    runner._execute_node(node)
    report = dict(runner._get_output(node, "report") or {})
    return report, "Applied Property Package"


def _quick_run_apply_object_properties(runner, node):
    runner._execute_node(node)
    report = dict(runner._get_output(node, "report") or {})
    return report, "Applied Object Properties"


def _quick_run_record_property_package(runner, node):
    task_ref = runner._build_record_property_package_task_ref(node)
    shared_action = runner._ensure_property_package_bake_action(task_ref, clear_existing=False)
    runner.property_package_bake_context = {
        "task_ref": copy.deepcopy(task_ref),
        "frame": int(getattr(runner.scene, "frame_current", 1)),
        "owner_node_name": str(getattr(node, "name", "") or ""),
        "shared_action": shared_action,
        "target_record_tree_name": str(task_ref.get("record_tree_name", "") or ""),
        "target_record_node_name": str(task_ref.get("record_node_name", "") or ""),
        "target_record_group_path": copy.deepcopy(list(task_ref.get("record_group_path", []) or [])),
        "touched_object_items": {},
        "touched_component_paths": set(),
    }
    try:
        runner._execute_node(node)
    finally:
        runner.property_package_bake_context = None
    runner._set_output(node, "task_ref", copy.deepcopy(task_ref))
    report = dict(runner._get_output(node, "report") or {})
    return report, "Recorded Property Package"


def _execute_quick_run_node(node_tree, node, scene, context, *, root_tree_name="", group_path_json=""):
    runner = _build_quick_run_runner(node_tree, scene, context, root_tree_name=root_tree_name, group_path_json=group_path_json)
    if runner is None:
        raise FlowExecutionError("AF_E001", "Scene is not available", getattr(node, "name", ""))
    if getattr(node, "bl_idname", "") == "AFNodeStorePropertyPackage":
        report, message = _quick_run_store_property_package(runner, node)
    elif getattr(node, "bl_idname", "") == "AFNodeApplyPropertyPackage":
        report, message = _quick_run_apply_property_package(runner, node)
    elif getattr(node, "bl_idname", "") == "AFNodeApplyObjectProperties":
        report, message = _quick_run_apply_object_properties(runner, node)
    elif getattr(node, "bl_idname", "") == "AFNodeRecordPropertyPackage":
        report, message = _quick_run_record_property_package(runner, node)
    else:
        raise FlowExecutionError("AF_E009", f"Unsupported quick-run node type: {getattr(node, 'bl_idname', '')}", getattr(node, "name", ""))
    runner._flush_status_report_cache()
    return report, message


def _active_quick_run_editor_context(context, node_tree):
    active_tree = _get_active_flow_tree(context)
    if active_tree is None or active_tree != node_tree:
        return "", ""
    from ..ui.overlay_context import _node_editor_group_path, _node_editor_root_tree

    root_tree = _node_editor_root_tree(context, node_tree)
    group_path = _node_editor_group_path(context)
    return str(getattr(root_tree, "name", "") or ""), json.dumps(list(group_path or []), ensure_ascii=True)


def _run_quick_node_action_with_reporting(
    operator,
    context,
    node_tree,
    node,
    *,
    root_tree_name="",
    group_path_json="",
):
    if _get_active_runner() is not None:
        operator.report({"WARNING"}, iface_("A flow is already running"))
        return {"CANCELLED"}

    effective_root_tree_name = str(root_tree_name or "").strip()
    effective_group_path_json = str(group_path_json or "").strip()
    default_root_tree_name, default_group_path_json = _active_quick_run_editor_context(context, node_tree)
    if not effective_root_tree_name:
        effective_root_tree_name = default_root_tree_name
    if not effective_group_path_json:
        effective_group_path_json = default_group_path_json

    scene = getattr(context, "scene", None) or bpy.context.scene

    _suspend_auto_follow_notifications()
    try:
        _report, message = _execute_quick_run_node(
            node_tree,
            node,
            scene,
            context,
            root_tree_name=effective_root_tree_name,
            group_path_json=effective_group_path_json,
        )
    except FlowExecutionError as exc:
        operator.report({"ERROR"}, str(exc.message or exc))
        return {"CANCELLED"}
    except Exception as exc:
        operator.report({"ERROR"}, f"{iface_('Quick node action failed')}: {exc}")
        return {"CANCELLED"}
    finally:
        _resume_auto_follow_notifications()

    _tag_flow_node_editor_redraw(None)
    operator.report({"INFO"}, iface_(message))
    return {"FINISHED"}


class AF_OT_RunStorePropertyPackageNode(bpy.types.Operator):
    bl_idname = "af.run_store_property_package_node"
    bl_label = "Store Property Package Now"
    bl_description = "Store the linked Property Package immediately without running the full flow"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree, node = _resolve_quick_run_node(self.node_tree_name, self.node_name)
        if node_tree is None:
            self.report({"ERROR"}, iface_("Automation Flow node tree not found"))
            return {"CANCELLED"}
        if node is None:
            self.report({"ERROR"}, iface_("Store Prop Pack node not found"))
            return {"CANCELLED"}
        if getattr(node, "bl_idname", "") != "AFNodeStorePropertyPackage":
            self.report({"ERROR"}, iface_("Store Prop Pack node not found"))
            return {"CANCELLED"}
        return _run_quick_node_action_with_reporting(self, context, node_tree, node)


class AF_OT_RunApplyPropertyPackageNode(bpy.types.Operator):
    bl_idname = "af.run_apply_property_package_node"
    bl_label = "Apply Property Package Now"
    bl_description = "Apply this Property Package immediately without running the full flow"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree, node = _resolve_quick_run_node(self.node_tree_name, self.node_name)
        if node_tree is None:
            self.report({"ERROR"}, iface_("Automation Flow node tree not found"))
            return {"CANCELLED"}
        if node is None:
            self.report({"ERROR"}, iface_("Apply Prop Pack node not found"))
            return {"CANCELLED"}
        if getattr(node, "bl_idname", "") != "AFNodeApplyPropertyPackage":
            self.report({"ERROR"}, iface_("Apply Prop Pack node not found"))
            return {"CANCELLED"}
        return _run_quick_node_action_with_reporting(self, context, node_tree, node)


class AF_OT_RunQuickNodeAction(bpy.types.Operator):
    bl_idname = "af.run_quick_node_action"
    bl_label = "Run Quick Node Action"
    bl_description = "Run the quick action for this property node immediately"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")
    root_tree_name: bpy.props.StringProperty(name="Root Tree Name", default="")
    group_path_json: bpy.props.StringProperty(name="Group Path", default="")

    def execute(self, context):
        node_tree, node = _resolve_quick_run_node(self.node_tree_name, self.node_name)
        if node_tree is None:
            self.report({"ERROR"}, iface_("Automation Flow node tree not found"))
            return {"CANCELLED"}
        if node is None:
            self.report({"ERROR"}, iface_("Quick-run node not found"))
            return {"CANCELLED"}
        return _run_quick_node_action_with_reporting(
            self,
            context,
            node_tree,
            node,
            root_tree_name=self.root_tree_name,
            group_path_json=self.group_path_json,
        )


class AF_OT_QuickRunNodeOverlayClick(bpy.types.Operator):
    bl_idname = "af.quick_run_node_overlay_click"
    bl_label = "Quick Run Overlay Click"
    bl_description = "Run the quick action from the overlay button"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return _get_active_flow_tree(context) is not None

    def invoke(self, context, event):
        node_tree = _get_active_flow_tree(context)
        region = getattr(context, "region", None)
        view2d = getattr(region, "view2d", None) if region is not None else None
        if node_tree is None or region is None or view2d is None or getattr(region, "type", "") != "WINDOW":
            return {"PASS_THROUGH"}

        from ..ui.overlay_context import _iter_visible_nodes, _node_editor_group_path, _node_editor_root_tree
        from ..ui.overlays import _quick_run_button_layout

        try:
            mouse_x = float(event.mouse_region_x)
            mouse_y = float(event.mouse_region_y)
        except Exception:
            return {"PASS_THROUGH"}

        visible_nodes = list(_iter_visible_nodes(node_tree, region=region, view2d=view2d, margin=120.0))
        node_order = {
            int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node): index
            for index, node in enumerate(getattr(node_tree, "nodes", []))
        }
        visible_nodes.sort(
            key=lambda node: node_order.get(int(node.as_pointer()) if hasattr(node, "as_pointer") else id(node), -1),
            reverse=True,
        )

        for node in visible_nodes:
            layout = _quick_run_button_layout(node, region=region, view2d=view2d)
            if layout is None:
                continue
            if not (
                float(layout["left"]) <= mouse_x <= float(layout["right"])
                and float(layout["bottom"]) <= mouse_y <= float(layout["top"])
            ):
                continue
            root_tree = _node_editor_root_tree(context, node_tree)
            group_path = _node_editor_group_path(context)
            result = bpy.ops.af.run_quick_node_action(
                "EXEC_DEFAULT",
                node_tree_name=str(getattr(node_tree, "name", "") or ""),
                node_name=str(getattr(node, "name", "") or ""),
                root_tree_name=str(getattr(root_tree, "name", "") or ""),
                group_path_json=json.dumps(list(group_path or []), ensure_ascii=True),
            )
            return set(result) if result is not None else {"FINISHED"}

        return {"PASS_THROUGH"}


class AF_OT_ClearStoredPropertyPackage(bpy.types.Operator):
    bl_idname = "af.clear_stored_property_package"
    bl_label = "Clear Stored Property Package"
    bl_description = "Clear stored Property Package data from this node"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if node_tree is None or getattr(node_tree, "bl_idname", "") != "AFNodeTreeType":
            self.report({"ERROR"}, "Automation Flow node tree not found")
            return {"CANCELLED"}
        node = node_tree.nodes.get(self.node_name)
        if node is None or getattr(node, "bl_idname", "") != "AFNodeStorePropertyPackage":
            self.report({"ERROR"}, "Store Prop Pack node not found")
            return {"CANCELLED"}
        try:
            from ..nodes import _ui_runner_for_node

            runner = _ui_runner_for_node(node, context)
            owner = runner._stored_property_package_owner(node) if runner is not None else None
            cleared_count = int(_clear_stored_property_package(node, owner=owner))
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to clear stored Property Package: {exc}")
            return {"CANCELLED"}
        _tag_flow_node_editor_redraw(None)
        if cleared_count <= 0:
            self.report({"INFO"}, "No stored Property Package data to clear")
            return {"CANCELLED"}
        self.report({"INFO"}, "Cleared stored Property Package data")
        return {"FINISHED"}


class AF_OT_HideDisabledPropertyDataSockets(bpy.types.Operator):
    bl_idname = "af.hide_disabled_property_data_sockets"
    bl_label = "Hide Disabled Field Sockets"
    bl_description = "Hide sockets for disabled property fields on the active Property Data node"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        node = getattr(context, "active_node", None)
        if node is None or getattr(node, "bl_idname", "") not in {
            "AFNodeModifierPropertyData",
            "AFNodeObjectDisplayPropertyData",
            "AFNodeObjectTransformPropertyData",
        }:
            self.report({"ERROR"}, "Active node is not a Property Data node")
            return {"CANCELLED"}

        try:
            from ..nodes import (
                _property_data_field_specs,
                _property_data_socket_key,
                _resolve_property_data_manual_hidden_keys,
                _sync_object_transform_property_data_sockets,
                _sync_property_data_node_sockets,
            )

            manual_hidden_keys = _resolve_property_data_manual_hidden_keys(node)
            for spec in _property_data_field_specs(node):
                enabled_attr = str(spec.get("capture_attr", "") or "")
                if not enabled_attr or bool(getattr(node, enabled_attr, False)):
                    continue
                input_name = str(spec.get("input_socket", "") or "")
                output_name = str(spec.get("output_socket", "") or "")
                if input_name:
                    manual_hidden_keys.add(_property_data_socket_key(is_output=False, socket_name=input_name))
                if output_name:
                    manual_hidden_keys.add(_property_data_socket_key(is_output=True, socket_name=output_name))

            if getattr(node, "bl_idname", "") == "AFNodeObjectTransformPropertyData":
                _sync_object_transform_property_data_sockets(node, manual_hidden_keys=manual_hidden_keys)
            else:
                _sync_property_data_node_sockets(node, manual_hidden_keys=manual_hidden_keys)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to hide disabled field sockets: {exc}")
            return {"CANCELLED"}

        _tag_flow_node_editor_redraw(getattr(getattr(node, "id_data", None), "name", None))
        return {"FINISHED"}


PROPERTY_OPERATOR_CLASSES = (
    AF_OT_RunStorePropertyPackageNode,
    AF_OT_RunApplyPropertyPackageNode,
    AF_OT_RunQuickNodeAction,
    AF_OT_QuickRunNodeOverlayClick,
    AF_OT_ClearStoredPropertyPackage,
    AF_OT_HideDisabledPropertyDataSockets,
)
