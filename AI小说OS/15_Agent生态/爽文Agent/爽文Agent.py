# 15_Agent生态/爽文Agent/爽文Agent.py
"""
爽文Agent - 专门负责生成快节奏、高爽点的小说内容。
可插拔设计：通过配置切换不同的爽文模板、模型服务、质量检查器等。
"""
import logging
import json
import time
from typing import Dict, Any, Optional, Callable

# 配置日志
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class BaseAgent:
    """Agent基类，定义通用接口，实际项目中可从公共模块导入"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_running = False

    def configure(self, config: Dict[str, Any]):
        self.config = config

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False

    def health_check(self) -> bool:
        return self.is_running

class ShuangWenAgent(BaseAgent):
    """
    爽文创作Agent。
    
    可插拔组件：
    - model_service: 调用底层模型的服务 (需遵循 20_模型协同/)
    - prompt_templates: 爽文提示词模板 (模板化)
    - quality_controller: 输出质量控制器
    - post_processor: 后处理器 (比如润色、格式化)
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        default_config = {
            "agent_name": "ShuangWenAgent",
            "version": "0.1.0",
            "model_service_type": "default",  # 将在20_模型协同中解析
            "prompt_templates": {
                "outline_to_chapter": "prompts/shuangwen/outline_to_chapter.j2",
                "continue_from_cliffhanger": "prompts/shuangwen/cliffhanger.j2",
                "power_up_scene": "prompts/shuangwen/power_up.j2"
            },
            "quality_threshold": 0.8,
            "max_retries": 3,
            "enable_post_process": True
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)
        
        # 可插拔组件实例
        self.model_service = None
        self.prompt_loader = None
        self.quality_checker = None
        self.post_processor = None
        
        # 内部状态
        self.session_context = {}
        self.statistics = {
            "total_tasks": 0,
            "success_tasks": 0,
            "total_tokens": 0,
            "avg_generation_time": 0.0
        }
        logger.info(f"爽文Agent初始化，配置: {self.config}")

    def register_model_service(self, model_service):
        """
        注入模型服务 (来自20_模型协同/)
        参数:
            model_service: 需实现 generate(prompt, **kwargs) 方法
        """
        self.model_service = model_service
        logger.info("模型服务注入成功")

    def register_prompt_loader(self, loader):
        """注入模板加载器"""
        self.prompt_loader = loader
        logger.info("模板加载器注入成功")

    def register_quality_checker(self, checker):
        """注入质量检查器"""
        self.quality_checker = checker
        logger.info("质量检查器注入成功")

    def register_post_processor(self, processor):
        """注入后处理器"""
        self.post_processor = processor
        logger.info("后处理器注入成功")

    def load_prompt(self, template_key: str, **kwargs) -> str:
        """
        从模板库加载并渲染提示词。
        若未注入loader，则返回基础文本。
        """
        if self.prompt_loader:
            return self.prompt_loader.load(template_key, **kwargs)
        else:
            # Fallback: 简单的字符串替换
            template_path = self.config["prompt_templates"].get(template_key, "")
            logger.warning(f"使用默认提示词生成，模板key={template_key}, 路径={template_path}")
            # 这里只做演示，实际应读取文件并渲染Jinja2
            return f"【默认爽文提示】基于设定生成爽点内容，参数: {json.dumps(kwargs, ensure_ascii=False)}"

    def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理创作任务。
        任务格式示例:
            {
                "task_type": "outline_to_chapter|continue|power_up",
                "input_data": { ... },   # 输入参数
                "options": { ... }       # 额外选项
            }
        返回:
            {
                "success": True/False,
                "output": "生成的文本",
                "metadata": { ... }
            }
        """
        if not self.is_running:
            return {"success": False, "error": "Agent未启动"}
        if not self.model_service:
            return {"success": False, "error": "未注册模型服务，无法生成"}

        task_type = task.get("task_type", "outline_to_chapter")
        input_data = task.get("input_data", {})
        options = task.get("options", {})

        logger.info(f"接收到爽文任务，类型: {task_type}, 选项: {options}")
        start_time = time.time()
        self.statistics["total_tasks"] += 1

        # 1. 加载对应提示词模板
        template_key_map = {
            "outline_to_chapter": "outline_to_chapter",
            "continue": "continue_from_cliffhanger",
            "power_up": "power_up_scene"
        }
        template_key = template_key_map.get(task_type, "outline_to_chapter")
        prompt = self.load_prompt(template_key, **input_data, **options)

        # 2. 调用模型生成 (重试机制)
        attempt = 0
        generated_text = ""
        while attempt < self.config["max_retries"]:
            try:
                response = self.model_service.generate(
                    prompt=prompt,
                    **options.get("generation_kwargs", {})
                )
                if isinstance(response, dict):
                    generated_text = response.get("text", "")
                else:
                    generated_text = str(response)
                break
            except Exception as e:
                attempt += 1
                logger.error(f"模型调用失败 (尝试 {attempt}/{self.config['max_retries']}): {str(e)}")
                if attempt >= self.config["max_retries"]:
                    return {"success": False, "error": f"模型生成失败: {str(e)}"}
                time.sleep(1)

        # 3. 质量检查 (可插拔)
        if self.quality_checker:
            quality_score, feedback = self.quality_checker.evaluate(generated_text)
            logger.info(f"质量得分: {quality_score}, 反馈: {feedback}")
            if quality_score < self.config["quality_threshold"]:
                # 可在此重新生成或标记
                logger.warning("生成内容质量低于阈值，但骨架暂不做重试")

        # 4. 后处理 (可插拔)
        if self.enable_post_process and self.post_processor:
            generated_text = self.post_processor.process(generated_text, task_type)

        # 统计
        elapsed = time.time() - start_time
        self.statistics["success_tasks"] += 1
        # 假设token估算
        self.statistics["total_tokens"] += len(prompt) + len(generated_text)
        # 更新平均生成时间
        prev_avg = self.statistics["avg_generation_time"]
        n = self.statistics["success_tasks"]
        self.statistics["avg_generation_time"] = (prev_avg * (n - 1) + elapsed) / n

        logger.info(f"爽文生成完成，耗时 {elapsed:.2f}s，文本长度: {len(generated_text)}")

        return {
            "success": True,
            "output": generated_text,
            "metadata": {
                "task_type": task_type,
                "generation_time": elapsed,
                "context": self.session_context.get("last_output_id", None)
            }
        }

    def start(self):
        super().start()
        logger.info("爽文Agent已启动")

    def stop(self):
        super().stop()
        logger.info("爽文Agent已停止")

    def health_check(self) -> bool:
        # 除了运行状态，还检查必要服务是否正常
        if not self.model_service:
            return False
        # 可以ping模型服务
        try:
            # 这里简化，实际调用health接口
            return self.is_running
        except:
            return False

    def get_statistics(self) -> Dict[str, Any]:
        return self.statistics

# 自测代码
if __name__ == "__main__":
    # 设置日志输出到控制台
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 模拟一个简单的模型服务（用于测试）
    class MockModelService:
        def generate(self, prompt, **kwargs):
            # 模拟生成爽文内容
            return {"text": f"【爽文自动生成】\n主角逆袭！\n根据提示生成内容：{prompt[:100]}...【待续】"}

    # 初始化Agent
    agent = ShuangWenAgent()
    # 注入模拟模型服务
    agent.register_model_service(MockModelService())
    agent.start()

    # 测试任务
    task = {
        "task_type": "outline_to_chapter",
        "input_data": {"outline": "废柴男主获得金手指，开始打脸反派"},
        "options": {}
    }
    result = agent.process(task)
    print("\n生成结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    agent.stop()
    print("\n统计信息:", agent.get_statistics())