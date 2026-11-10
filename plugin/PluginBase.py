from abc import ABC, abstractmethod, ABCMeta

# from fastapi import APIRouter
from typing import Any
from modules.Logger import logger

from modules.Types import MessageType, MessageData


class PluginMeta(ABCMeta):
    """插件元类：类定义时自动实例化并注册。

    Attributes:
        plugins: 已注册的插件实例，顺序即分发优先级。
    """

    plugins: list["PluginBase"] = []

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        new_class = super().__new__(cls, name, bases, namespace, **kwargs)

        # 未显式声明 usable 的类按不可用处理，而不是直接 KeyError
        if namespace.get("usable", False):
            plugin_instance: PluginBase = new_class()
            cls.plugins.append(plugin_instance)
            logger.info(f"注册插件: {plugin_instance.pluginName}")
        return new_class


class PluginBase(ABC, metaclass=PluginMeta):
    messageStartWith: str | list[str] = (
        ""  # only use for plugins that reply message startwith /
    )
    usable = False

    @property
    @abstractmethod
    def messageType(
        self,
    ) -> (
        MessageType.Group
        | MessageType.Person
        | list[MessageType.Group | MessageType.Person]
    ):
        pass

    @property
    @abstractmethod
    def pluginName(self) -> str:
        pass

    @abstractmethod
    async def run(self, message: MessageData) -> Any:
        pass
