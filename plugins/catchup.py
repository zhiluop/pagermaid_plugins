"""
Catchup 插件 - 关键词触发回复
触发方式: 在群组中发送 /关键词
"""

import contextlib
import json
import random
import re
import time
from pathlib import Path
from typing import Optional, Dict, List

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message, Client
from pagermaid.utils import logs


# 配置文件路径
plugin_dir = Path(__file__).parent
config_file = plugin_dir / "catchup_config.json"
trigger_log_file = plugin_dir / "catchup_trigger_log.json"
data_file = plugin_dir / "catchup_data.json"

# 默认频率限制（秒）
DEFAULT_RATE_LIMIT = 3600


@Hook.on_startup()
async def plugin_startup():
    """插件初始化"""
    logs.info("Catchup 插件已加载")


@Hook.on_shutdown()
async def plugin_shutdown():
    """插件关闭"""
    logs.info("Catchup 插件已卸载")


# 模板数据
TEMPLATES_DATA = {
    "templates": [
        # 单人模板
        {"id": 1, "mode": "single", "content": "{name} 正在看着你"},
        {"id": 2, "mode": "single", "content": "{name} 收到了一条神秘消息"},
        {"id": 3, "mode": "single", "content": "有人在呼唤 {name}"},
        {"id": 4, "mode": "single", "content": "{name} 的名字被提及了"},
        {"id": 5, "mode": "single", "content": "{name} 突然感觉背后一凉"},
        # 双人模板
        {"id": 101, "mode": "dual", "content": "{trigger_user} 向 {target_user} 发送了信号"},
        {"id": 102, "mode": "dual", "content": "{trigger_user} 正在寻找 {target_user}"},
        {"id": 103, "mode": "dual", "content": "{target_user} 收到 {trigger_user} 的消息"},
        {"id": 104, "mode": "dual", "content": "{trigger_user} 呼唤了 {target_user}"},
        {"id": 105, "mode": "dual", "content": "{trigger_user} 对 {target_user} 说：在吗"},
    ]
}


class TemplateGenerator:
    """模板生成器"""

    def __init__(self):
        self.single_templates: List[str] = []
        self.dual_templates: List[str] = []
        self.load_templates()

    def load_templates(self):
        """加载模板"""
        for template in TEMPLATES_DATA["templates"]:
            if template["mode"] == "single":
                self.single_templates.append(template["content"])
            else:
                self.dual_templates.append(template["content"])
        logs.info(f"已加载 {len(self.single_templates)} 个单人模板和 {len(self.dual_templates)} 个双人模板")

    def generate_single(self, name: str) -> str:
        """生成单人回复"""
        if not self.single_templates:
            return f"{name} 收到了消息"
        template = random.choice(self.single_templates)
        return template.replace("{name}", name).replace("{target_user}", name)

    def generate_dual(self, trigger_user: str, target_user: str) -> str:
        """生成双人回复"""
        if not self.dual_templates:
            return f"{trigger_user} 向 {target_user} 发送了消息"
        template = random.choice(self.dual_templates)
        return template.replace("{trigger_user}", trigger_user).replace("{target_user}", target_user)


class CatchupConfigManager:
    """配置管理类"""

    def __init__(self):
        self.enabled: bool = False
        self.owner_id: Optional[int] = None
        self.keywords: Dict[str, Dict] = {}  # keyword -> {target_user_id, target_chat_id, rate_limit_seconds}
        self.load()

    def load(self):
        """从文件加载配置"""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.enabled = data.get("enabled", False)
                    self.owner_id = data.get("owner_id")
                    self.keywords = data.get("keywords", {})
                logs.info(f"Catchup 配置已加载，共 {len(self.keywords)} 个关键词")
            except Exception as e:
                logs.error(f"加载 Catchup 配置失败: {e}")
                self.keywords = {}
        else:
            self.keywords = {}

    def save(self):
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self.enabled,
                    "owner_id": self.owner_id,
                    "keywords": self.keywords,
                }, f, indent=4, ensure_ascii=False)
            logs.info("Catchup 配置已保存")
        except Exception as e:
            logs.error(f"保存 Catchup 配置失败: {e}")

    def add_keyword(self, keyword: str, target_user_id: int, target_chat_id: int, rate_limit: int = DEFAULT_RATE_LIMIT):
        """添加或更新关键词配置"""
        self.keywords[keyword] = {
            "target_user_id": target_user_id,
            "target_chat_id": target_chat_id,
            "rate_limit_seconds": rate_limit
        }
        self.save()
        return f"关键词 `{keyword}` 配置已更新"

    def delete_keyword(self, keyword: str) -> tuple[bool, str]:
        """删除关键词配置"""
        if keyword in self.keywords:
            del self.keywords[keyword]
            self.save()
            return True, f"关键词 `{keyword}` 已删除"
        return False, f"关键词 `{keyword}` 不存在"

    def get_keyword_config(self, keyword: str) -> Optional[Dict]:
        """获取关键词配置"""
        return self.keywords.get(keyword)

    def list_keywords(self) -> str:
        """列出所有关键词配置"""
        if not self.keywords:
            return "暂无关键词配置"
        lines = ["**关键词配置列表：**"]
        for keyword, config in self.keywords.items():
            lines.append(f"- `{keyword}` → 用户: `{config['target_user_id']}`, 群组: `{config['target_chat_id']}`, 限制: {config['rate_limit_seconds']}秒")
        return "\n".join(lines)


# 全局实例
config_manager = CatchupConfigManager()
