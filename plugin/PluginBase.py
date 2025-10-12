from abc import ABC, abstractmethod, ABCMeta

# from fastapi import APIRouter
from typing import Any
from modules.Logger import logger

from modules.Types import MessageType, MessageData


class PluginMeta(ABCMeta):
    plugins: list["PluginBase"] = []  # 存储所有插件实例的字典

    def __new__(cls, name: str, bases: tuple[type], namespace: dict[str, Any]) -> type:
        # 创建类
        new_class = super().__new__(cls, name, bases, namespace)

        # 如果不是基类，则实例化并存储插件
        if namespace["usable"]:
            plugin_instance = new_class()
            cls.plugins.append(plugin_instance)
            logger.info(f"注册插件: {plugin_instance.pluginName}")
        return new_class


class PluginBase(ABC, metaclass=PluginMeta):
    messageStartWith = ""  # only use for plugins that reply message startwith /
    usable = False

    @property
    @abstractmethod
    def messageType(self) -> MessageType.Group | MessageType.Person:
        pass

    @property
    @abstractmethod
    def pluginName(self) -> str:
        pass

    @abstractmethod
    async def run(self, message: MessageData) -> Any:
        pass
