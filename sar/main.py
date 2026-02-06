"""
贴纸自动回复插件 (SAR - Sticker Auto Reply)
功能描述: 在指定群组中，当有人用贴纸回复我的消息时，自动回复同样的贴纸
文件名: sar.py
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional, Set

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message, Client
from pagermaid.utils import logs


# 配置文件路径
plugin_dir = Path(__file__).parent
config_file = plugin_dir / "sar_config.json"


class SARConfig:
    """贴纸自动回复配置管理类"""

    def __init__(self):
        self.enabled_chats: Set[int] = set()  # 启用功能的群组ID集合
        self.my_user_id: Optional[int] = None  # 自己的用户ID
        self.stats: dict = {"total_replied": 0}  # 统计信息
        self.load()

    def load(self) -> None:
        """从文件加载配置"""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.enabled_chats = set(data.get("enabled_chats", []))
                    self.my_user_id = data.get("my_user_id")
                    self.stats = data.get("stats", {"total_replied": 0})
                logs.info(
                    f"[SAR] 配置已加载，已启用 {len(self.enabled_chats)} 个群组"
                )
            except Exception as e:
                logs.error(f"[SAR] 加载配置失败: {e}")
                self.enabled_chats = set()
                self.my_user_id = None
                self.stats = {"total_replied": 0}
        else:
            logs.info("[SAR] 配置文件不存在，使用默认配置")
            self.save()

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "enabled_chats": list(self.enabled_chats),
                        "my_user_id": self.my_user_id,
                        "stats": self.stats,
                    },
                    f,
                    indent=4,
                    ensure_ascii=False,
                )
            return True
        except Exception as e:
            logs.error(f"[SAR] 保存配置失败: {e}")
            return False

    def add_chat(self, chat_id: int) -> str:
        """添加启用功能的群组"""
        if chat_id in self.enabled_chats:
            return f"⚠️ 群组 `{chat_id}` 已在启用列表中"
        self.enabled_chats.add(chat_id)
        self.save()
        return f"✅ 已启用群组 `{chat_id}` 的贴纸自动回复功能"

    def remove_chat(self, chat_id: int) -> str:
        """移除启用功能的群组"""
        if chat_id not in self.enabled_chats:
            return f"⚠️ 群组 `{chat_id}` 未启用此功能"
        self.enabled_chats.remove(chat_id)
        self.save()
        return f"❌ 已禁用群组 `{chat_id}` 的贴纸自动回复功能"

    def is_enabled(self, chat_id: int) -> bool:
        """检查群组是否启用功能"""
        return chat_id in self.enabled_chats

    def list_chats(self) -> str:
        """列出所有启用的群组"""
        if not self.enabled_chats:
            return "📋 **当前没有启用任何群组**"

        output = "📋 **已启用的群组列表：**\n\n"
        for chat_id in self.enabled_chats:
            output += f"• 群组ID: `{chat_id}`\n"
        return output

    def get_stats(self) -> str:
        """获取统计信息"""
        output = "📊 **统计信息：**\n\n"
        output += f"启用群组数: `{len(self.enabled_chats)}`\n"
        output += f"累计回复: `{self.stats['total_replied']}` 次\n"
        return output

    def increment_stats(self) -> None:
        """增加统计计数"""
        self.stats["total_replied"] += 1
        self.save()


# 全局配置实例
config = SARConfig()


# ==================== 生命周期钩子 ====================


@Hook.on_startup()
async def sar_startup():
    """插件启动时执行"""
    logs.info("[SAR] 贴纸自动回复插件已加载")


@Hook.on_shutdown()
async def sar_shutdown():
    """插件关闭时执行"""
    logs.info("[SAR] 贴纸自动回复插件已卸载")


# ==================== 管理命令 ====================


@listener(
    command="sar",
    description="贴纸自动回复管理命令",
    parameters="<add|remove|list|stats|on|off>",
    is_plugin=True,
)
async def sar_command(message: Message):
    """处理 SAR 管理命令"""
    # 获取当前用户的ID
    bot = getattr(message, "_client", None)
    if bot:
        try:
            me = await bot.get_me()
            config.my_user_id = me.id
            config.save()
        except Exception as e:
            logs.error(f"[SAR] 获取用户信息失败: {e}")

    # 获取命令参数
    text = message.arguments or ""

    # 如果没有参数，返回提示信息并在3秒后撤回
    if not text or text.strip() == "":
        await message.edit("请输入文本")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 检查是否是帮助命令
    if text.strip().lower() == "help":
        await show_help(message)
        return

    cmd = text.lower().split()[0]

    # 添加当前群组
    if cmd == "add" or cmd == "on":
        # 只能在群组中使用
        if not message.chat or message.chat.id > 0:
            await message.edit("❌ 此命令只能在群组中使用")
            await asyncio.sleep(3)
            await message.delete()
            return

        chat_id = message.chat.id
        result = config.add_chat(chat_id)
        await message.edit(result)
        await asyncio.sleep(3)
        await message.delete()

    # 移除当前群组
    elif cmd == "remove" or cmd == "off":
        # 只能在群组中使用
        if not message.chat or message.chat.id > 0:
            await message.edit("❌ 此命令只能在群组中使用")
            await asyncio.sleep(3)
            await message.delete()
            return

        chat_id = message.chat.id
        result = config.remove_chat(chat_id)
        await message.edit(result)
        await asyncio.sleep(3)
        await message.delete()

    # 手动添加指定群组ID
    elif cmd == "set":
        params = text.split()
        if len(params) < 2:
            await message.edit(
                "❌ **参数错误！**\n\n"
                "使用方法: `,sar set <群组ID>`\n\n"
                "示例: `,sar set -1001234567890`"
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        try:
            chat_id = int(params[1])
            result = config.add_chat(chat_id)
            await message.edit(result)
            await asyncio.sleep(3)
            await message.delete()
        except ValueError:
            await message.edit("❌ **群组ID格式错误！**\n\n请输入有效的数字ID")
            await asyncio.sleep(3)
            await message.delete()

    # 查看配置
    elif cmd == "list":
        await message.edit(config.list_chats())
        await asyncio.sleep(3)
        await message.delete()

    # 统计信息
    elif cmd == "stats":
        await message.edit(config.get_stats())
        await asyncio.sleep(3)
        await message.delete()

    else:
        await show_help(message)


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**📖 贴纸自动回复插件使用说明**

**功能描述：**
当有人在启用功能的群组中用贴纸回复你的消息时，自动回复同样的贴纸。

**管理命令：**

**,sar on** - 在当前群组启用功能
**,sar off** - 在当前群组禁用功能
**,sar set <群组ID>** - 启用指定群组的功能
  • 示例: `,sar set -1001234567890`

**,sar list** - 查看所有启用的群组
**,sar stats** - 查看统计信息

---

**💡 提示：**
• 此功能只在群组中生效
• 需要有人用贴纸**回复**你的消息才会触发
• 会回复完全相同的贴纸"""

    await message.edit(help_text)


# ==================== 贴纸自动回复监听器 ====================


@listener(is_plugin=True, incoming=True, outgoing=False, ignore_edited=True)
async def sticker_auto_reply_handler(message: Message, bot: Client):
    """
    贴纸自动回复消息处理器

    检测传入的贴纸消息，如果是在回复我的消息，则自动回复相同的贴纸
    """
    # 检查是否有发送者
    if not message.from_user:
        return

    # 检查是否是贴纸消息
    if not message.sticker:
        return

    # 检查是否回复了消息
    if not message.reply_to_message:
        return

    # 检查是否在启用的群组中
    if not config.is_enabled(message.chat.id):
        return

    # 获取我的用户ID
    if not config.my_user_id:
        try:
            me = await bot.get_me()
            config.my_user_id = me.id
            config.save()
        except Exception as e:
            logs.error(f"[SAR] 获取用户信息失败: {e}")
            return

    # 检查回复的消息是否是我发送的
    replied_message = message.reply_to_message
    if not replied_message.from_user or replied_message.from_user.id != config.my_user_id:
        return

    # 执行贴纸回复
    try:
        # 获取贴纸文件ID
        sticker_file_id = message.sticker.file_id

        # 回复相同的贴纸
        await replied_message.reply(sticker=sticker_file_id)

        # 更新统计
        config.increment_stats()

        # 获取用户信息用于日志
        user_name = (
            message.from_user.username
            or message.from_user.first_name
            or str(message.from_user.id)
        )
        logs.info(
            f"[SAR] 已回复用户 {user_name}({message.from_user.id}) 在群组 {message.chat.id} 的贴纸"
        )

    except Exception as e:
        logs.error(f"[SAR] 贴纸回复失败: {e}")
