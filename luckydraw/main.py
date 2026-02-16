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

# 抢红包随机延迟范围（秒）
MIN_DELAY = 2.0
MAX_DELAY = 5.0


class LuckyDrawConfig:
    """自动抽奖配置管理类"""

    def __init__(self):
        self.enabled_chats: Set[int] = set()  # 启用功能的群组ID集合
        self.test_chats: Set[int] = set()  # 测试群组（输出详细日志）
        self.sent_keywords: Dict[str, list] = {}  # 已发送的口令 {群组ID: [口令1, 口令2, ...]}
        self.sent_messages: Set[str] = set()  # 已处理的消息ID {群组ID_消息ID}
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
                    self.stats = data.get("stats", self.stats)
            except Exception as e:
                logs.error(f"[LuckyDraw] 加载配置失败: {e}")
                self.enabled_chats = set()
                self.test_chats = set()
                self.sent_keywords = {}
                self.sent_messages = set()
                self.stats = {"total_detected": 0, "total_joined": 0, "total_blocked": 0}
        else:
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


class KeywordExtractor:
    """口令提取器"""

    # 口令提取规则列表（按优先级排序）
    PATTERNS = [
        # 格式1: 【密令抽奖】...领取密令: xxx
        (r"领取密令[：:]\s*(.+?)(?:\n|$)", "密令抽奖"),
        # 格式2: 参与关键词：「xxx」 或 参与关键词：xxx
        (r"参与关键词[：:]\s*[「「\"]?(.+?)[」」\"]?(?:\n|$)", "参与关键词"),
        # 格式3: 发送 xxx 进行领取 / 发送 xxx 领取
        (r"发送\s+(.+?)\s+(?:进行)?领取", "红包口令"),
        # 格式4: 输入口令: xxx / 口令: xxx
        (r"(?:输入)?口令[：:]\s*(.+?)(?:\n|$)", "口令"),
        # 格式5: 回复 xxx 领取 / 回复 xxx 参与
        (r"回复\s+(.+?)\s+(?:领取|参与)", "回复口令"),
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
    else:
        await show_help(message)


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**自动抽奖插件使用说明**

**功能描述：**
在启用功能的群组中，自动识别红包/抽奖活动消息并发送口令参与。
每个口令只发送一次，不会重复发送。

**支持的口令格式：**
- `领取密令: xxx` → 发送 xxx
- `参与关键词：「xxx」` → 发送 xxx
- `发送 xxx 进行领取` → 发送 xxx
- `口令: xxx` → 发送 xxx

**安全检测：**
如果消息或口令中包含以下关键词，将自动跳过：
脚本、检测、不能领、禁止脚本、防脚本等

**管理命令：**

`,ldraw set <群组ID>` - 启用指定群组
`,ldraw set <群组ID> off` - 禁用指定群组
`,ldraw set <群组ID> test` - 添加到测试群组（输出详细日志）
`,ldraw set <群组ID> test off` - 从测试群组移除
`,ldraw list` - 查看所有启用的群组
`,ldraw stats` - 查看统计信息
`,ldraw test <文本>` - 测试口令提取功能
`,ldraw clear` - 清除已发送口令记录

**注意事项：**
- 为避免被检测，插件会随机延迟 0.5-2 秒发送口令
- 建议在信任的群组中使用此功能
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


# ==================== 自动抽奖监听器 ====================


@listener(is_plugin=True, incoming=True, outgoing=False, ignore_edited=True)
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

    # 随机延迟，避免被检测为脚本
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    await asyncio.sleep(delay)

    # 发送口令（直接发送到群组，而不是回复）
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
