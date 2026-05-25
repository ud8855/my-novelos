"""
事件总线模块 - 实现模块间松耦合通信
提供事件的订阅、发布、取消订阅功能，支持同步与异步执行，具备日志记录和异常恢复机制。
可插拔设计：通过实现IEventBus接口，可替换不同的事件总线实现。
配置化：支持通过配置字典控制行为（如最大线程数、是否异步等）。
"""

import abc
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
from concurrent.f