from ..runtime_core.registration import safe_register_class, safe_unregister_class
from . import (
    assembly,
    bake_helpers,
    bake_ops,
    dynamic_inputs,
    flow_reload,
    flow_run,
    group_assets,
    group_interface,
    group_navigation,
    misc_ops,
    node_add_ops,
    property_ops,
    run_ops,
    status_ops,
)

assembly.initialize_default_operators_module(globals())
assembly.install_operator_module_proxy(globals())

def register():
    assembly.register_operator_classes(CLASSES, safe_register_class)
    assembly.register_group_navigation_keymaps()
    flow_run.register_handlers()


def unregister():
    flow_run.unregister_handlers()
    assembly.unregister_group_navigation_keymaps()
    assembly.unregister_operator_classes(CLASSES, safe_unregister_class)

__all__ = list(assembly.OPERATOR_MODULE_EXPORTS)
