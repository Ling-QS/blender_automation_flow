import os
import re

import bpy

from ...runtime_core.constants import (
    FlowExecutionError,
    PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
    PHYSICS_SUPPORTED_MODIFIER_TYPES,
    PROPERTY_PACKAGE_ROLE_COMPOSITE,
    PROPERTY_PACKAGE_ROLE_SETTINGS,
    PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE,
    TASK_KIND_PROPERTY_PACKAGE_BAKE,
    TASK_KIND_GEOMETRY,
    TASK_KIND_PHYSICS,
    TASK_KIND_PHYSICS_BAKE_ALL,
    TASK_KIND_RENDER,
)
from ...runtime_property.packages import (
    _clone_property_package,
    _is_composite_property_package,
    _physics_property_package_to_settings_payloads as _physics_property_package_to_settings_payloads_impl,
    _validate_property_package as _validate_property_package_impl,
)
from ...runtime_refs.objects import _object_list_from_task_ref as _object_list_from_task_ref_impl
from ...runtime_task_ref.helpers import (
    _frame_range_from_task_ref as _frame_range_from_task_ref_impl,
    _rehydrate_property_package_bake_predicted_items as _rehydrate_property_package_bake_predicted_items_impl,
)
from ...runtime_task_ref.refs import (
    _raise_if_invalid_task_ref as _raise_if_invalid_task_ref_impl,
    _rehydrate_task_ref_object_references as _rehydrate_task_ref_object_references_impl,
    _validate_task_ref_object_targets as _validate_task_ref_object_targets_impl,
)
from ...runtime_scene.objects import (
    _dedup_obj_items as _dedup_obj_items_impl,
    _ensure_object_persistent_uuid as _ensure_object_persistent_uuid_impl,
    _find_object_by_item as _find_object_by_item_impl,
    _obj_item as _obj_item_impl,
)
from ...runtime_persistence.serialization import _copy_runtime_state_value, _copy_task_ref_payload
from ...runtime_state.cache import _property_package_bake_action_name_from_task_ref
from ...runtime_task_target import (
    _point_cache_has_existing_cache as _point_cache_has_existing_cache_impl,
    _resolve_bake_entry,
    _resolve_bake_target as _resolve_bake_target_impl,
    _resolve_physics_batch_task_target as _resolve_physics_batch_task_target_impl,
    _resolve_physics_task_target as _resolve_physics_task_target_impl,
    _split_bake_task_path as _split_bake_task_path_impl,
    _split_physics_task_path as _split_physics_task_path_impl,
)


class RuntimeTaskRefCommonMixin:
    def _find_object_by_item(self, item):
        return _find_object_by_item_impl(item)

    def _component_path_for_modifier(self, obj, modifier_name):
        return f"{obj.name}/{modifier_name}"

    def _split_bake_task_path(self, task_path, node_name):
        return _split_bake_task_path_impl(
            task_path,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _resolve_bake_target(self, task_path, node_name):
        return _resolve_bake_target_impl(
            task_path,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            split_bake_task_path=self._split_bake_task_path,
            resolve_bake_entry=_resolve_bake_entry,
        )

    def _split_physics_task_path(self, task_path, node_name):
        return _split_physics_task_path_impl(
            task_path,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _resolve_physics_task_target(self, task_path, node_name):
        return _resolve_physics_task_target_impl(
            task_path,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            split_physics_task_path=self._split_physics_task_path,
            physics_supported_modifier_types=PHYSICS_SUPPORTED_MODIFIER_TYPES,
        )

    def _resolve_physics_batch_task_target(self, task_path, node_name):
        return _resolve_physics_batch_task_target_impl(
            task_path,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            resolve_physics_task_target=self._resolve_physics_task_target,
            physics_batch_supported_modifier_types=PHYSICS_BATCH_SUPPORTED_MODIFIER_TYPES,
        )

    def _ensure_object_persistent_uuid(self, obj):
        return _ensure_object_persistent_uuid_impl(obj)

    def _dedup_obj_items(self, items, sort_mode, object_resolver=None):
        return _dedup_obj_items_impl(items, sort_mode, object_resolver=object_resolver)

    def _clone_property_package(self, package):
        return _clone_property_package(package)

    def _is_composite_property_package(self, package):
        return _is_composite_property_package(package, PROPERTY_PACKAGE_ROLE_COMPOSITE)

    def _validate_property_package(self, package, node_name, allow_roles=None, allow_scopes=None):
        return _validate_property_package_impl(
            package,
            node_name,
            allow_roles=allow_roles,
            allow_scopes=allow_scopes,
            flow_execution_error_cls=FlowExecutionError,
            property_package_role_composite=PROPERTY_PACKAGE_ROLE_COMPOSITE,
        )

    def _physics_property_package_to_settings_payloads(self, package, node_name):
        return _physics_property_package_to_settings_payloads_impl(
            package,
            node_name,
            validate_property_package=self._validate_property_package,
            find_object_by_item=self._find_object_by_item,
            component_path_for_modifier=self._component_path_for_modifier,
            ensure_object_persistent_uuid=self._ensure_object_persistent_uuid,
            flow_execution_error_cls=FlowExecutionError,
            property_package_role_settings=PROPERTY_PACKAGE_ROLE_SETTINGS,
            property_package_scope_physics_bake=PROPERTY_PACKAGE_SCOPE_PHYSICS_BAKE,
        )

    def _property_package_bake_action_name_from_task_ref(self, task_ref):
        return _property_package_bake_action_name_from_task_ref(task_ref)

    def _object_list_from_task_ref(self, task_ref, sort_mode="NAME_ASC", scene=None):
        return _object_list_from_task_ref_impl(
            task_ref,
            sort_mode=sort_mode,
            scene=scene,
            rehydrate_task_ref_object_references=self._rehydrate_task_ref_object_references,
            rehydrate_property_package_bake_predicted_items=self._rehydrate_property_package_bake_predicted_items,
            copy_runtime_state_value=_copy_runtime_state_value,
            dedup_obj_items=self._dedup_obj_items,
            obj_item=_obj_item_impl,
            ensure_object_persistent_uuid=self._ensure_object_persistent_uuid,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        )

    def _frame_range_from_task_ref(self, task_ref, scene):
        return _frame_range_from_task_ref_impl(
            task_ref,
            scene,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
            task_kind_geometry=TASK_KIND_GEOMETRY,
        )

    def _rehydrate_task_ref_object_references(self, task_ref, object_resolver=None, scene=None):
        return _rehydrate_task_ref_object_references_impl(
            task_ref,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_physics=TASK_KIND_PHYSICS,
            task_kind_render=TASK_KIND_RENDER,
            task_kind_property_package_bake=TASK_KIND_PROPERTY_PACKAGE_BAKE,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
            copy_task_ref_payload=_copy_task_ref_payload,
            copy_runtime_state_value=_copy_runtime_state_value,
            ensure_object_persistent_uuid=self._ensure_object_persistent_uuid,
            find_object_by_item=self._find_object_by_item,
            dedup_obj_items=self._dedup_obj_items,
            scene=scene,
            object_resolver=object_resolver,
        )

    def _rehydrate_property_package_bake_predicted_items(self, task_ref, scene):
        return _rehydrate_property_package_bake_predicted_items_impl(
            task_ref,
            scene,
            predict_property_package_bake_targets_resilient=self._predict_property_package_bake_targets_resilient,
        )

    def _validate_task_ref_object_targets(self, task_ref, node_name):
        return _validate_task_ref_object_targets_impl(
            task_ref,
            node_name,
            flow_execution_error_cls=FlowExecutionError,
            task_kind_geometry=TASK_KIND_GEOMETRY,
            task_kind_physics=TASK_KIND_PHYSICS,
            task_kind_physics_bake_all=TASK_KIND_PHYSICS_BAKE_ALL,
        )

    def _raise_if_invalid_task_ref(self, task_ref, fallback_node_name):
        return _raise_if_invalid_task_ref_impl(
            task_ref,
            fallback_node_name,
            flow_execution_error_cls=FlowExecutionError,
        )

    def _point_cache_has_existing_cache(self, point_cache):
        return _point_cache_has_existing_cache_impl(
            point_cache,
            bpy_module=bpy,
            os_module=os,
            re_module=re,
        )


__all__ = ["RuntimeTaskRefCommonMixin"]
