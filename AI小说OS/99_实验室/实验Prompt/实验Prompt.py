"""
实验Prompt模块

负责管理实验性的Prompt模板，支持动态注册、更新、删除和渲染。
遵循可插拔、配置化原则。
"""

import logging
from typing import Dict, Optional, Any

# 获取模块级日志记录器
logger = logging.getLogger(__name__)


class ExperimentPromptManager:
    """
    实验Prompt管理器
    
    提供对实验性Prompt模板的集中管理，支持模板注册、获取、渲染和配置化加载。
    """

    def __init__(self):
        self._templates: Dict[str, str] = {}
        logger.info("ExperimentPromptManager initialized")

    def register_template(self, name: str, template: str) -> None:
        """
        注册一个实验性Prompt模板
        
        参数:
            name: 模板名称，唯一标识
            template: 模板字符串，支持占位符 {var}
        """
        if not name:
            raise ValueError("Template name cannot be empty")
        self._templates[name] = template
        logger.info(f"Registered experiment prompt template: {name}")

    def remove_template(self, name: str) -> bool:
        """
        移除一个模板
        
        返回:
            True如果成功移除，False如果不存在
        """
        if name in self._templates:
            del self._templates[name]
            logger.info(f"Removed experiment prompt template: {name}")
            return True
        else:
            logger.warning(f"Attempted to remove non-existent template: {name}")
            return False

    def update_template(self, name: str, template: str) -> None:
        """
        更新已存在的模板内容
        """
        if name not in self._templates:
            logger.warning(f"Template '{name}' does not exist, registering as new")
        self._templates[name] = template
        logger.info(f"Updated experiment prompt template: {name}")

    def get_template(self, name: str) -> Optional[str]:
        """
        获取模板字符串，如不存在返回None
        """
        template = self._templates.get(name)
        if template is None:
            logger.warning(f"Experiment prompt template not found: {name}")
        return template

    def render_template(self, name: str, **kwargs: Any) -> str:
        """
        渲染模板，使用传入的关键字参数填充占位符
        
        参数:
            name: 模板名称
            **kwargs: 用于填充模板的变量值
        
        返回:
            填充后的字符串
        
        异常:
            ValueError: 如果模板不存在或缺少必要的占位符
        """
        template = self.get_template(name)
        if template is None:
            raise ValueError(f"Template '{name}' not found")
        try:
            rendered = template.format(**kwargs)
        except KeyError as e:
            missing_key = e.args[0]
            logger.error(f"Missing variable '{missing_key}' for template '{name}'")
            raise ValueError(f"Missing variable '{missing_key}' for template '{name}'") from e
        logger.debug(f"Rendered template '{name}'")
        return rendered

    def list_templates(self) -> list:
        """列出所有已注册模板名称"""
        return list(self._templates.keys())

    def load_from_config(self, config: Dict[str, str]) -> None:
        """
        从字典配置加载多个模板
        
        参数:
            config: 键为模板名，值为模板字符串的字典
        """
        for name, template in config.items():
            self.register_template(name, template)
        logger.info(f"Loaded {len(config)} templates from config")

    def reload_from_file(self, file_path: str) -> None:
        """
        从配置文件重新加载所有实验模板（会清空现有模板后再加载）
        
        参数:
            file_path: 配置文件路径，支持JSON/YAML等格式
        """
        # 占位：实际加载逻辑
        logger.warning("reload_from_file not implemented, placeholder")
        # TODO: 实现根据文件扩展名解析，清空当前模板并加载
        raise NotImplementedError("reload_from_file is not yet implemented")


# 全局单例，方便其它模块导入使用
_experiment_prompt_manager = ExperimentPromptManager()


def get_experiment_prompt_manager() -> ExperimentPromptManager:
    """获取全局实验Prompt管理器实例"""
    return _experiment_prompt_manager


# ---- 自测代码 ----
if __name__ == "__main__":
    # 配置基本日志用于测试
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    print("=== 实验Prompt模块自测 ===")
    mgr = get_experiment_prompt_manager()
    
    # 测试注册
    mgr.register_template("test1", "Hello, {name}!")
    mgr.register_template("test2", "You are a {role}.")
    
    # 测试列表
    print("已注册模板:", mgr.list_templates())
    
    # 测试获取
    print("模板test1:", mgr.get_template("test1"))
    
    # 测试渲染
    try: