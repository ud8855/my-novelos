class WorkingMemory:
    """
    工作记忆模块
    用于管理Agent当前的短时上下文信息，如剧情状态、角色状态、最近事件等。
    支持热插拔、配置化、日志记录、异常恢复。
    """
    def __init__(self, config: dict = None):
        """
        初始化工作记忆
        :param config: 配置字典，例如 {'max_items': 100, 'cache_path': 'working_memory_cache.json'}
        """
        self._log = logging.getLogger(__name__)
        self._memory = {}
        self._config = config or {}
        self._max_items = self._config.get('max_items', 100)
        self._cache_path = self._config.get('cache_path', 'working_memory_cache.json')
        self._log.info("WorkingMemory initialized | max_items=%d", self._max_items)

    def store(self, key: str, value: object) -> bool:
        """
        存入一条工作记忆
        :param key: 键
        :param value: 值
        :return: 是否成功
        """
        try:
            if len(self._memory) >= self._max_items:
                self._log.warning("Memory full | key=%s | current_size=%d", key, len(self._memory))
                return False
            self._memory[key] = value
            self._log.debug("Stored | key=%s | type=%s", key, type(value).__name__)
            return True
        except Exception as e:
            self._log.error("Store failed | key=%s | error=%s", key, str(e))
            return False

    def retrieve(self, key: str) -> object:
        """
        检索一条工作记忆
        :param key: 键
        :return: 值，若不存在返回None
        """
        try:
            value = self._memory.get(key)
            self._log.debug("Retrieved | key=%s | found=%s", key, value is not None)
            return value
        except Exception as e:
            self._log.error("Retrieve failed | key=%s | error=%s", key, str(e))
            return None

    def update(self, key: str, value: object) -> bool:
        """
        更新已存在的工作记忆，若不存在则新建
        :param key: 键
        :param value: 值
        :return: 是否成功
        """
        try:
            self._memory[key] = value
            self._log.debug("Updated | key=%s", key)
            return True
        except Exception as e:
            self._log.error("Update failed | key=%s | error=%s", key, str(e))
            return False

    def delete(self, key: str) -> bool:
        """
        删除一条工作记忆
        :param key: 键
        :return: 是否成功
        """
        try:
            if key in self._memory:
                del self._memory[key]
                self._log.debug("Deleted | key=%s", key)
                return True
            else:
                self._log.debug("Delete skipped (not found) | key=%s", key)
                return False
        except Exception as e:
            self._log.error("Delete failed | key=%s | error=%s", key, str(e))
            return False

    def clear(self) -> bool:
        """
        清空所有工作记忆
        :return: 是否成功
        """
        try:
            self._memory.clear()
            self._log.info("Memory cleared")
            return True
        except Exception as e:
            self._log.error("Clear failed | error=%s", str(e))
            return False

    def get_all(self) -> dict:
        """
        获取当前整个工作记忆的快照
        :return: 字典形式的所有记忆项
        """
        try:
            return dict(self._memory)
        except Exception as e:
            self._log.error("Get all failed | error=%s", str(e))
            return {}

    def get_context(self) -> dict:
        """
        获取当前全局剧情上下文（即工作记忆内容）
        :return: 同get_all()
        """
        return self.get_all()

    def set_context(self, data: dict) -> bool:
        """
        用给定字典完全替换工作记忆
        :param data: 新的上下文字典
        :return: 是否成功
        """
        try:
            if not isinstance(data, dict):
                self._log.error("set_context requires a dict")
                return False
            self._memory = data.copy()
            self._log.info("Context replaced | items=%d", len(self._memory))
            return True
        except Exception as e:
            self._log.error("Set context failed | error=%s", str(e))
            return False

    def save_to_cache(self) -> bool:
        """
        将当前工作记忆持久化到缓存文件（支持热更新加载）
        :return: 是否成功
        """
        try:
            import json
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._memory, f, ensure_ascii=False, indent=2)
            self._log.info("Saved to cache | path=%s", self._cache_path)
            return True
        except Exception as e:
            self._log.error("Save to cache failed | error=%s", str(e))
            return False

    def load_from_cache(self) -> bool:
        """
        从缓存文件加载工作记忆
        :return: 是否成功
        """
        try:
            import json, os
            if not os.path.exists(self._cache_path):
                self._log.warning("Cache file not found | path=%s", self._cache_path)
                return False
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                self._memory = json.load(f)
            self._log.info("Loaded from cache | items=%d", len(self._memory))
            return True
        except Exception as e:
            self._log.error("Load from cache failed | error=%s", str(e))
            return False

    def __repr__(self):
        return f"<WorkingMemory items={len(self._memory)} max={self._max_items}>"


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 自测代码
    wm = WorkingMemory({'max_items': 5, 'cache_path': 'test_wm_cache.json'})
    assert wm.store('plot', '主角进入森林')
    assert wm.store('characters', {'Alice': 'happy', 'Bob': 'curious'})
    assert wm.retrieve('plot') == '主角进入森林'
    assert wm.update('plot', '主角发现遗迹')
    assert wm.retrieve('plot') == '主角发现遗迹'
    assert wm.delete('characters')
    assert wm.retrieve('characters') is None
    assert len(wm.get_all()) == 1
    assert wm.get_context()['plot'] == '主角发现遗迹'
    # 快照不污染原数据
    snap = wm.get_all()
    snap['plot'] = 'changed'
    assert wm.retrieve('plot') == '主角发现遗迹'
    # 设置上下文
    wm.set_context({'new_story': '太空冒险'})
    assert wm.retrieve('new_story') == '太空冒险'
    assert wm.retrieve('plot') is None
    # 保存和加载缓存
    wm.save_to_cache()
    wm.clear()
    assert len(wm.get_all()) == 0
    wm.load_from_cache()
    assert wm.retrieve('new_story') == '太空冒险'
    # 清理缓存文件
    import os
    if os.path.exists('test_wm_cache.json'):
        os.remove('test_wm_cache.json')
    print("All tests passed.")