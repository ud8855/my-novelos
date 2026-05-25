# 模块路径: 18_读者模拟/评论模拟/评论模拟.py
# 功能: 评论模拟器, 根据小说内容生成多种读者类型的模拟评论
# 依赖: 20_模型协同/模型编排 (ModelCoordinator), 21_API模型 (API调用)
# 被调用层次: 由读者模拟上层模块或调度器调用
# 注意: 可插拔设计, 支持配置化读者角色与生成策略

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

# 配置日志
logger = logging.getLogger(__name__)

class CommentSimulatorConfig:
    """评论模拟器配置类, 负责从外部加载或提供默认配置"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "comment_sim_config.json"
        self.data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件, 若不存在则返回默认配置"""
        default_config = {
            "reader_roles": {
                "挑刺读者": {"style": "批评, 严谨", "max_length": 100},
                "赞美读者": {"style": "热情, 鼓励", "max_length": 80},
                "剧情讨论读者": {"style": "分析, 提问", "max_length": 120},
            },
            "generation_params": {
                "temperature": 0.8,
                "max_tokens": 150,
                "top_p": 0.9
            },
            "default_role": "剧情讨论读者",
            "enable_cache": True,
            "log_level": "INFO"
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    logger.info(f"评论模拟器配置已从 {self.config_path} 加载")
                    return {**default_config, **loaded}
            except Exception as e:
                logger.exception(f"加载配置文件失败: {e}, 使用默认配置")
        else:
            logger.info(f"配置文件 {self.config_path} 不存在, 使用默认配置")
            # 可选: 保存默认配置
            self._save_config(default_config)
        return default_config

    def _save_config(self, config: Dict) -> None:
        """保存当前配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"默认配置已保存到 {self.config_path}")
        except Exception as e:
            logger.error(f"保存默认配置失败: {e}")

    def get_reader_roles(self) -> Dict[str, Dict]:
        return self.data.get("reader_roles", {})

    def get_generation_params(self) -> Dict[str, Any]:
        return self.data.get("generation_params", {})

    def get_default_role(self) -> str:
        return self.data.get("default_role", "剧情讨论读者")


class CommentSimulator:
    """
    评论模拟器主类
    根据小说章节内容, 模拟不同读者类型的评论。
    通过模型协同层调用AI模型生成评论文本。
    """

    def __init__(self, config: Optional[CommentSimulatorConfig] = None,
                 model_coordinator: Any = None):
        """
        初始化评论模拟器
        :param config: 配置对象, 若为None则使用默认配置
        :param model_coordinator: 模型协同器实例, 负责调用底层API模型
        """
        self.config = config or CommentSimulatorConfig()
        self.reader_roles = self.config.get_reader_roles()
        self.gen_params = self.config.get_generation_params()
        self.default_role = self.config.get_default_role()
        
        # 模型协同层接口(占位符, 实际依赖注入)
        self.model_coordinator = model_coordinator
        if model_coordinator is None:
            logger.warning("模型协同器未注入, 评论模拟将使用简化模式或无输出")
        
        logger.info("评论模拟器初始化完成")

    def simulate_comments(self, chapter_content: str,
                          roles: Optional[List[str]] = None,
                          num_per_role: int = 2,
                          additional_context: str = "") -> Dict[str, List[str]]:
        """
        为指定章节内容生成模拟评论
        :param chapter_content: 章节文本内容
        :param roles: 需要的读者角色列表, 若为None则使用所有已配置角色
        :param num_per_role: 每个角色生成的评论数量
        :param additional_context: 额外上下文信息(如章节摘要、读者历史等)
        :return: 字典, 键为角色名, 值为评论列表
        """
        if not roles:
            roles = list(self.reader_roles.keys())
        
        result = {}
        for role in roles:
            role_config = self.reader_roles.get(role)
            if not role_config:
                logger.warning(f"未找到读者角色配置: {role}, 跳过")
                continue
            
            comments = []
            for i in range(num_per_role):
                comment = self._generate_single_comment(
                    chapter_content=chapter_content,
                    role=role,
                    role_config=role_config,
                    additional_context=additional_context
                )
                if comment:
                    comments.append(comment)
            result[role] = comments
            logger.info(f"为角色 '{role}' 生成了 {len(comments)} 条评论")
        return result

    def _generate_single_comment(self, chapter_content: str,
                                 role: str,
                                 role_config: Dict[str, Any],
                                 additional_context: str) -> Optional[str]:
        """
        生成单条评论的核心方法
        :return: 生成的评论文本, 失败时返回None
        """
        prompt = self._build_prompt(chapter_content, role, role_config, additional_context)
        try:
            if self.model_coordinator:
                # 通过模型协同层调用AI模型
                response = self.model_coordinator.generate_text(
                    prompt=prompt,
                    **self.gen_params
                )
                return response.strip()
            else:
                # 若无模型协同器, 返回模拟数据用于测试
                logger.debug("无模型协同器, 返回模拟评论")
                return f"[模拟评论({role})] 这是一条针对本章内容的自动评论。"
        except Exception as e:
            logger.exception(f"生成评论失败 (角色={role}): {e}")
            return None

    def _build_prompt(self, chapter_content: str, role: str,
                      role_config: Dict[str, Any], additional_context: str) -> str:
        """
        构建发送给模型的提示词模板
        """
        style = role_config.get("style", "")
        max_len = role_config.get("max_length", 100)
        
        prompt_parts = [
            f"你是一位{role}的小说读者。",
            f"请以{style}的口吻, 针对以下小说章节内容撰写一条简短评论(不超过{max_len}字)。",
        ]
        if additional_context:
            prompt_parts.append(f"额外背景信息: {additional_context}")
        prompt_parts.append(f"章节内容:\n{chapter_content}")
        prompt_parts.append("评论:")
        return "\n".join(prompt_parts)

    def clear_cache(self):
        """清除内部缓存(如果启用了缓存机制)"""
        if self.config.data.get("enable_cache"):
            logger.info("清除评论模拟器缓存")
            # 实现缓存清理逻辑
        else:
            logger.debug("缓存未启用, 无需清除")

    def update_config(self, new_config: Dict[str, Any]):
        """热更新配置"""
        logger.info("热更新评论模拟器配置")
        self.config.data.update(new_config)
        self.reader_roles = self.config.get_reader_roles()
        self.gen_params = self.config.get_generation_params()
        self.default_role = self.config.get_default_role()


def self_test():
    """
    自测函数: 演示评论模拟器的基本用法
    """
    print("开始评论模拟器自测...")
    # 设置日志级别以便查看
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 模拟章节内容
    test_chapter = (
        "夜幕降临, 林越站在城墙上, 望着远处连绵的灯火。\n"
        "身后传来脚步声, 她没有回头, 只是淡淡地问: '准备好了吗?'\n"
        "'准备好了。' 一个低沉的声音回答。\n"
        "她转过身, 看着面前的黑衣男子, 眼中闪过一丝复杂。\n"
        "'记住, 一切按计划行事。' 她低声说完, 身影消失在夜色之中。"
    )
    
    # 创建模拟器实例 (无模型协同器, 使用模拟数据)
    simulator = CommentSimulator()
    
    # 生成评论, 每个角色1条
    roles_to_use = ["挑刺读者", "赞美读者", "剧情讨论读者"]
    comments = simulator.simulate_comments(test_chapter, roles=roles_to_use, num_per_role=1)
    
    for role, comment_list in comments.items():
        print(f"\n【{role}】:")
        for idx, comment in enumerate(comment_list, 1):
            print(f"  {idx}. {comment}")
    
    print("\n自测完成。")

if __name__ == "__main__":
    self_test()