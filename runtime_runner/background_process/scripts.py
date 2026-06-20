from .script_templates import background_task_plan_script_text


class RuntimeBackgroundProcessScriptsMixin:
    def _background_task_plan_script_text(self):
        return background_task_plan_script_text()
