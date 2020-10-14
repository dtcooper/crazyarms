from django.apps import AppConfig


class CarbConfig(AppConfig):
    name = 'carb'
    verbose_name = 'Crazy Arms Radio Backend'

    def ready(self):
        from constance.apps import ConstanceConfig

        ConstanceConfig.verbose_name = 'Configuration'
