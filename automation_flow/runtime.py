import sys
import types

from .runtime_runner.core import FlowRunner
from .runtime_runner.core.active import get_active_runner, set_active_runner
from .runtime_core.constants import FlowExecutionError
from .runtime_core.runtime_exports import (
    ALL_EXPORTS,
    EXPORT_GROUPS,
    LEGACY_EXPORTS,
    STABLE_EXPORTS,
    has_runtime_export,
    resolve_runtime_export,
)


class _RuntimeModule(types.ModuleType):
    def __getattribute__(self, name):
        if name == "ACTIVE_RUNNER":
            return get_active_runner()
        try:
            return types.ModuleType.__getattribute__(self, name)
        except AttributeError:
            if has_runtime_export(name):
                return resolve_runtime_export(name)
            raise

    def __setattr__(self, name, value):
        if name == "ACTIVE_RUNNER":
            set_active_runner(value)
            return
        types.ModuleType.__setattr__(self, name, value)


__all__ = [
    "FlowRunner",
    "FlowExecutionError",
    "ACTIVE_RUNNER",
    "ALL_EXPORTS",
    "EXPORT_GROUPS",
    "LEGACY_EXPORTS",
    *STABLE_EXPORTS,
]


sys.modules[__name__].__class__ = _RuntimeModule
