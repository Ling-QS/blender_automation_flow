import copy

from ...runtime_core.constants import (
    FLOW_OK,
    PROPERTY_PACKAGE_ROLE_SNAPSHOT,
    PROPERTY_PACKAGE_SCOPE_MODIFIER,
    FlowExecutionError,
)
from ...node_system.socket_aliases import PROPERTY_PACKAGE_SOCKET_NAME
from ...runtime_refs.objects import _property_package_to_object_list as _property_package_to_object_list_impl
from ...runtime_property.definitions import (
    _clone_property_definition,
    _iter_property_definition_entries,
    _make_empty_property_definition,
    _normalize_property_definition_entries,
    _validate_property_definition,
)
from ...runtime_property.packages import (
    _iter_property_package_entries as _iter_property_package_entries_impl,
    _property_package_item_count as _property_package_item_count_impl,
    _property_package_to_definition as _property_package_to_definition_impl,
)


class RuntimePropertyPackageActionsMixin:
    def _property_package_item_count_for_actions(self, property_package):
        return _property_package_item_count_impl(property_package, self._is_composite_property_package)

    def _iter_property_package_entries_for_actions(self, property_package, node_name, allow_roles=None, allow_scopes=None):
        return _iter_property_package_entries_impl(
            property_package,
            node_name,
            allow_roles=allow_roles,
            allow_scopes=allow_scopes,
            validate_property_package=self._validate_property_package,
            is_composite_property_package=self._is_composite_property_package,
            clone_property_package=self._clone_property_package,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _property_package_to_definition_for_actions(self, property_package, node_name):
        return _property_package_to_definition_impl(
            property_package,
            node_name,
            validate_property_package=self._validate_property_package,
            is_composite_property_package=self._is_composite_property_package,
            iter_property_definition_entries=_iter_property_definition_entries,
            normalize_property_definition_entries=_normalize_property_definition_entries,
            make_empty_property_definition=_make_empty_property_definition,
            clone_property_definition=_clone_property_definition,
            validate_property_definition=_validate_property_definition,
        )

    def _property_package_to_object_list_for_actions(self, property_package, sort_mode):
        return _property_package_to_object_list_impl(
            property_package,
            sort_mode,
            is_composite_property_package=self._is_composite_property_package,
            dedup_obj_items=self._dedup_obj_items,
        )

    def _execute_property_package_action_node(self, node, dry_run=False):
        node_type = str(getattr(node, "bl_idname", "") or "")
        if node_type == "AFNodeStorePropertyPackage":
            return self._execute_store_property_package_node(node, dry_run=dry_run)
        if node_type == "AFNodeApplyObjectProperties":
            return self._execute_apply_object_properties_node(node, dry_run=dry_run)
        if node_type == "AFNodeApplyPropertyPackage":
            return self._execute_apply_property_package_node(node, dry_run=dry_run)
        if node_type == "AFNodeRecordPropertyPackage":
            return self._execute_record_property_package_node(node)
        return None

    def _execute_store_property_package_node(self, node, dry_run=False):
        property_package = None
        store_mode = str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
        if store_mode == "STORE_AND_OUTPUT":
            property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if property_package is None:
                raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
            self._validate_property_package(property_package, node.name)
            if not dry_run:
                self._write_stored_property_package(node, property_package)
        else:
            property_package = self._read_stored_property_package(node)
            if property_package is None:
                raise FlowExecutionError("AF_E011", "No stored Property Package is available", node.name)
            self._validate_property_package(property_package, node.name)
        if any(
            str(entry.get("package_role", "") or "") == PROPERTY_PACKAGE_ROLE_SNAPSHOT
            and str(entry.get("scope_kind", "") or "") == PROPERTY_PACKAGE_SCOPE_MODIFIER
            for entry in self._iter_property_package_entries_for_actions(property_package, node.name)
        ):
            self.last_snapshot_package = copy.deepcopy(property_package)
        self._set_output(node, "property_package", copy.deepcopy(property_package))
        report = {
            "package_role": str(property_package.get("package_role", "")),
            "scope_kind": str(property_package.get("scope_kind", "")),
            "count": self._property_package_item_count_for_actions(property_package),
            "mode": store_mode,
            "dry_run": bool(dry_run),
        }
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]

    def _execute_apply_object_properties_node(self, node, dry_run=False):
        object_list = self._get_linked_output(node, "Object List", "object_list")
        if object_list is None:
            raise FlowExecutionError("AF_E011", "Object List input is not linked", node.name)
        apply_mode = str(getattr(node, "apply_mode", "PACKAGE") or "PACKAGE")
        if apply_mode == "ASSIGNMENT":
            report = self._apply_object_properties_from_assignments_direct(node, object_list, dry_run=dry_run)
        else:
            property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
            if property_package is None:
                raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
            property_definition = self._property_package_to_definition_for_actions(property_package, node.name)
            report = self._apply_property_package(node, property_definition, property_package, object_list, dry_run=dry_run)
        report["object_count"] = int(object_list.get("count", 0))
        report["dry_run"] = bool(dry_run)
        report["apply_mode"] = apply_mode
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]

    def _execute_apply_property_package_node(self, node, dry_run=False):
        property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
        if property_package is None:
            raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
        property_definition = self._property_package_to_definition_for_actions(property_package, node.name)
        object_list = self._property_package_to_object_list_for_actions(property_package, "NAME_ASC")
        report = self._apply_property_package(node, property_definition, property_package, object_list, dry_run=dry_run)
        report["object_count"] = int(object_list.get("count", 0))
        report["dry_run"] = bool(dry_run)
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]

    def _execute_record_property_package_node(self, node):
        bake_context = self.property_package_bake_context if isinstance(self.property_package_bake_context, dict) else None
        if bake_context is None:
            report = {
                "recorded": False,
                "skipped": True,
                "reason": "outside_property_package_bake",
            }
            self._set_output(node, "report", report)
            return FLOW_OK, "SKIPPED"
        target_record_tree_name = str(bake_context.get("target_record_tree_name", "") or "").strip()
        target_record_node_name = str(bake_context.get("target_record_node_name", "") or "").strip()
        target_record_group_path = list(bake_context.get("target_record_group_path", []) or [])
        current_tree_name = str(getattr(getattr(node, "id_data", None), "name", "") or "")
        current_group_path = list(getattr(self, "current_group_path", []) or [])
        if (
            target_record_tree_name
            and target_record_node_name
            and (
                current_tree_name != target_record_tree_name
                or str(getattr(node, "name", "") or "") != target_record_node_name
                or current_group_path != target_record_group_path
            )
        ):
            report = {
                "recorded": False,
                "skipped": True,
                "reason": "other_record_node",
            }
            self._set_output(node, "report", report)
            return FLOW_OK, "SKIPPED"
        property_package = self._get_linked_output(node, PROPERTY_PACKAGE_SOCKET_NAME, "property_package")
        if property_package is None:
            raise FlowExecutionError("AF_E011", "Property Package input is not linked", node.name)
        frame = int(bake_context.get("frame", getattr(self.scene, "frame_current", 1)))
        report = self._record_property_package_current_frame(node, property_package, frame)
        self._set_output(node, "report", report)
        return FLOW_OK, report["count"]


__all__ = ["RuntimePropertyPackageActionsMixin"]
