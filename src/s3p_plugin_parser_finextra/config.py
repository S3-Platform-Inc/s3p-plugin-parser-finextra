import datetime

from s3p_sdk.plugin.config import (
    PluginConfig,
    CoreConfig,
    TaskConfig,
    trigger,
    MiddlewareConfig,
    modules,
    payload, RestrictionsConfig
)
from s3p_sdk.plugin.types import SOURCE
from s3p_sdk.module import (
    WebDriver,
)

config = PluginConfig(
    plugin=CoreConfig(
        reference='finextra',         # уникальное имя источника
        type=SOURCE,                            # Тип источника (SOURCE, ML, PIPELINE)
        files=['finextra.py', ],        # Список файлов, которые будут использоваться в плагине (эти файлы будут сохраняться в платформе)
        is_localstorage=False,
        restrictions=RestrictionsConfig(
            maximum_materials=300,
            to_last_material=None,
            from_date=datetime.datetime(2024, 8, 1),
            to_date=None,
        )
    ),
    task=TaskConfig(
        trigger=trigger.TriggerConfig(
            type=trigger.SCHEDULE,
            interval=datetime.timedelta(days=1),    # Интервал перезапуска плагина
        )
    ),
    middleware=MiddlewareConfig(
        modules=[
            modules.TimezoneSafeControlConfig(order=1, is_critical=True),
            modules.SaveOnlyNewDocuments(order=2, is_critical=True),
        ],
        bus=None,
    ),
    payload=payload.PayloadConfig(
        file='finextra.py',                 # python файл плагина (точка входа). Этот файл должен быть указан в `plugin.files[*]`
        classname='Finextra',               # имя python класса в указанном файле
        entry=payload.entry.EntryConfig(
            method='content',
            params=[
                payload.entry.ConstParamConfig('feeds', [
                    'https://www.finextra.com/rss/channel.aspx?channel=ai/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=blockchain/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=cards/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=payments/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=retail/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=risk/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=security/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=startups/feed',
                    'https://www.finextra.com/rss/channel.aspx?channel=transaction/feed',
                ])
            ]
        )
    )
)

__all__ = ['config']
