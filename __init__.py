bl_info = {
    "name": "Automation Flow",
    "author": "Codex",
    "version": (0, 1, 0),
    "blender": (5, 1, 0),
    "location": "Node Editor > Automation Flow",
    "description": "Node-based automation flow for modifier state and GN bake orchestration",
    "category": "Node",
}

from .runtime_core.module_loading import load_local_submodules

_MODULE_SPECS = (
    ("translations", "translations"),
    ("node_definitions", "node_definitions"),
    ("node_system", "node_system"),
    ("_node_system_config", "node_system.config"),
    ("_node_system_editor_context", "node_system.editor_context"),
    ("_node_system_pair_helpers", "node_system.pair_helpers"),
    ("sockets", "node_system.sockets"),
    ("tree", "node_system.tree"),
    ("nodes", "nodes"),
    ("operators", "operators"),
    ("ui", "ui"),
)

load_local_submodules(globals(), __package__, _MODULE_SPECS)

MODULES = (
    translations,
    tree,
    sockets,
    nodes,
    operators,
    ui,
)


def register():
    tree.suspend_runtime_sync()
    try:
        for module in MODULES:
            module.register()
    finally:
        tree.resume_runtime_sync()
    tree.queue_post_register_sync()


def unregister():
    tree.suspend_runtime_sync()
    try:
        for module in reversed(MODULES):
            module.unregister()
    finally:
        tree.resume_runtime_sync()
