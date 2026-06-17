import copy

import bpy

from ..node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME
from ..runtime_runner.core import FlowRunner
from ..runtime_core.constants import FlowExecutionError, PROPERTY_PACKAGE_ROLE_SNAPSHOT, PROPERTY_PACKAGE_SCOPE_MODIFIER
from ..runtime_property.api import (
    _iter_property_package_entries,
    _property_package_item_count,
    _validate_property_package,
)
from ..runtime_state.cache import _clear_stored_property_package
from .editor_utils import _tag_flow_node_editor_redraw
from .flow_run import (
    _capture_runtime_ui_context,
    _get_active_runner,
    _resolve_af_flow_node,
    _resume_auto_follow_notifications,
    _suspend_auto_follow_notifications,
)


class AF_OT_RunStorePropertyPackageNode(bpy.types.Operator):
    bl_idname = "af.run_store_property_package_node"
    bl_label = "Store Prop Pack Now"
    bl_description = "Store the linked Prop Pack immediately without running the full flow"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree, node = _resolve_af_flow_node(self.node_tree_name, self.node_name, "AFNodeStorePropertyPackage")
        if node is None:
            self.report({"ERROR"}, "Store Prop Pack node not found")
            return {"CANCELLED"}

        scene = getattr(context, "scene", None) or bpy.context.scene
        runner = FlowRunner(node_tree, scene, ui_context=_capture_runtime_ui_context(context)) if scene is not None else None
        if runner is None:
            self.report({"ERROR"}, "Scene is not available")
            return {"CANCELLED"}

        _suspend_auto_follow_notifications()
        try:
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
            runner._set_output(
                node,
                "report",
                {
                    "package_role": str(property_package.get("package_role", "") or ""),
                    "scope_kind": str(property_package.get("scope_kind", "") or ""),
                    "count": _property_package_item_count(property_package),
                    "mode": "MANUAL_STORE",
                    "dry_run": False,
                },
            )
            runner._flush_status_report_cache()
        except FlowExecutionError as exc:
            self.report({"ERROR"}, str(exc.message or exc))
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to store Property Package: {exc}")
            return {"CANCELLED"}
        finally:
            _resume_auto_follow_notifications()

        _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
        self.report({"INFO"}, "Stored Prop Pack")
        return {"FINISHED"}


class AF_OT_RunApplyPropertyPackageNode(bpy.types.Operator):
    bl_idname = "af.run_apply_property_package_node"
    bl_label = "Apply Prop Pack Now"
    bl_description = "Apply this Prop Pack immediately without running the full flow"
    bl_options = {"REGISTER", "UNDO"}

    node_tree_name: bpy.props.StringProperty(name="Node Tree Name", default="")
    node_name: bpy.props.StringProperty(name="Node Name", default="")

    def execute(self, context):
        if _get_active_runner() is not None:
            self.report({"WARNING"}, "A flow is already running")
            return {"CANCELLED"}

        node_tree, node = _resolve_af_flow_node(self.node_tree_name, self.node_name, "AFNodeApplyPropertyPackage")
        if node is None:
            self.report({"ERROR"}, "Apply Prop Pack node not found")
            return {"CANCELLED"}

        scene = getattr(context, "scene", None) or bpy.context.scene
        runner = FlowRunner(node_tree, scene, ui_context=_capture_runtime_ui_context(context)) if scene is not None else None
        if runner is None:
            self.report({"ERROR"}, "Scene is not available")
            return {"CANCELLED"}

        _suspend_auto_follow_notifications()
        try:
            runner._execute_node(node)
            runner._flush_status_report_cache()
            report = dict(runner._get_output(node, "report") or {})
        except FlowExecutionError as exc:
            self.report({"ERROR"}, str(exc.message or exc))
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to apply Property Package: {exc}")
            return {"CANCELLED"}
        finally:
            _resume_auto_follow_notifications()

        _tag_flow_node_editor_redraw(getattr(node_tree, "name", None))
        applied_count = int(report.get("count", 0) or 0)
        self.report({"INFO"}, f"Applied Prop Pack ({applied_count})")
        return {"FINISHED"}


class AF_OT_ClearStoredPropertyPackage(bpy.types.Operator):
    bl_idname = "af.clear_stored_property_package"
    bl_label = "Clear Stored Prop Pack"
    bl_description = "Clear stored Prop Pack data from this node"
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
            self.report({"INFO"}, "No stored Prop Pack data to clear")
            return {"CANCELLED"}
        self.report({"INFO"}, "Cleared stored Prop Pack data")
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
    AF_OT_ClearStoredPropertyPackage,
    AF_OT_HideDisabledPropertyDataSockets,
)
