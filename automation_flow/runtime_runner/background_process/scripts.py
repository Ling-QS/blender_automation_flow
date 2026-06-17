from .script_templates import (
    background_auto_flow_bake_script_text,
    background_render_script_text,
    background_task_plan_script_text,
    background_task_step_script_text,
)


class RuntimeBackgroundProcessScriptsMixin:
    def _background_render_script_text(self):
        return background_render_script_text()

    def _background_task_plan_script_text(self):
        return background_task_plan_script_text()

    def _background_task_step_script_text(self):
        return background_task_step_script_text()

    def _background_auto_flow_bake_script_text(self):
        return background_auto_flow_bake_script_text()
