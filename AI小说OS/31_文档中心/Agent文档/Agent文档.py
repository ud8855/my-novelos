# 31_文档中心/Agent文档/Agent文档.py
# 层级：文档中心层
# 依赖：20_模型协同（间接）、数据存储中心、配置中心
# 被调用：UI层、API服务、其他Agent（通过文档中心获取Agent信息）
# 解决问题：统一管理所有AI Agent的文档说明、能力描述、版本信息，支持动态更新和查询，确保Agent可被系统理解和使用

import logging
import os
from typing import Dict, List, Optional, Any

# 可插拔接口假设：所有文档模块需实现此协议
# 实际项目应从公共接口导入，这里作为占位
try:
    from 基础框架.插件接口 import DocPluginBase, PluginInfo
except ImportError:
    class DocPluginBase:  # type: ignore
        """文档基类占位，实际需继承项目公共接口"""
        def on_load(self):
            pass

        def on_unload(self):
            pass

    class PluginInfo:  # type: ignore
        """插件信息占位"""
        def __init__(self, name: str, version: str, description: str):
            self.name = name
            self.version = version
            self.description = description


# 配置中心占位
try:
    from 20_模型协同.配置中心 import get_config
except ImportError:
    def get_config(key: str, default=None):
        """配置获取占位，实际从配置中心读取"""
        return default


# 日志配置化
def _setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(get_config("DOC_LOG_LEVEL", "INFO"))
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = _setup_logger(__name__)


class AgentDocManager(DocPluginBase):
    """
    Agent文档管理器
    负责加载、缓存、查询和热更新所有Agent的文档数据。
    支持从配置文件、数据库或远程服务获取Agent元信息。
    """

    def __init__(self):
        super().__init__()
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._load_path: Optional[str] = None
        self._initialized = False

    @property
    def plugin_info(self) -> PluginInfo:
        """返回插件信息，用于可插拔管理"""
        return PluginInfo(
            name="AgentDocManager",
            version="0.1.0",
            description="管理所有AI Agent的文档、能力描述和版本信息"
        )

    def on_startup(self) -> None:
        """插件启动时调用，执行初始化"""
        logger.info("Agent文档管理器启动中...")
        self._load_path = get_config("AGENT_DOC_PATH", "./agent_docs/")
        self._load_documents()
        self._initialized = True
        logger.info("Agent文档管理器启动完成")

    def on_shutdown(self) -> None:
        """插件关闭时调用，执行清理"""
        logger.info("Agent文档管理器关闭")
        self._docs.clear()
        self._initialized = False

    def _load_documents(self) -> None:
        """从存储中加载所有Agent文档（骨架实现，未来对接具体数据源）"""
        logger.debug(f"尝试从 {self._load_path} 加载Agent文档")
        # TODO: 实际实现文件读取或数据库查询
        self._docs = {}
        logger.info(f"已加载 {len(self._docs)} 个Agent文档")

    def get_agent_doc(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定Agent的文档
        :param agent_id: Agent唯一标识
        :return: 文档数据字典，不存在返回None
        """
        if not self._initialized:
            logger.error("Agent文档管理器未初始化，无法获取文档")
            return None
        return self._docs.get(agent_id)

    def list_agents(self) -> List[str]:
        """
        列出所有已注册Agent的ID
        :return: Agent ID列表
        """
        if not self._initialized:
            logger.error("Agent文档管理器未初始化")
            return []
        return list(self._docs.keys())

    def search_agents(self, keyword: str) -> List[Dict[str, Any]]:
        """
        根据关键词搜索Agent文档（精确匹配或模糊搜索）
        :param keyword: 搜索词
        :return: 匹配的文档列表
        """
        if not self._initialized:
            logger.error("Agent文档管理器未初始化")
            return []
        # 简单关键词匹配（未来可扩展更高级搜索）
        matched = []
        for agent_doc in self._docs.values():
            if keyword.lower() in agent_doc.get("name", "").lower() \
                    or keyword.lower() in agent_doc.get("description", "").lower():
                matched.append(agent_doc)
        return matched

    def add_or_update_agent_doc(self, agent_id: str, doc_data: Dict[str, Any]) -> bool:
        """
        动态添加或更新Agent文档（热更新支持）
        :param agent_id: Agent ID
        :param doc_data: 文档数据
        :return: 是否操作成功
        """
        if not self._initialized:
            logger.error("Agent文档管理器未初始化，无法更新文档")
            return False
        if not agent_id or not doc_data:
            logger.warning("无效参数，agent_id或doc_data为空")
            return False
        # 进行更新（需要持久化到存储源，骨架仅修改内存）
        self._docs[agent_id] = doc_data
        logger.info(f"Agent文档 {agent_id} 已更新")
        # TODO: 触发通知其他依赖模块
        return True

    def remove_agent_doc(self, agent_id: str) -> bool:
        """
        移除一个Agent的文档
        :param agent_id: Agent ID
        :return: 是否成功移除
        """
        if not self._initialized:
            logger.error("Agent文档管理器未初始化")
            return False
        if agent_id in self._docs:
            del self._docs[agent_id]
            logger.info(f"Agent文档 {agent_id} 已移除")
            return True
        else:
            logger.warning(f"尝试移除不存在的Agent文档: {agent_id}")
            return False

    def validate_doc_schema(self, doc_data: Dict[str, Any]) -> bool:
        """
        验证文档数据是否符合预定格式（协议定义）
        :param doc_data: 待验证文档
        :return: 是否合法
        """
        required_keys = {"agent_id", "name", "description", "capabilities", "version"}
        missing = required_keys - set(doc_data.keys())
        if missing:
            logger.warning(f"文档缺少必要字段: {missing}")
            return False
        # 可进一步验证字段类型
        return True


# 可插拔入口：返回插件实例（项目规范）
def get_plugin_instance():
    return AgentDocManager()


# 自测代码
if __name__ == "__main__":
    # 配置临时日志输出以便测试
    logging.basicConfig(level=logging.DEBUG)

    print("=== Agent文档管理器自测 ===")
    mgr = AgentDocManager()
    mgr.on_startup()

    # 添加文档
    test_doc = {
        "agent_id": "writer_001",
        "name": "写作助手Alpha",
        "description": "擅长科幻小说创作",
        "capabilities": ["plot_generation", "character_design"],
        "version": "1.0"
    }
    if not mgr.validate_doc_schema(test_doc):
        print("文档验证失败")
    else:
        if mgr.add_or_update_agent_doc("writer_001", test_doc):
            print("添加成功")

    # 查询
    doc = mgr.get_agent_doc("writer_001")
    print("查询结果:", doc)

    # 搜索
    results = mgr.search_agents("科幻")
    print("搜索结果:", results)

    # 列出所有
    agents = mgr.list_agents()
    print("所有Agent:", agents)

    # 删除
    mgr.remove_agent_doc("writer_001")
    print("删除后列表:", mgr.list_agents())

    mgr.on_shutdown()
    print("自测结束")