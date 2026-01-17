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
        self.enabled: bool = False  # 插件总开关，控制所有关键词是否生效
        self.owner_id: Optional[int] = None  # 插件所有者ID，只有所有者可以管理配置
        self.keywords: Dict[str, Dict] = {}  # keyword -> {target_user_id, target_chat_id, rate_limit_seconds}
        self.load()

    def load(self) -> None:
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
                # 重置所有属性，避免数据不一致
                self.enabled = False
                self.owner_id = None
                self.keywords = {}
        else:
            self.keywords = {}

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self.enabled,
                    "owner_id": self.owner_id,
                    "keywords": self.keywords,
                }, f, indent=4, ensure_ascii=False)
            logs.info("Catchup 配置已保存")
            return True
        except Exception as e:
            logs.error(f"保存 Catchup 配置失败: {e}")
            return False

    def add_keyword(self, keyword: str, target_user_id: int, target_chat_id: int, rate_limit: int = DEFAULT_RATE_LIMIT) -> str:
        """添加或更新关键词配置"""
        # 参数验证
        if not keyword or not keyword.strip():
            return "关键词不能为空"
        if rate_limit < 0:
            return "频率限制必须大于等于0"

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


class TriggerLogManager:
    """触发记录管理类"""

    def __init__(self):
        self.logs: Dict[str, float] = {}  # keyword -> last_trigger_time
        self.load()

    def load(self) -> None:
        """从文件加载触发记录"""
        if trigger_log_file.exists():
            try:
                with open(trigger_log_file, "r", encoding="utf-8") as f:
                    self.logs = json.load(f)
                logs.info(f"触发记录已加载，共 {len(self.logs)} 条")
            except Exception as e:
                logs.error(f"加载触发记录失败: {e}")
                self.logs = {}
        else:
            self.logs = {}

    def save(self) -> None:
        """保存触发记录到文件"""
        try:
            with open(trigger_log_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=4)
        except Exception as e:
            logs.error(f"保存触发记录失败: {e}")

    def can_trigger(self, keyword: str, is_owner: bool) -> tuple[bool, Optional[int]]:
        """
        检查关键词是否可以触发
        返回: (是否可以触发, 需要等待的秒数)
        """
        # 主人无限制
        if is_owner:
            return True, None

        # 检查频率限制
        if keyword in self.logs:
            last_time = self.logs[keyword]
            elapsed = time.time() - last_time
            keyword_config = config_manager.get_keyword_config(keyword)
            if keyword_config:
                rate_limit = keyword_config.get("rate_limit_seconds", DEFAULT_RATE_LIMIT)
                if elapsed < rate_limit:
                    wait_time = int(rate_limit - elapsed)
                    return False, wait_time

        return True, None

    def record_trigger(self, keyword: str) -> None:
        """记录关键词触发时间"""
        self.logs[keyword] = time.time()
        self.save()

    def clear_keyword(self, keyword: str) -> None:
        """清除关键词的触发记录"""
        if keyword in self.logs:
            del self.logs[keyword]
            self.save()


# 全局实例
config_manager = CatchupConfigManager()
trigger_log = TriggerLogManager()


@listener(
    command="catchup",
    description="Catchup 插件管理",
    parameters="<on|off|set|delete|list|owner|status>",
    is_plugin=True,
)
async def catchup_command(message: Message):
    """处理 catchup 管理命令"""
    if not message.arguments:
        await show_help(message)
        return

    cmd = message.arguments.lower().split()[0]

    if cmd == "on":
        await enable_feature(message)
    elif cmd == "off":
        await disable_feature(message)
    elif cmd == "set":
        await set_keyword(message)
    elif cmd == "delete":
        await delete_keyword(message)
    elif cmd == "list":
        await list_keywords(message)
    elif cmd == "owner":
        await set_owner(message)
    elif cmd == "status":
        await show_status(message)
    else:
        await show_help(message)


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**Catchup 插件使用说明:**

**,catchup on** - 开启全局功能
**,catchup off** - 关闭全局功能
**,catchup set <关键词> <用户ID> <群组ID> [秒数]** - 添加/更新关键词配置
**,catchup delete <关键词>** - 删除关键词配置
**,catchup list** - 列出所有关键词配置
**,catchup owner <用户ID>** - 设置主人ID
**,catchup status** - 查看当前状态

**触发方式:**
- 在群组中发送 `/关键词` 触发对应配置的回复

**频率限制:**
- 主人触发：无限制
- 其他人触发：每个关键词独立计算频率限制"""
    await message.edit(help_text)


async def enable_feature(message: Message):
    """开启全局功能"""
    if not config_manager.keywords:
        await message.edit("❌ 请先添加关键词配置！\\n使用 `,catchup set <关键词> <用户ID> <群组ID>`")
        return
    config_manager.enabled = True
    config_manager.save()
    await message.edit(f"✅ Catchup 功能已开启\\n已配置 {len(config_manager.keywords)} 个关键词")


async def disable_feature(message: Message):
    """关闭全局功能"""
    config_manager.enabled = False
    config_manager.save()
    await message.edit("❌ Catchup 功能已关闭")


async def set_keyword(message: Message):
    """设置关键词配置"""
    params = message.arguments.split()
    if len(params) < 4:
        await message.edit("❌ 参数错误！\\n使用 `,catchup set <关键词> <用户ID> <群组ID> [秒数]`")
        return

    try:
        keyword = params[1]
        user_id = int(params[2])
        chat_id = int(params[3])
        rate_limit = int(params[4]) if len(params) > 4 else DEFAULT_RATE_LIMIT

        msg = config_manager.add_keyword(keyword, user_id, chat_id, rate_limit)
        await message.edit(f"✅ {msg}\\n用户ID: `{user_id}`\\n群组ID: `{chat_id}`\\n频率限制: {rate_limit}秒")
    except ValueError:
        await message.edit("❌ ID格式错误！请输入有效的数字ID")


async def delete_keyword(message: Message):
    """删除关键词配置"""
    params = message.arguments.split()
    if len(params) < 2:
        await message.edit("❌ 参数错误！\\n使用 `,catchup delete <关键词>`")
        return

    keyword = params[1]
    success, msg = config_manager.delete_keyword(keyword)
    if success:
        trigger_log.clear_keyword(keyword)
    await message.edit(f"{'✅' if success else '❌'} {msg}")


async def list_keywords(message: Message):
    """列出所有关键词配置"""
    result = config_manager.list_keywords()
    await message.edit(result)


async def set_owner(message: Message):
    """设置主人ID"""
    params = message.arguments.split()
    if len(params) < 2:
        await message.edit("❌ 参数错误！\\n使用 `,catchup owner <用户ID>`")
        return

    try:
        owner_id = int(params[1])
        config_manager.owner_id = owner_id
        config_manager.save()
        await message.edit(f"✅ 主人ID已设置为: `{owner_id}`")
    except ValueError:
        await message.edit("❌ ID格式错误！请输入有效的数字ID")


async def show_status(message: Message):
    """显示当前状态"""
    status = "✅ 已开启" if config_manager.enabled else "❌ 已关闭"
    owner_info = f"`{config_manager.owner_id}`" if config_manager.owner_id else "未设置"
    keywords_list = config_manager.list_keywords()

    status_text = f"""**Catchup 插件状态:**

功能状态: {status}
主人ID: {owner_info}

{keywords_list}

**频率限制:** 主人无限制，其他人按关键词独立计算

**触发方式:** `/关键词`"""
    await message.edit(status_text)
