import bpy
from bpy.app.translations import pgettext_iface as iface_

from .node_definitions import (
    initialize_default_nodes_module,
    register_classes,
    unregister_classes,
)
from .runtime_core.registration import safe_register_class, safe_unregister_class


initialize_default_nodes_module(globals())


def register():
    register_classes(CLASSES, safe_register_class, after_register=_schedule_preview_data_ui_refresh)


def unregister():
    unregister_classes(CLASSES, safe_unregister_class)
