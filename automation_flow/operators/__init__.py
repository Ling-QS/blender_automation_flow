import sys
import types

from ..runtime_core.module_exports import resolve_module_export
from ..runtime_core.registration import safe_register_class, safe_unregister_class
from . import (
    assembly,
    bake_helpers,
    bake_ops,
    dynamic_inputs,
    flow_reload,
    flow_run,
    group_interface,
    group_navigation,
    misc_ops,
    node_add_ops,
    property_ops,
    run_ops,
    status_ops,
)

_OPERATOR_EXPORT_MODULES = (
    bake_helpers,
    flow_run,
    flow_reload,
    bake_ops,
    dynamic_inputs,
    group_navigation,
    group_interface,
    misc_ops,
    node_add_ops,
    property_ops,
    run_ops,
    status_ops,
)

CLASSES = assembly.build_operator_classes(
    run_ops=run_ops,
    status_ops=status_ops,
    dynamic_inputs=dynamic_inputs,
    misc_ops=misc_ops,
    node_add_ops=node_add_ops,
    group_navigation=group_navigation,
    bake_ops=bake_ops,
    property_ops=property_ops,
    group_interface=group_interface,
)

def register():
    assembly.register_operator_classes(CLASSES, safe_register_class)
    assembly.register_group_navigation_keymaps()
    flow_run.register_handlers()


def unregister():
    flow_run.unregister_handlers()
    assembly.unregister_group_navigation_keymaps()
    assembly.unregister_operator_classes(CLASSES, safe_unregister_class)


class _OperatorsModule(types.ModuleType):
    _FLOW_RUN_PROXY_NAMES = {
        "_AUTO_FOLLOW_LAST_PLAY_STATE",
        "_is_animation_playing",
    }

    def __getattribute__(self, name):
        if name in _OperatorsModule._FLOW_RUN_PROXY_NAMES:
            return getattr(flow_run, name)
        return types.ModuleType.__getattribute__(self, name)

    def __getattr__(self, name):
        return resolve_module_export(_OPERATOR_EXPORT_MODULES, name, __name__)

    def __setattr__(self, name, value):
        if name in _OperatorsModule._FLOW_RUN_PROXY_NAMES:
            setattr(flow_run, name, value)
        types.ModuleType.__setattr__(self, name, value)


sys.modules[__name__].__class__ = _OperatorsModule

__all__ = [
    "bake_helpers",
    "bake_ops",
    "assembly",
    "dynamic_inputs",
    "flow_reload",
    "flow_run",
    "group_interface",
    "group_navigation",
    "misc_ops",
    "node_add_ops",
    "property_ops",
    "run_ops",
    "status_ops",
    "CLASSES",
    "register",
    "unregister",
]
