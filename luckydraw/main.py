# -*- coding: utf-8 -*-
# 插件名称: luckydraw
# 生成时间: 2026-02-22 14:26:56

# -*- coding: utf-8 -*-
# 插件名称: luckydraw
# 生成时间: 2026-02-21 14:59:08

# -*- coding: utf-8 -*-
# 插件名称: luckydraw
# 生成时间: 2026-02-16 17:00

"""
自动抽奖插件 (LuckyDraw)
功能描述: 在指定群组中自动识别红包/抽奖活动并发送口令参与
文件名: luckydraw.py
"""

import asyncio
import json
import random
import re
from pathlib import Path
from typing import Dict, Optional, Set, List

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message, Client
from pagermaid.utils import logs


# 配置文件路径
plugin_dir = Path(__file__).parent
config_file = plugin_dir / "luckydraw_config.json"

# 脚本检测关键词（出现这些词则不触发）
SCRIPT_DETECTION_KEYWORDS = [
    "脚本",
    "检测",
    "不能领",
    "禁止脚本",
    "防脚本",
    "robot",
    "bot",
    "auto",
    "脚本检测",
    "自动领",
    "作弊",
    "挂",
]
# 自排除关键词（消息包含这些词时不参与抽奖，避免尴尬）
SELF_EXCLUSION_KEYWORDS = [
    "我是G",
    "我是g",
    "自ban",
    "自ban人",
    "我是自ban人",
    "我是自ban",
    "我是狗",
    "我是畜生",
    "我是猪",
    "我是傻",
    "我是sb",
    "我是SB",
    "我是傻逼",
    "我是蠢",
    "我是废物",
    "我是垃圾",
]

# 抢红包随机延迟范围（秒）- 默认值
DEFAULT_MIN_DELAY = 2.0
DEFAULT_MAX_DELAY = 5.0

# 等待其他用户回复的时间范围（秒）
WAIT_MIN_DELAY = 3.0
WAIT_MAX_DELAY = 8.0

# 需要等待的其他用户回复数量（随机1-2人）
WAIT_USER_COUNT_MIN = 1
WAIT_USER_COUNT_MAX = 2

# 群组默认延时配置
DEFAULT_DELAY = 2.0  # 秒

# 默认抽奖机器人ID白名单（首次使用时写入配置文件）
DEFAULT_BOT_WHITELIST: Set[int] = {
    6461022460,  # 抽奖机器人
}


class LuckyDrawConfig:
    """自动抽奖配置管理类"""

    def __init__(self):
        self.enabled_chats: Set[int] = set()  # 启用功能的群组ID集合
        self.test_chats: Set[int] = set()  # 测试群组（输出详细日志）
        self.sent_keywords: Dict[str, list] = {}  # 已发送的口令 {群组ID: [口令1, 口令2, ...]}
        self.sent_messages: Set[str] = set()  # 已处理的消息ID {群组ID_消息ID}
        self.chat_delays: Dict[str, dict] = {}  # 群组延时配置 {群组ID: {"min": min_delay, "max": max_delay}}
        self.bot_whitelist: Set[int] = set()  # 抽奖机器人白名单
        self.stats: Dict[str, int] = {
            "total_detected": 0,  # 检测到的抽奖次数
            "total_joined": 0,    # 成功参与的次数
            "total_blocked": 0,   # 被安全检测拦截的次数
        }
        self.load()

    def load(self) -> None:
        """从文件加载配置"""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.enabled_chats = set(data.get("enabled_chats", []))
                    self.test_chats = set(data.get("test_chats", []))
                    self.sent_keywords = data.get("sent_keywords", {})
                    self.sent_messages = set(data.get("sent_messages", []))
                    self.chat_delays = data.get("chat_delays", {})
                    self.bot_whitelist = set(data.get("bot_whitelist", DEFAULT_BOT_WHITELIST))
                    self.stats = data.get("stats", self.stats)
            except Exception as e:
                logs.error(f"[LuckyDraw] 加载配置失败: {e}")
                self.enabled_chats = set()
                self.test_chats = set()
                self.sent_keywords = {}
                self.sent_messages = {}
                self.chat_delays = {}
                self.bot_whitelist = set(DEFAULT_BOT_WHITELIST)
                self.stats = {"total_detected": 0, "total_joined": 0, "total_blocked": 0}
        else:
            # 首次使用，使用默认白名单
            self.bot_whitelist = set(DEFAULT_BOT_WHITELIST)
            self.save()

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "enabled_chats": list(self.enabled_chats),
                        "test_chats": list(self.test_chats),
                        "sent_keywords": self.sent_keywords,
                        "sent_messages": list(self.sent_messages),
                        "chat_delays": self.chat_delays,
                        "bot_whitelist": list(self.bot_whitelist),
                        "stats": self.stats,
                    },
                    f,
                    indent=4,
                    ensure_ascii=False,
                )
            return True
        except Exception as e:
            logs.error(f"[LuckyDraw] 保存配置失败: {e}")
            return False

    def add_chat(self, chat_id: int) -> str:
        """添加启用功能的群组"""
        if chat_id in self.enabled_chats:
            return f"群组 `{chat_id}` 已在启用列表中"
        self.enabled_chats.add(chat_id)
        self.save()
        return f"已启用群组 `{chat_id}` 的自动抽奖功能"

    def remove_chat(self, chat_id: int) -> str:
        """移除启用功能的群组"""
        if chat_id not in self.enabled_chats:
            return f"群组 `{chat_id}` 未启用此功能"
        self.enabled_chats.remove(chat_id)
        self.save()
        return f"已禁用群组 `{chat_id}` 的自动抽奖功能"

    def is_enabled(self, chat_id: int) -> bool:
        """检查群组是否启用功能"""
        return chat_id in self.enabled_chats

    def is_test_chat(self, chat_id: int) -> bool:
        """检查是否为测试群组"""
        return chat_id in self.test_chats

    def add_test_chat(self, chat_id: int) -> str:
        """添加测试群组"""
        if chat_id in self.test_chats:
            return f"群组 `{chat_id}` 已在测试群组列表中"
        self.test_chats.add(chat_id)
        self.save()
        return f"已添加群组 `{chat_id}` 到测试群组"

    def remove_test_chat(self, chat_id: int) -> str:
        """移除测试群组"""
        if chat_id not in self.test_chats:
            return f"群组 `{chat_id}` 不在测试群组列表中"
        self.test_chats.remove(chat_id)
        self.save()
        return f"已移除群组 `{chat_id}` 从测试群组"

    def get_chat_delay(self, chat_id: int) -> tuple[float, float]:
        """获取群组的延时配置 (min_delay, max_delay)"""
        key = str(chat_id)
        if key in self.chat_delays:
            return (
                self.chat_delays[key].get("min", DEFAULT_DELAY),
                self.chat_delays[key].get("max", DEFAULT_DELAY)
            )
        return (DEFAULT_DELAY, DEFAULT_DELAY)

    def set_chat_delay(self, chat_id: int, min_delay: float, max_delay: float = None) -> str:
        """设置群组的延时配置"""
        key = str(chat_id)
        if max_delay is None:
            max_delay = min_delay + 3.0  # 如果只设置一个值，范围为 [delay, delay+3]
        
        # 限制范围
        min_delay = max(0.1, min_delay)
        max_delay = max(min_delay, max_delay)
        
        self.chat_delays[key] = {"min": min_delay, "max": max_delay}
        self.save()
        return f"已设置群组 `{chat_id}` 延时为 {min_delay}~{max_delay} 秒"

    def remove_chat_delay(self, chat_id: int) -> str:
        """移除群组的自定义延时配置，恢复默认"""
        key = str(chat_id)
        if key in self.chat_delays:
            del self.chat_delays[key]
            self.save()
            return f"已移除群组 `{chat_id}` 的自定义延时，恢复默认 {DEFAULT_DELAY} 秒"
        return f"群组 `{chat_id}` 未设置自定义延时"

    def list_chat_delays(self) -> str:
        """列出所有群组的延时配置"""
        if not self.chat_delays:
            return "暂无自定义延时配置，默认延时 2 秒"
        
        output = "**群组延时配置列表：**\n\n"
        for chat_id, delay in self.chat_delays.items():
            output += f"- 群组 `{chat_id}`: {delay['min']}~{delay['max']} 秒\n"
        return output

    def has_sent_keyword(self, chat_id: int, keyword: str) -> bool:
        """检查口令是否已发送"""
        key = str(chat_id)
        if key not in self.sent_keywords:
            return False
        return keyword in self.sent_keywords[key]

    def mark_keyword_sent(self, chat_id: int, keyword: str) -> None:
        """标记口令已发送"""
        key = str(chat_id)
        if key not in self.sent_keywords:
            self.sent_keywords[key] = []
        if keyword not in self.sent_keywords[key]:
            self.sent_keywords[key].append(keyword)
            self.save()

    def is_message_processed(self, chat_id: int, message_id: int) -> bool:
        """检查消息是否已处理"""
        key = f"{chat_id}_{message_id}"
        return key in self.sent_messages

    def mark_message_processed(self, chat_id: int, message_id: int) -> None:
        """标记消息已处理"""
        key = f"{chat_id}_{message_id}"
        self.sent_messages.add(key)
        # 保持集合不要太大，限制1000条
        if len(self.sent_messages) > 1000:
            self.sent_messages = set(list(self.sent_messages)[-500:])
        self.save()

    def clear_sent_keywords(self, chat_id: int = None) -> str:
        """清除已发送口令记录"""
        if chat_id is None:
            self.sent_keywords = {}
            self.save()
            return "已清除所有群组的口令记录"
        key = str(chat_id)
        if key in self.sent_keywords:
            del self.sent_keywords[key]
            self.save()
        return f"已清除群组 `{chat_id}` 的口令记录"

    def list_chats(self) -> str:
        """列出所有启用的群组"""
        if not self.enabled_chats:
            return "当前没有启用任何群组"

        output = "**已启用的群组列表：**\n\n"
        for chat_id in self.enabled_chats:
            output += f"- 群组ID: `{chat_id}`\n"
        return output

    # ========== 机器人白名单管理 ==========

    def add_bot(self, bot_id: int) -> str:
        """添加机器人到白名单"""
        if bot_id in self.bot_whitelist:
            return f"机器人 `{bot_id}` 已在白名单中"
        self.bot_whitelist.add(bot_id)
        self.save()
        return f"已添加机器人 `{bot_id}` 到白名单"

    def remove_bot(self, bot_id: int) -> str:
        """从白名单移除机器人"""
        if bot_id not in self.bot_whitelist:
            return f"机器人 `{bot_id}` 不在白名单中"
        self.bot_whitelist.remove(bot_id)
        self.save()
        return f"已从白名单移除机器人 `{bot_id}`"

    def is_bot_allowed(self, bot_id: int) -> bool:
        """检查机器人是否在白名单中"""
        return bot_id in self.bot_whitelist

    def list_bots(self) -> str:
        """列出所有白名单机器人"""
        if not self.bot_whitelist:
            return "当前白名单为空，所有抽奖消息都会被忽略"

        output = "**机器人白名单：**\n\n"
        for bot_id in self.bot_whitelist:
            output += f"- 机器人ID: `{bot_id}`\n"
        output += "\n💡 只有这些机器人发布的抽奖才会参与"
        return output

    def get_stats(self) -> str:
        """获取统计信息"""
        output = "**统计信息：**\n\n"
        output += f"- 启用群组数: `{len(self.enabled_chats)}`\n"
        output += f"- 检测到的抽奖: `{self.stats['total_detected']}` 次\n"
        output += f"- 成功参与: `{self.stats['total_joined']}` 次\n"
        output += f"- 安全拦截: `{self.stats['total_blocked']}` 次\n"
        return output

    def increment_detected(self) -> None:
        """增加检测计数"""
        self.stats["total_detected"] += 1
        self.save()

    def increment_joined(self) -> None:
        """增加参与计数"""
        self.stats["total_joined"] += 1
        self.save()

    def increment_blocked(self) -> None:
        """增加拦截计数"""
        self.stats["total_blocked"] += 1
        self.save()


# 全局配置实例
config = LuckyDrawConfig()


# 待发送口令队列 {chat_id: {message_id: {"keyword": keyword, "type": keyword_type, "wait_count": int, "current_count": int}}}
pending_draws: Dict[str, dict] = {}


def check_red_packet_finished(text: str, chat_id: int, is_test: bool) -> bool:
    """
    检查红包是否已领完，如果是则清除该口令记录
    返回: 是否处理了这个消息
    """
    # 红包已领完的模式
    finished_patterns = [
        r"已领完",
        r"已领取完毕",
        r"红包已被领完",
        r"领取详情:",
    ]
    
    for pattern in finished_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # 提取红包ID
            red_packet_id_match = re.search(r"(?:红包ID|ID|ID:)[^\d]*(\w+)", text, re.IGNORECASE)
            red_packet_id = red_packet_id_match.group(1) if red_packet_id_match else None
            
            # 提取红包口令（如果有）
            result = KeywordExtractor.extract(text)
            if result:
                keyword, _ = result
                # 清除这个口令的记录
                if config.has_sent_keyword(chat_id, keyword):
                    # 重新添加已发送的关键字记录，这样下次相同口令就能发送了
                    key = str(chat_id)
                    if key in config.sent_keywords and keyword in config.sent_keywords[key]:
                        config.sent_keywords[key].remove(keyword)
                        config.save()
                        logs.info(f"[LuckyDraw] 红包已领完，清除口令记录: {keyword}")
                        if is_test:
                            return True
                    return True
            
            # 如果没有提取到口令，清除最近一个口令（保守处理）
            key = str(chat_id)
            if key in config.sent_keywords and config.sent_keywords[key]:
                removed_keyword = config.sent_keywords[key].pop()
                config.save()
                logs.info(f"[LuckyDraw] 红包已领完，清除最近口令记录: {removed_keyword}")
                if is_test:
                    logs.info(f"[LuckyDraw] 检测到红包已领完，已清除最近口令记录")
            
            return True
    
    return False


class KeywordExtractor:
    """口令提取器"""

    # 口令提取规则列表（按优先级排序）
    PATTERNS = [
        # 格式1: 【密令抽奖】...领取密令: xxx
        (r"领取密令[：:]\s*(.+?)(?:\n|$)", "密令抽奖"),
        # 格式2: 参与关键词：「xxx」 或 参与关键词：xxx
        (r"参与关键词[：:]\s*[「「\"]?(.+?)[」」\"]?(?:\n|$)", "参与关键词"),
        # 格式3: 发送 xxx 进行领取（口令在中间，优先级最高）
        (r"发送\s+(.+?)\s+进行领取", "红包口令-进行领取"),
        # 格式3.5: 发送 xxx 领取 / 发送下方口令领取：xxx（口令在领取之后）
        (r"发送.+(?:领取)[：:]?\s*(.+?)(?:\n|$)", "红包口令"),
        # 格式4: 输入口令: xxx / 口令: xxx
        (r"(?:输入)?口令[：:]\s*(.+?)(?:\n|$)", "口令"),
        # 格式5: 回复 xxx 领取 / 回复 xxx 参与
        (r"回复\s+(.+?)\s+(?:领取|参与)", "回复口令"),
        # 格式6: 【拼手气红包】xxx (红包ID)
        (r"【拼手气红包】\s*([a-zA-Z0-9\-]+)(?:\s|$)", "拼手气红包"),
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[tuple[str, str]]:
        """
        从消息文本中提取口令
        返回: (口令内容, 口令类型) 或 None
        """
        if not text:
            return None

        for pattern, keyword_type in cls.PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                keyword = match.group(1).strip()
                # 清理口令中的引号和多余空格
                keyword = keyword.strip('"\'「」【】')
                if keyword and len(keyword) > 0:
                    return (keyword, keyword_type)

        return None


class SecurityChecker:
    """安全检测器"""

    @classmethod
    def is_safe(cls, text: str, keyword: str) -> tuple[bool, str]:
        """
        检查消息和口令是否安全
        返回: (是否安全, 原因)
        """
        check_text = f"{text} {keyword}".lower()

        for danger_word in SCRIPT_DETECTION_KEYWORDS:
            if danger_word.lower() in check_text:
                return False, f"检测到敏感词: {danger_word}"

        return True, "安全"


# ==================== 生命周期钩子 ====================


@Hook.on_startup()
async def luckydraw_startup():
    """插件启动时执行"""
    logs.info("[LuckyDraw] 自动抽奖插件已加载")


@Hook.on_shutdown()
async def luckydraw_shutdown():
    """插件关闭时执行"""
    logs.info("[LuckyDraw] 自动抽奖插件已卸载")


# ==================== 管理命令 ====================


@listener(
    command="ldraw",
    description="自动抽奖管理命令",
    parameters="<on|off|set|list|stats|help>",
    is_plugin=True,
)
async def ldraw_command(message: Message):
    """处理 LuckyDraw 管理命令"""
    # 获取命令参数
    text = message.arguments or ""

    # 如果没有参数，显示帮助
    if not text or text.strip() == "":
        await show_help(message)
        return

    cmd = text.lower().split()[0]

    if cmd == "on":
        await enable_chat(message)
    elif cmd == "off":
        await disable_chat(message)
    elif cmd == "set":
        await set_chat(message)
    elif cmd == "delayset":
        await set_delay_by_chat_id(message)
    elif cmd == "delayoff":
        await remove_delay_by_chat_id(message)
    elif cmd == "delay":
        await set_delay(message)
    elif cmd == "listdelay":
        await list_delays(message)
    elif cmd == "list":
        await list_chats(message)
    elif cmd == "stats":
        await show_stats(message)
    elif cmd == "help":
        await show_help(message)
    elif cmd == "test":
        await test_extract(message)
    elif cmd == "clear":
        await clear_keywords(message)
    elif cmd == "bot":
        await manage_bot(message)
    else:
        await show_help(message)


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**自动抽奖插件使用说明**

**功能描述：**
在启用功能的群组中，自动识别抽奖活动消息并发送口令参与。
每个口令只发送一次，不会重复发送。

**⚠️ 重要：机器人白名单机制**
只响应白名单中机器人发布的抽奖消息，忽略其他用户发布的抽奖。

**管理命令：**

`,ldraw bot list` - 查看白名单机器人
`,ldraw bot add <ID>` - 添加机器人到白名单
`,ldraw bot del <ID>` - 从白名单移除机器人

`,ldraw set <群组ID>` - 启用指定群组
`,ldraw set <群组ID> off` - 禁用指定群组
`,ldraw set <群组ID> test` - 添加到测试群组（输出详细日志）

`,ldraw delay <延时>` - 设置当前群组延时
`,ldraw delay <最小> <最大>` - 设置精确延时范围
`,ldraw delayset <群组ID> <最小延时> [最大延时]` - 设置指定群组延时
`,ldraw delayoff <群组ID>` - 移除指定群组延时
`,ldraw listdelay` - 查看所有群组延时配置
`,ldraw list` - 查看所有启用的群组
`,ldraw stats` - 查看统计信息
`,ldraw test <文本>` - 测试口令提取功能
`,ldraw clear` - 清除已发送口令记录

**支持的口令格式：**
- `领取密令: xxx` → 发送 xxx
- `参与关键词：「xxx」` → 发送 xxx
- `口令: xxx` → 发送 xxx

**注意事项：**
- 为避免被检测，插件会随机延迟后发送口令
- 测试群组会输出详细日志方便调试"""

    await message.edit(help_text)


async def enable_chat(message: Message):
    """在当前群组启用功能"""
    if not message.chat or message.chat.id > 0:
        await message.edit("此命令只能在群组中使用")
        await asyncio.sleep(3)
        await message.delete()
        return

    chat_id = message.chat.id
    result = config.add_chat(chat_id)
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


async def disable_chat(message: Message):
    """在当前群组禁用功能"""
    if not message.chat or message.chat.id > 0:
        await message.edit("此命令只能在群组中使用")
        await asyncio.sleep(3)
        await message.delete()
        return

    chat_id = message.chat.id
    result = config.remove_chat(chat_id)
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


async def set_chat(message: Message):
    """手动添加/移除群组ID"""
    params = message.arguments.split()
    if len(params) < 2:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法: \n"
            "`,ldraw set <群组ID>` - 启用指定群组\n"
            "`,ldraw set <群组ID> off` - 禁用指定群组\n"
            "`,ldraw set <群组ID> test` - 添加到测试群组\n"
            "`,ldraw set <群组ID> test off` - 从测试群组移除\n\n"
            "示例: `,ldraw set -1001234567890`"
        )
        await asyncio.sleep(8)
        await message.delete()
        return

    try:
        chat_id = int(params[1])
        
        # 判断操作类型
        if len(params) >= 3:
            action = params[2].lower()
            if action == "off":
                result = config.remove_chat(chat_id)
            elif action == "test":
                if len(params) >= 4 and params[3].lower() == "off":
                    result = config.remove_test_chat(chat_id)
                else:
                    result = config.add_test_chat(chat_id)
            else:
                result = config.add_chat(chat_id)
        else:
            result = config.add_chat(chat_id)
        
        await message.edit(f"**{result}**")
        await asyncio.sleep(3)
        await message.delete()
    except ValueError:
        await message.edit("**群组ID格式错误！**\n\n请输入有效的数字ID")
        await asyncio.sleep(3)
        await message.delete()


async def list_chats(message: Message):
    """查看所有启用的群组"""
    result = config.list_chats()
    await message.edit(result)
    await asyncio.sleep(5)
    await message.delete()


async def show_stats(message: Message):
    """查看统计信息"""
    result = config.get_stats()
    await message.edit(result)
    await asyncio.sleep(5)
    await message.delete()


async def test_extract(message: Message):
    """测试口令提取功能"""
    params = message.arguments.split(maxsplit=1)
    if len(params) < 2:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法: `,luckydraw test <文本>`\n\n"
            "示例: `,luckydraw test 领取密令: 新年快乐`"
        )
        await asyncio.sleep(5)
        await message.delete()
        return

    test_text = params[1]
    result = KeywordExtractor.extract(test_text)

    if result:
        keyword, keyword_type = result
        is_safe, reason = SecurityChecker.is_safe(test_text, keyword)
        status = "安全" if is_safe else f"不安全 ({reason})"

        output = (
            f"**口令提取测试结果：**\n\n"
            f"- 口令类型: `{keyword_type}`\n"
            f"- 提取结果: `{keyword}`\n"
            f"- 安全检测: {status}"
        )
    else:
        output = "**未能从文本中提取到口令**\n\n请检查文本格式是否符合支持的口令格式。"

    await message.edit(output)
    await asyncio.sleep(5)
    await message.delete()


async def clear_keywords(message: Message):
    """清除已发送口令记录"""
    params = message.arguments.split()
    if len(params) >= 2:
        try:
            chat_id = int(params[1])
            result = config.clear_sent_keywords(chat_id)
        except ValueError:
            await message.edit("**群组ID格式错误！**\n\n请输入有效的数字ID")
            await asyncio.sleep(3)
            await message.delete()
            return
    else:
        result = config.clear_sent_keywords()
    
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


async def manage_bot(message: Message):
    """管理机器人白名单"""
    params = message.arguments.split()
    
    if len(params) < 2:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法:\n"
            "`,ldraw bot list` - 查看白名单机器人列表\n"
            "`,ldraw bot add <机器人ID>` - 添加机器人到白名单\n"
            "`,ldraw bot del <机器人ID>` - 从白名单移除机器人\n\n"
            "示例:\n"
            "`,ldraw bot add 6461022460`\n"
            "`,ldraw bot del 6461022460`"
        )
        await asyncio.sleep(8)
        await message.delete()
        return
    
    action = params[1].lower()
    
    if action == "list":
        result = config.list_bots()
        await message.edit(result)
        await asyncio.sleep(5)
        await message.delete()
        return
    
    if len(params) < 3:
        await message.edit("**参数错误！**\n\n需要指定机器人ID")
        await asyncio.sleep(3)
        await message.delete()
        return
    
    try:
        bot_id = int(params[2])
    except ValueError:
        await message.edit("**机器人ID格式错误！**\n\n请输入有效的数字ID")
        await asyncio.sleep(3)
        await message.delete()
        return
    
    if action == "add":
        result = config.add_bot(bot_id)
    elif action in ["del", "remove", "delete"]:
        result = config.remove_bot(bot_id)
    else:
        await message.edit("**未知操作！**\n\n支持的操作: add, del")
        await asyncio.sleep(3)
        await message.delete()
        return
    
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


async def set_delay(message: Message):
    """设置群组的延时"""
    params = message.arguments.split()
    
    if len(params) < 2:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法:\n"
            "`,ldraw delay <延时秒数>` - 设置当前群组延时（最小~最大范围自动+3秒）\n"
            "`,ldraw delay <最小延时> <最大延时>` - 设置精确范围\n"
            "`,ldraw delay <群组ID> <延时>` - 设置指定群组延时\n"
            "`,ldraw delay off` - 移除当前群组的自定义延时\n\n"
            "示例:\n"
            "`,ldraw delay 0.5` - 设置延时 0.5~3.5 秒\n"
            "`,ldraw delay 2 5` - 设置延时 2~5 秒\n"
            "`,ldraw delay -1001234567890 3` - 设置指定群组延时 3~6 秒"
        )
        await asyncio.sleep(10)
        await message.delete()
        return
    
    # 判断是设置还是移除
    if params[1].lower() == "off":
        # 移除当前群组的延时配置
        if not message.chat or message.chat.id > 0:
            await message.edit("此命令只能在群组中使用")
            await asyncio.sleep(3)
            await message.delete()
            return
        chat_id = message.chat.id
        result = config.remove_chat_delay(chat_id)
        await message.edit(f"**{result}**")
        await asyncio.sleep(3)
        await message.delete()
        return
    
    # 解析参数
    try:
        # 判断第一个参数是否是群组ID（负数）
        if params[1].startswith("-"):
            if len(params) < 3:
                await message.edit("**参数错误！**\n\n需要指定延时值")
                await asyncio.sleep(3)
                await message.delete()
                return
            chat_id = int(params[1])
            min_delay = float(params[2])
            max_delay = float(params[3]) if len(params) > 3 else None
        else:
            # 当前群组
            if not message.chat or message.chat.id > 0:
                await message.edit("此命令只能在群组中使用")
                await asyncio.sleep(3)
                await message.delete()
                return
            chat_id = message.chat.id
            min_delay = float(params[1])
            max_delay = float(params[2]) if len(params) > 2 else None
        
        result = config.set_chat_delay(chat_id, min_delay, max_delay)
        await message.edit(f"**{result}**")
        await asyncio.sleep(3)
        await message.delete()
    except ValueError:
        await message.edit("**参数错误！**\n\n请输入有效的数字")
        await asyncio.sleep(3)
        await message.delete()


async def list_delays(message: Message):
    """列出所有群组的延时配置"""
    result = config.list_chat_delays()
    await message.edit(result)
    await asyncio.sleep(5)
    await message.delete()


async def set_delay_by_chat_id(message: Message) -> None:
    """通过群组ID设置延时"""
    params = message.arguments.split()

    if len(params) < 3:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法:\n"
            "`,ldraw delayset <群组ID> <最小延时> [最大延时]`\n\n"
            "示例:\n"
            "`,ldraw delayset -1001234567890 0.5`\n"
            "`,ldraw delayset -1001234567890 2 5`"
        )
        await asyncio.sleep(8)
        await message.delete()
        return

    try:
        chat_id = int(params[1])
    except ValueError:
        await message.edit("**群组ID格式错误！**\n\n请输入有效的数字ID")
        await asyncio.sleep(3)
        await message.delete()
        return

    if chat_id >= 0:
        await message.edit("**群组ID错误！**\n\n群组ID必须为负数")
        await asyncio.sleep(3)
        await message.delete()
        return

    try:
        min_delay = float(params[2])
    except ValueError:
        await message.edit("**参数错误！**\n\n最小延时必须为数字")
        await asyncio.sleep(3)
        await message.delete()
        return

    max_delay: Optional[float] = None
    if len(params) >= 4:
        try:
            max_delay = float(params[3])
        except ValueError:
            await message.edit("**参数错误！**\n\n最大延时必须为数字")
            await asyncio.sleep(3)
            await message.delete()
            return

    if min_delay < 0.1:
        await message.edit("**参数错误！**\n\n最小延时不能小于 0.1 秒")
        await asyncio.sleep(3)
        await message.delete()
        return

    if max_delay is not None and max_delay < min_delay:
        await message.edit("**参数错误！**\n\n最大延时必须大于等于最小延时")
        await asyncio.sleep(3)
        await message.delete()
        return

    result = config.set_chat_delay(chat_id, min_delay, max_delay)
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


async def remove_delay_by_chat_id(message: Message) -> None:
    """通过群组ID移除延时"""
    params = message.arguments.split()

    if len(params) < 2:
        await message.edit(
            "**参数错误！**\n\n"
            "使用方法:\n"
            "`,ldraw delayoff <群组ID>`\n\n"
            "示例:\n"
            "`,ldraw delayoff -1001234567890`"
        )
        await asyncio.sleep(6)
        await message.delete()
        return

    try:
        chat_id = int(params[1])
    except ValueError:
        await message.edit("**群组ID格式错误！**\n\n请输入有效的数字ID")
        await asyncio.sleep(3)
        await message.delete()
        return

    if chat_id >= 0:
        await message.edit("**群组ID错误！**\n\n群组ID必须为负数")
        await asyncio.sleep(3)
        await message.delete()
        return

    result = config.remove_chat_delay(chat_id)
    await message.edit(f"**{result}**")
    await asyncio.sleep(3)
    await message.delete()


# ==================== 自动抽奖监听器 ====================


@listener(is_plugin=True, incoming=True, outgoing=False, ignore_edited=False)
async def luckydraw_handler(message: Message, bot: Client):
    """
    自动抽奖消息处理器

    检测传入的消息，识别红包/抽奖活动并自动发送口令参与
    """
    # 检查是否在群组中
    if not message.chat:
        return

    chat_id = message.chat.id
    is_test = config.is_test_chat(chat_id)

    # 检查是否在启用的群组中
    if not config.is_enabled(chat_id):
        if is_test:
            logs.info(f"[LuckyDraw] 群组 {chat_id} 未启用，跳过")
        return

    # 打印所有消息属性用于调试
    if is_test:
        logs.info(f"[LuckyDraw] ===== 收到消息 =====")
        logs.info(f"[LuckyDraw] message.text: {message.text}")
        logs.info(f"[LuckyDraw] message.caption: {getattr(message, 'caption', 'N/A')}")
        logs.info(f"[LuckyDraw] message.raw_text: {getattr(message, 'raw_text', 'N/A')}")
        logs.info(f"[LuckyDraw] message.forward_from: {message.forward_from}")
        logs.info(f"[LuckyDraw] message.forward_from_chat: {message.forward_from_chat}")
        logs.info(f"[LuckyDraw] message.media: {getattr(message, 'media', 'N/A')}")
        logs.info(f"[LuckyDraw] message.chat.id: {chat_id}")
        logs.info(f"[LuckyDraw] message.sender_id: {getattr(message, 'sender_id', 'N/A')}")

    # ========== 机器人ID检测 ==========
    # 只处理白名单中机器人发布的抽奖消息
    
    # 获取发送者ID（参考 userinfo 插件）
    sender_id = None
    
    # 判断是否是频道/群组发言（皮套）
    if hasattr(message, 'sender_chat') and message.sender_chat:
        sender_id = message.sender_chat.id
    # 普通用户/机器人发言
    elif hasattr(message, 'from_user') and message.from_user:
        sender_id = message.from_user.id
    
    # 检查是否是转发的消息（转发消息需要检查原始发送者）
    forward_from = getattr(message, "forward_from", None)
    forward_from_chat = getattr(message, "forward_from_chat", None)
    
    # 确定实际的发送者ID
    actual_sender_id = sender_id
    if forward_from:
        # 转发自用户
        actual_sender_id = getattr(forward_from, "id", sender_id)
    elif forward_from_chat:
        # 转发自频道/群组
        actual_sender_id = getattr(forward_from_chat, "id", sender_id)
    
    if is_test:
        logs.info(f"[LuckyDraw] sender_chat: {getattr(message, 'sender_chat', None)}")
        logs.info(f"[LuckyDraw] from_user: {getattr(message, 'from_user', None)}")
        logs.info(f"[LuckyDraw] sender_id: {sender_id}, actual_sender_id: {actual_sender_id}")
    
    # 检查发送者是否在白名单中
    if not config.is_bot_allowed(actual_sender_id):
        if is_test:
            logs.info(f"[LuckyDraw] 发送者 {actual_sender_id} 不在白名单中，跳过")
        return
    
    if is_test:
        logs.info(f"[LuckyDraw] 发送者 {actual_sender_id} 在白名单中，继续处理")

    # 尝试获取消息文本（支持转发消息和媒体消息）
    text = message.text
    if not text:
        # 尝试获取 media 的 caption
        text = getattr(message, 'caption', None)
    if not text:
        text = getattr(message, 'raw_text', None)
    
    if is_test:
        logs.info(f"[LuckyDraw] 最终获取的text: {text[:100] if text else 'None'}...")

    # 检查是否有消息文本
    if not text:
        if is_test:
            logs.info(f"[LuckyDraw] 无法获取消息文本，跳过")
        return


    # 检查消息是否包含自排除关键词，如果是则不参与抽奖
    text_lower = text.lower()
    for exclude_keyword in SELF_EXCLUSION_KEYWORDS:
        if exclude_keyword in text_lower:
            if is_test:
                logs.info(f"[LuckyDraw] 检测到自排除关键词 '{exclude_keyword}'，跳过")
            return

    # 检查是否红包已领完，如果是则清除该口令记录
    if check_red_packet_finished(text, chat_id, is_test):
        return

    # 检查消息是否已处理（去重）
    message_id = message.id
    if config.is_message_processed(chat_id, message_id):
        if is_test:
            logs.info(f"[LuckyDraw] 消息已处理过，跳过 | message_id: {message_id}")
        return
    config.mark_message_processed(chat_id, message_id)

    # 提取口令
    result = KeywordExtractor.extract(text)
    if not result:
        if is_test:
            logs.info(f"[LuckyDraw] 未匹配到口令格式")
        return

    keyword, keyword_type = result
    
    # 检查口令是否已发送过
    if config.has_sent_keyword(chat_id, keyword):
        if is_test:
            logs.info(f"[LuckyDraw] 口令已发送过，跳过 | 口令: {keyword}")
        return

    if is_test:
        logs.info(f"[LuckyDraw] 检测到口令 | 类型: {keyword_type} | 口令: {keyword}")

    # 增加检测计数
    config.increment_detected()

    # 安全检测
    is_safe, reason = SecurityChecker.is_safe(text, keyword)
    if not is_safe:
        config.increment_blocked()
        logs.warning(f"[LuckyDraw] 拦截可疑抽奖: {reason}, 口令: {keyword}")
        if is_test:
            try:
                await bot.send_message(chat_id, f"⚠️ 安全拦截: {reason}")
            except Exception:
                pass
        return

    # 直接延时发送（不再等待其他用户回复）

    # 检查是否已有相同口令在队列中，避免重复加入
    for existing_key, existing_pending in pending_draws.items():
        if existing_pending.get("keyword") == keyword and existing_pending.get("chat_id") == chat_id:
            if is_test:
                logs.info(f"[LuckyDraw] 相同口令已在队列中，跳过 | 口令: {keyword}")
            return
    
    # 将口令加入待发送队列
    queue_key = f"{chat_id}_{message_id}"
    pending_draws[queue_key] = {
        "keyword": keyword,
        "keyword_type": keyword_type,
        "chat_id": chat_id,
        "wait_count": 1,
        "current_count": 0,
    }
    
    # 获取群组的延时配置
    min_delay, max_delay = config.get_chat_delay(chat_id)
    delay = random.uniform(min_delay, max_delay)
    
    # 延时后发送
    await asyncio.sleep(delay)
    
    # 检查是否已发送过（避免重复发送）
    if config.has_sent_keyword(chat_id, keyword):
        if is_test:
            logs.info(f"[LuckyDraw] 口令已发送过，跳过 | 口令: {keyword}")
    else:
        # 发送口令
        try:
            await bot.send_message(chat_id, keyword)
            config.mark_keyword_sent(chat_id, keyword)
            config.increment_joined()
            
            log_msg = (
                f"[LuckyDraw] 成功参与抽奖 | "
                f"群组: {chat_id} | "
                f"类型: {keyword_type} | "
                f"口令: {keyword} | "
                f"延迟: {delay:.2f}s"
            )
            logs.info(log_msg)
            
            if is_test:
                try:
                    await bot.send_message(chat_id, f"✅ 已发送口令: {keyword}")
                except Exception:
                    pass
        except Exception as e:
            logs.error(f"[LuckyDraw] 发送口令失败: {e}")
    
    # 从队列中移除
    if queue_key in pending_draws:
        del pending_draws[queue_key]


# ==================== 监听其他用户回复 ====================


@listener(is_plugin=True, incoming=True, outgoing=False, ignore_edited=False)
async def luckydraw_reply_handler(message: Message, bot: Client):
    """
    监听其他用户回复，触发口令发送
    """
    # 检查是否在群组中
    if not message.chat:
        return

    chat_id = message.chat.id
    is_test = config.is_test_chat(chat_id)

    # 检查是否在启用的群组中
    if not config.is_enabled(chat_id):
        return

    # 检查消息是否已处理（去重）- 避免重复计数
    message_id = message.id
    if config.is_message_processed(chat_id, message_id):
        return
    
    # 检查是否是机器人自己的消息
    sender = getattr(message, "sender_id", None)
    bot_id = (await bot.get_me()).id
    if sender == bot_id:
        return

    # 检查是否有待发送的口令
    pending_keys = [k for k in pending_draws.keys() if k.startswith(f"{chat_id}_")]
    if not pending_keys:
        return

    # 遍历待发送队列，检查是否有匹配的
    for queue_key in list(pending_draws.keys()):
        if not queue_key.startswith(f"{chat_id}_"):
            continue
        
        pending = pending_draws[queue_key]
        keyword = pending.get("keyword")
        
        # 检查口令是否已发送过，避免重复发送
        if config.has_sent_keyword(chat_id, keyword):
            if is_test:
                logs.info(f"[LuckyDraw] 口令已发送过，跳过 | 口令: {keyword}")
            # 从队列中移除
            del pending_draws[queue_key]
            continue
        
        # 增加当前回复计数
        
        if is_test:
            logs.info(f"[LuckyDraw] 用户回复，当前: {pending['current_count']}/{pending['wait_count']}")
        
        # 检查是否满足发送条件
        if pending["current_count"] >= pending["wait_count"]:
            keyword = pending["keyword"]
            keyword_type = pending["keyword_type"]
            
            # 获取群组的延时配置
            min_delay, max_delay = config.get_chat_delay(chat_id)
            # 随机延迟，避免被检测为脚本
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)
            
            # 发送口令
            try:
                await bot.send_message(chat_id, keyword)
                # 标记口令已发送
                config.mark_keyword_sent(chat_id, keyword)
                config.increment_joined()
                
                log_msg = (
                    f"[LuckyDraw] 成功参与抽奖 | "
                    f"群组: {chat_id} | "
                    f"类型: {keyword_type} | "
                    f"口令: {keyword} | "
                    f"等待人数: {pending['wait_count']} | "
                    f"延迟: {delay:.2f}s"
                )
                logs.info(log_msg)
                
                if is_test:
                    try:
                        await bot.send_message(chat_id, f"✅ 已发送口令: {keyword}")
                    except Exception:
                        pass
            except Exception as e:
                logs.error(f"[LuckyDraw] 发送口令失败: {e}")
            
            # 从队列中移除（安全删除，避免 KeyError）
            if queue_key in pending_draws:
                del pending_draws[queue_key]
