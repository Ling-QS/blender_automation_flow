import copy
import json

from ...node_system.socket_aliases import find_node_input_socket
from ...runtime_core.constants import FlowExecutionError, PROPERTY_PACKAGE_ROLE_COMPOSITE
from ...runtime_flow.helpers import _find_single_from_input_socket
from ...runtime_property.packages import (
    _is_composite_property_package,
    _property_package_item_count,
)
from ...runtime_state.cache import (
    _fallback_group_instance_stored_property_package,
    _read_stored_property_package_direct,
    _rehydrate_property_package_object_references,
    _stored_property_package_key_for_node,
)


class RuntimeStoredPackageMixin:
    def _stored_property_package_owner(self, node):
        if self.current_group_path:
            try:
                return self._resolve_step_ref(self.current_group_path[-1], node.name)
            except FlowExecutionError:
                pass
        return node

    def _stored_property_package_key(self, node):
        return _stored_property_package_key_for_node(node)

    def _read_stored_property_package(self, node):
        owner = self._stored_property_package_owner(node)
        package = _read_stored_property_package_direct(node, owner=owner)
        if package is not None:
            return _rehydrate_property_package_object_references(
                package,
                object_resolver=self._find_object_by_item_cached,
                node_name=node.name,
            )
        if owner is node:
            fallback_package = _fallback_group_instance_stored_property_package(node)
            if fallback_package is not None:
                return _rehydrate_property_package_object_references(
                    fallback_package,
                    object_resolver=self._find_object_by_item_cached,
                    node_name=node.name,
                )
            return None
        return None

    def _write_stored_property_package(self, node, property_package):
        owner = self._stored_property_package_owner(node)
        if owner is None:
            raise FlowExecutionError("AF_E009", "Storage owner is missing", node.name)
        try:
            owner[self._stored_property_package_key(node)] = json.dumps(copy.deepcopy(property_package), ensure_ascii=True)
        except Exception as exc:
            raise FlowExecutionError("AF_E009", f"Failed to store Property Package: {exc}", node.name)

    def _preview_store_property_package_outputs(self, node, group_path=None):
        if node is None or getattr(node, "bl_idname", "") != "AFNodeStorePropertyPackage":
            return None, None

        active_group_path = list(self.current_group_path if group_path is None else group_path)
        previous_group_path = list(self.current_group_path)
        try:
            self.current_group_path = list(active_group_path)
            store_mode = str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT")
            if store_mode == "OUTPUT_ONLY":
                property_package = self._read_stored_property_package(node)
            else:
                property_package = self._read_stored_property_package(node)
                if property_package is None:
                    package_input = find_node_input_socket(node, "Property Package")
                    upstream_node, upstream_socket = _find_single_from_input_socket(package_input)
                    if upstream_node is not None:
                        property_package = self._get_output_from_source(upstream_node, upstream_socket, "property_package", active_group_path)
                        if property_package is None:
                            property_package = self.preview_flow_output(upstream_node, "property_package")
                        if property_package is None:
                            property_package = self._get_output_from_source(upstream_node, upstream_socket, "property_package", active_group_path)
            if property_package is None:
                return None, None
            report = {
                "package_role": str(property_package.get("package_role", "")),
                "scope_kind": str(property_package.get("scope_kind", "")),
                "count": self._property_package_item_count_for_preview(property_package),
                "mode": str(getattr(node, "store_mode", "STORE_AND_OUTPUT") or "STORE_AND_OUTPUT"),
                "dry_run": True,
            }
            return copy.deepcopy(property_package), report
        except FlowExecutionError:
            return None, None
        finally:
            self.current_group_path = previous_group_path

    def _property_package_item_count_for_preview(self, property_package):
        return _property_package_item_count(
            property_package,
            lambda package: _is_composite_property_package(package, PROPERTY_PACKAGE_ROLE_COMPOSITE),
        )


__all__ = ["RuntimeStoredPackageMixin"]
