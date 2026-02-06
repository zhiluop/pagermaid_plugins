"""
贴纸跟随插件 - 自动跟随发送特定贴纸

功能：
- 在特定群组中，当有人发送特定贴纸时，自动跟随发送同一个贴纸
- 贴纸通过回复消息的形式设置
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message, Client
from pagermaid.utils import logs


# 配置文件路径
plugin_dir = Path(__file__).parent
config_file = plugin_dir / "sfl_config.json"


@Hook.on_startup()
async def plugin_startup():
    """插件初始化"""
    logs.info("贴纸跟随插件已加载")


@Hook.on_shutdown()
async def plugin_shutdown():
    """插件关闭"""
    logs.info("贴纸跟随插件已卸载")


class StickerFollowManager:
    """贴纸跟随配置管理类"""

    def __init__(self):
        self.chats: Dict[str, Dict] = {}  # chat_id -> {enabled, file_id, file_unique_id, chat_title}
        self.load()

    def load(self) -> None:
        """从文件加载配置"""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chats = data.get("chats", {})
                logs.info(f"贴纸跟随配置已加载，共 {len(self.chats)} 个群组")
            except Exception as e:
                logs.error(f"加载贴纸跟随配置失败: {e}")
                self.chats = {}
        else:
            self.chats = {}

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"chats": self.chats}, f, indent=4, ensure_ascii=False)
            logs.info("贴纸跟随配置已保存")
            return True
        except Exception as e:
            logs.error(f"保存贴纸跟随配置失败: {e}")
            return False

    def enable_chat(self, chat_id: str, chat_title: str) -> str:
        """开启群组的贴纸跟随"""
        if chat_id not in self.chats:
            self.chats[chat_id] = {
                "enabled": False,
                "file_id": None,
                "file_unique_id": None,
                "chat_title": chat_title
            }

        self.chats[chat_id]["enabled"] = True
        self.chats[chat_id]["chat_title"] = chat_title
        self.save()
        return f"群组 `{chat_title}` 的贴纸跟随已开启"

    def disable_chat(self, chat_id: str) -> str:
        """关闭群组的贴纸跟随"""
        if chat_id not in self.chats:
            return f"群组 `{chat_id}` 尚未配置"

        self.chats[chat_id]["enabled"] = False
        self.save()
        return f"群组 `{self.chats[chat_id]['chat_title']}` 的贴纸跟随已关闭"

    def set_sticker(self, chat_id: str, file_id: str, file_unique_id: str) -> str:
        """设置要跟随的贴纸"""
        if chat_id not in self.chats:
            return f"群组 `{chat_id}` 尚未配置，请先开启功能"

        self.chats[chat_id]["file_id"] = file_id
        self.chats[chat_id]["file_unique_id"] = file_unique_id
        self.save()
        return f"群组 `{self.chats[chat_id]['chat_title']}` 的跟随贴纸已设置"

    def get_chat_config(self, chat_id: str) -> Optional[Dict]:
        """获取群组配置"""
        return self.chats.get(str(chat_id))

    def list_chats(self) -> str:
        """列出所有已配置的群组"""
        if not self.chats:
            return "暂无配置的群组"

        lines = ["**已配置的群组列表：**\n"]
        for chat_id, config in self.chats.items():
            status = "✅ 已开启" if config["enabled"] else "❌ 已关闭"
            sticker_info = f"贴纸ID: `{config.get('file_unique_id', '未设置')}`" if config.get("file_unique_id") else "未设置贴纸"
            lines.append(f"- {config['chat_title']} (`{chat_id}`)\n  状态: {status}\n  {sticker_info}\n")

        return "\n".join(lines)


# 全局实例
manager = StickerFollowManager()


@listener(
    command="sfl",
    description="贴纸跟随管理",
    parameters="<on|off|set|list|help>",
    is_plugin=True,
)
async def sfl_command(message: Message):
    """处理贴纸跟随管理命令"""
    # 获取命令参数
    text = message.arguments or ""

    # 如果没有参数，返回提示信息并在3秒后撤回
    if not text or text.strip() == "":
        await message.edit("请输入命令参数")
        await asyncio.sleep(3)
        await message.delete()
        return

    cmd = text.lower().split()[0]

    if cmd == "on":
        await enable_chat(message)
    elif cmd == "off":
        await disable_chat(message)
    elif cmd == "set":
        await set_sticker(message)
    elif cmd == "list":
        await list_chats(message)
    elif cmd == "help":
        await show_help(message)
    else:
        await show_help(message)


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**贴纸跟随插件使用说明:**

**,sfl on** - 开启当前聊天的贴纸跟随
**,sfl off** - 关闭当前聊天的贴纸跟随
**,sfl set** - 回复一条贴纸消息来设置要跟随的贴纸
**,sfl list** - 查看已设置的群组列表
**,sfl help** - 显示此帮助信息

**使用方式:**
1. 在群组中使用 `,sfl on` 开启功能
2. 回复一条想要跟随的贴纸消息，使用 `,sfl set` 设置
3. 当群组中有人发送该贴纸时，机器人会自动跟随发送同一个贴纸

**注意事项:**
- 每个群组需要单独开启和设置贴纸
- 贴纸ID通过回复消息获取"""
    await message.edit(help_text)


async def enable_chat(message: Message):
    """开启当前聊天的贴纸跟随"""
    if not message.chat:
        await message.edit("❌ 只能在聊天中使用此命令")
        await asyncio.sleep(3)
        await message.delete()
        return

    chat_id = str(message.chat.id)
    chat_title = message.chat.title or message.chat.first_name or f"Chat-{chat_id}"

    result = manager.enable_chat(chat_id, chat_title)
    file_unique_id = manager.chats[chat_id].get("file_unique_id")

    if file_unique_id:
        await message.edit(f"✅ {result}\n当前贴纸ID: `{file_unique_id}`")
    else:
        await message.edit(
            f"✅ {result}\n\n💡 请回复一条贴纸消息并使用 `,sfl set` 设置要跟随的贴纸"
        )

    await asyncio.sleep(3)
    await message.delete()


async def disable_chat(message: Message):
    """关闭当前聊天的贴纸跟随"""
    if not message.chat:
        await message.edit("❌ 只能在聊天中使用此命令")
        await asyncio.sleep(3)
        await message.delete()
        return

    chat_id = str(message.chat.id)
    result = manager.disable_chat(chat_id)
    await message.edit(f"{'✅' if '已关闭' in result else '❌'} {result}")
    await asyncio.sleep(3)
    await message.delete()


async def set_sticker(message: Message):
    """设置要跟随的贴纸"""
    # 检查是否回复了消息
    if not message.reply_to_message:
        await message.edit(
            "❌ 请回复一条贴纸消息\n\n使用方法：回复一条贴纸消息后发送 `,sfl set`"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    reply_msg = message.reply_to_message

    # 检查回复的消息是否是贴纸
    if not reply_msg.sticker:
        await message.edit("❌ 回复的消息不是贴纸\n\n请回复一条贴纸消息")
        await asyncio.sleep(3)
        await message.delete()
        return

    if not message.chat:
        await message.edit("❌ 只能在聊天中使用此命令")
        await asyncio.sleep(3)
        await message.delete()
        return

    chat_id = str(message.chat.id)
    file_id = reply_msg.sticker.file_id
    file_unique_id = reply_msg.sticker.file_unique_id

    logs.info(f"[贴纸跟随] 设置贴纸 - file_id: {file_id}, file_unique_id: {file_unique_id}")

    # 检查群组是否已配置
    if chat_id not in manager.chats:
        await message.edit(
            "⚠️ 当前聊天尚未开启贴纸跟随\n\n请先使用 `,sfl on` 开启功能"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    result = manager.set_sticker(chat_id, file_id, file_unique_id)
    await message.edit(f"✅ {result}\n贴纸ID: `{file_unique_id}`")
    await asyncio.sleep(3)
    await message.delete()


async def list_chats(message: Message):
    """列出所有已配置的群组"""
    result = manager.list_chats()
    await message.edit(result)
    await asyncio.sleep(3)
    await message.delete()


@listener(is_plugin=True, incoming=True, outgoing=True, ignore_edited=True)
async def sticker_follow_trigger(message: Message, bot: Client):
    """监听贴纸消息并自动跟随"""
    # 只处理贴纸消息
    if not message.sticker:
        return

    logs.info(f"[贴纸跟随] 检测到贴纸消息")

    # 只在群组中处理
    if not message.chat or message.chat.id >= 0:
        logs.info(f"[贴纸跟随] 忽略非群组消息")
        return

    chat_id = str(message.chat.id)
    file_id = message.sticker.file_id
    file_unique_id = message.sticker.file_unique_id

    logs.info(f"[贴纸跟随] 群组ID: {chat_id}, file_id: {file_id}, file_unique_id: {file_unique_id}")

    # 获取群组配置
    config = manager.get_chat_config(chat_id)
    if not config:
        logs.info(f"[贴纸跟随] 群组 {chat_id} 未配置")
        return

    # 检查是否开启
    if not config.get("enabled"):
        logs.info(f"[贴纸跟随] 群组 {chat_id} 功能未开启")
        return

    # 检查是否是设置的贴纸（使用 file_unique_id 进行匹配）
    target_file_unique_id = config.get("file_unique_id")
    target_file_id = config.get("file_id")

    logs.info(f"[贴纸跟随] 目标 file_unique_id: {target_file_unique_id}, file_id: {target_file_id}")

    if not target_file_unique_id:
        logs.info(f"[贴纸跟随] 群组 {chat_id} 未设置贴纸")
        return

    # 优先使用 file_unique_id 匹配
    if file_unique_id != target_file_unique_id:
        logs.info(f"[贴纸跟随] 贴纸不匹配: {file_unique_id} != {target_file_unique_id}")
        return

    logs.info(f"[贴纸跟随] 贴纸匹配成功！准备发送...")

    # 发送同一个贴纸（使用 file_id）
    try:
        await message.reply_sticker(target_file_id)
        logs.info(f"[贴纸跟随] 在群组 {config['chat_title']} 中跟随发送了贴纸")
    except Exception as e:
        logs.error(f"[贴纸跟随] 发送贴纸失败: {e}")
