"""
JPMAI 插件 - AI 生成艳情文案回复
触发方式: 在群组中发送 /关键词
基于 jpm 插件升级，调用 AI 模型实时生成仿明清艳情小说风格的文案
"""

import contextlib
import json
import time
from pathlib import Path
from typing import Optional, Dict

import httpx

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message, Client
from pagermaid.utils import logs


# 配置文件路径
plugin_dir = Path(__file__).parent
config_file = plugin_dir / "jpmai_config.json"
trigger_log_file = plugin_dir / "jpmai_trigger_log.json"

# 默认频率限制（秒）
DEFAULT_RATE_LIMIT = 3600

# 默认模型
DEFAULT_MODEL = "glm-4.6"

# 系统提示词 - 仿明清艳情小说风格
SYSTEM_PROMPT = """你是一位精通明清艳情小说的文学大师，擅长模仿《肉蒲团》《灯草和尚》《金云翘传》《品花鉴宝》《欢喜缘》等经典作品的文风。

你的任务是根据用户指令创作一段艳情文案。

**重要要求：**
- 只生成一段文案，不要重复，不要生成多个版本
- 直接输出文案内容，不要有任何前缀、后缀或解释
- 不要输出"好的"、"以下是"等开场白

**文风要求：**
- 使用半文半白的语言风格，带有古典韵味
- 描写要露骨、香艳、撩人，直接描绘肉体之欢、床第之事
- 善用"云雨"、"巫山"、"销魂"等典故，以及比喻、暗示与直白描写相结合
- 细腻描绘身体感受、肌肤触感、呼吸心跳
- 注重氛围营造：烛光、帷帐、香气、月色等
- 必须包含具体的身体描写和感官体验
- 要有情节发展，不是纯粹的堆砌

**字数控制：** 280-350字

请记住：你的目标是创作真正露骨香艳的艳情文学，不是含蓄暗示的普通言情。"""


@Hook.on_startup()
async def plugin_startup():
    """插件初始化"""
    logs.info("JPMAI 插件已加载")


@Hook.on_shutdown()
async def plugin_shutdown():
    """插件关闭"""
    logs.info("JPMAI 插件已卸载")


class AIGenerator:
    """AI 文案生成器"""

    def __init__(self, api_url: str, api_key: str, model: str = DEFAULT_MODEL):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate_single(self, name: str) -> str:
        """生成单人文案"""
        user_prompt = f"""【单人场景】请为"{name}"创作一段艳情文案。

{name}独处闺房/书房，夜深人静，春心萌动，情欲难耐。描写{name}身体的燥热与渴望、辗转难眠的春思、手指不自觉地游走、肌肤的敏感与颤栗、呼吸的急促与轻吟。

注意：只生成一段文案，约300字。"""

        return await self._call_api(user_prompt)

    async def generate_dual(self, name: str, target: str) -> str:
        """生成双人文案"""
        user_prompt = f"""【双人场景】请为"{name}"和"{target}"创作一段艳情文案。

{name}与{target}独处，暧昧气氛升温，情欲暗涌。描写两人之间的眉目传情、肌肤触碰时的电流感、呼吸交缠唇齿相接、衣衫渐解春光乍泄、身体纠缠的欢愉。

注意：只生成一段文案，约300字。"""

        return await self._call_api(user_prompt)

    async def _call_api(self, user_prompt: str) -> str:
        """调用 API 生成文案"""
        url = f"{self.api_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 25600,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]

                    # 提取真正的文案内容（过滤掉思考过程）
                    extracted_content = self._extract_content(content)

                    if extracted_content:
                        return extracted_content
                    else:
                        # 如果提取失败，返回原始内容
                        logs.warning("[JPMAI] 内容提取失败，返回原始内容")
                        return content.strip()
                else:
                    logs.error(f"[JPMAI] API 返回无效响应: {data}")
                    return "生成失败，请稍后再试"

        except httpx.TimeoutException:
            logs.error("[JPMAI] API 请求超时")
            return "生成超时，请稍后再试"
        except httpx.HTTPStatusError as e:
            logs.error(
                f"[JPMAI] API 请求失败: {e.response.status_code} - {e.response.text}"
            )
            return f"生成失败: HTTP {e.response.status_code}"
        except Exception as e:
            logs.error(f"[JPMAI] API 调用异常: {e}")
            return f"生成失败: {e}"

    def _extract_content(self, raw_content: str) -> Optional[str]:
        """从AI回复中提取真正的文案内容"""
        # 过滤关键词：思考过程通常会包含这些
        filter_keywords = [
            "拆解",
            "构思",
            "初稿",
            "步骤",
            "内心活动",
            "场景构建",
            "起草",
            "润色",
            "构思",
            "最终",
            "修改",
            "提炼",
            "首先",
            "其次",
            "然后",
            "最后",
            "总之",
            "第一",
            "第二",
            "第三",
            "段落",
            "标题",
        ]

        # 按段落分割
        paragraphs = [p.strip() for p in raw_content.split("\n") if p.strip()]

        if not paragraphs:
            return None

        # 如果只有一个段落，直接返回
        if len(paragraphs) == 1:
            return paragraphs[0]

        # 过滤掉包含思考过程关键词的段落
        filtered_paragraphs = []
        for para in paragraphs:
            # 检查是否包含过滤关键词
            if any(keyword in para for keyword in filter_keywords):
                continue

            # 检查是否是标题（较短且包含特殊符号）
            if len(para) < 30 and (
                "：" in para or ":" in para or para.endswith("：") or para.endswith(":")
            ):
                continue

            filtered_paragraphs.append(para)

        # 如果过滤后没有段落，使用原始段落中最长的
        if not filtered_paragraphs:
            filtered_paragraphs = paragraphs

        # 返回最长的段落（通常是正文）
        longest_para = max(filtered_paragraphs, key=len)

        # 限制字数在280-350字之间
        if len(longest_para) > 400:
            longest_para = longest_para[:350] + "..."

        return longest_para


class JPMAIConfigManager:
    """配置管理类"""

    def __init__(self):
        self.enabled: bool = False  # 插件总开关
        self.owner_id: Optional[int] = None  # 插件所有者ID
        self.api_url: Optional[str] = None  # API 地址
        self.api_key: Optional[str] = None  # API 密钥
        self.model: str = DEFAULT_MODEL  # 模型名称
        self.keywords: Dict[
            str, Dict
        ] = {}  # keyword -> {target_user_id, target_chat_id, rate_limit_seconds, anchor_message_id}
        self.load()

    def load(self) -> None:
        """从文件加载配置"""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.enabled = data.get("enabled", False)
                    self.owner_id = data.get("owner_id")
                    self.api_url = data.get("api_url")
                    self.api_key = data.get("api_key")
                    self.model = data.get("model", DEFAULT_MODEL)
                    self.keywords = data.get("keywords", {})
                logs.info(f"JPMAI 配置已加载，共 {len(self.keywords)} 个关键词")
            except Exception as e:
                logs.error(f"加载 JPMAI 配置失败: {e}")
                self._reset()
        else:
            self.keywords = {}

    def _reset(self):
        """重置配置"""
        self.enabled = False
        self.owner_id = None
        self.api_url = None
        self.api_key = None
        self.model = DEFAULT_MODEL
        self.keywords = {}

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "enabled": self.enabled,
                        "owner_id": self.owner_id,
                        "api_url": self.api_url,
                        "api_key": self.api_key,
                        "model": self.model,
                        "keywords": self.keywords,
                    },
                    f,
                    indent=4,
                    ensure_ascii=False,
                )
            logs.info("JPMAI 配置已保存")
            return True
        except Exception as e:
            logs.error(f"保存 JPMAI 配置失败: {e}")
            return False

    def set_api(self, api_url: str, api_key: str, model: str = None) -> str:
        """设置 API 配置"""
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        if model:
            self.model = model
        self.save()
        return f"API 配置已更新\nURL: `{self.api_url}`\n模型: `{self.model}`"

    def is_api_configured(self) -> bool:
        """检查 API 是否已配置"""
        return bool(self.api_url and self.api_key)

    def get_generator(self) -> Optional[AIGenerator]:
        """获取 AI 生成器实例"""
        if not self.is_api_configured():
            return None
        return AIGenerator(self.api_url, self.api_key, self.model)

    def add_keyword(
        self,
        keyword: str,
        target_user_id: int,
        target_chat_id: int,
        rate_limit: int = DEFAULT_RATE_LIMIT,
    ) -> str:
        """添加或更新关键词配置"""
        if not keyword or not keyword.strip():
            return "关键词不能为空"
        if rate_limit < 0:
            return "频率限制必须大于等于0"

        # 保留已有的锚点消息ID
        existing_anchor = None
        if keyword in self.keywords:
            existing_anchor = self.keywords[keyword].get("anchor_message_id")

        self.keywords[keyword] = {
            "target_user_id": target_user_id,
            "target_chat_id": target_chat_id,
            "rate_limit_seconds": rate_limit,
            "anchor_message_id": existing_anchor,
        }
        self.save()
        return f"关键词 `{keyword}` 配置已更新"

    def set_anchor(self, keyword: str, anchor_message_id: int) -> str:
        """设置关键词的锚点消息ID"""
        if keyword not in self.keywords:
            return f"关键词 `{keyword}` 不存在"

        self.keywords[keyword]["anchor_message_id"] = anchor_message_id
        self.save()
        return f"关键词 `{keyword}` 的锚点消息已设置"

    def get_anchor(self, keyword: str) -> Optional[int]:
        """获取关键词的锚点消息ID"""
        config = self.keywords.get(keyword)
        return config.get("anchor_message_id") if config else None

    def clear_anchor(self, keyword: str) -> str:
        """清除关键词的锚点消息ID"""
        if keyword not in self.keywords:
            return f"关键词 `{keyword}` 不存在"

        if "anchor_message_id" in self.keywords[keyword]:
            del self.keywords[keyword]["anchor_message_id"]
            self.save()
            return f"关键词 `{keyword}` 的锚点消息已清除"
        return f"关键词 `{keyword}` 没有设置锚点消息"

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
            lines.append(
                f"- `{keyword}` → 用户: `{config['target_user_id']}`, 群组: `{config['target_chat_id']}`, 限制: {config['rate_limit_seconds']}秒"
            )
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
                logs.info(f"JPMAI 触发记录已加载，共 {len(self.logs)} 条")
            except Exception as e:
                logs.error(f"加载 JPMAI 触发记录失败: {e}")
                self.logs = {}
        else:
            self.logs = {}

    def save(self) -> None:
        """保存触发记录到文件"""
        try:
            with open(trigger_log_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=4)
        except Exception as e:
            logs.error(f"保存 JPMAI 触发记录失败: {e}")

    def can_trigger(self, keyword: str, is_owner: bool) -> tuple[bool, Optional[int]]:
        """检查关键词是否可以触发"""
        # 主人无限制
        if is_owner:
            return True, None

        # 检查频率限制
        if keyword in self.logs:
            last_time = self.logs[keyword]
            elapsed = time.time() - last_time
            keyword_config = config_manager.get_keyword_config(keyword)
            if keyword_config:
                rate_limit = keyword_config.get(
                    "rate_limit_seconds", DEFAULT_RATE_LIMIT
                )
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
config_manager = JPMAIConfigManager()
trigger_log = TriggerLogManager()


@listener(
    command="jpmai",
    description="JPMAI 插件管理 - AI 生成艳情文案",
    parameters="<on|off|set|delete|list|owner|status|anchor|api>",
    is_plugin=True,
)
async def jpmai_command(message: Message):
    """处理 jpmai 管理命令"""
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
    elif cmd == "anchor":
        await manage_anchor(message)
    elif cmd == "api":
        await set_api(message)
    else:
        await show_help(message)


def check_permission(message: Message) -> bool:
    """检查消息发送者是否有权限执行管理命令"""
    if config_manager.owner_id is None:
        return True
    return message.from_user.id == config_manager.owner_id


async def show_help(message: Message):
    """显示帮助信息"""
    help_text = """**JPMAI 插件使用说明:**

**,jpmai on** - 开启全局功能
**,jpmai off** - 关闭全局功能
**,jpmai api <URL> <密钥> [模型]** - 设置 API 配置
**,jpmai set <关键词> <用户ID> <群组ID> [秒数]** - 添加/更新关键词配置
**,jpmai delete <关键词>** - 删除关键词配置
**,jpmai list** - 列出所有关键词配置
**,jpmai owner <用户ID>** - 设置主人ID
**,jpmai status** - 查看当前状态
**,jpmai anchor <set|clear> <关键词> [消息ID]** - 管理锚点消息

**API 配置示例:**
`,jpmai api http://example.com:8317 sk-xxxx glm-4.6`

**触发方式:**
- 在群组中发送 `/关键词` 触发 AI 生成单人文案
- 回复某人或带参数 `/关键词 xxx` 触发 AI 生成双人文案

**说明:**
本插件使用 AI 模型实时生成仿明清艳情小说风格的文案，支持单人和双人场景。"""
    await message.edit(help_text)


async def enable_feature(message: Message):
    """开启全局功能"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    if not config_manager.is_api_configured():
        await message.edit("❌ 请先配置 API\n使用 `,jpmai api <URL> <密钥> [模型]`")
        return

    config_manager.enabled = True
    config_manager.save()

    if not config_manager.keywords:
        await message.edit(
            "⚠️ JPMAI 功能已开启，但尚未配置关键词\n使用 `,jpmai set <关键词> <用户ID> <群组ID>` 添加配置"
        )
    else:
        await message.edit(
            f"✅ JPMAI 功能已开启\n已配置 {len(config_manager.keywords)} 个关键词"
        )


async def disable_feature(message: Message):
    """关闭全局功能"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    config_manager.enabled = False
    config_manager.save()
    await message.edit("❌ JPMAI 功能已关闭")


async def set_api(message: Message):
    """设置 API 配置"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    params = message.arguments.split()
    if len(params) < 3:
        await message.edit(
            "❌ 参数错误！\n使用 `,jpmai api <URL> <密钥> [模型]`\n\n示例：\n`,jpmai api http://example.com:8317 sk-xxxx glm-4.6`"
        )
        return

    api_url = params[1]
    api_key = params[2]
    model = params[3] if len(params) > 3 else None

    msg = config_manager.set_api(api_url, api_key, model)
    await message.edit(f"✅ {msg}")


async def set_keyword(message: Message):
    """设置关键词配置"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    params = message.arguments.split()
    if len(params) < 4:
        await message.edit(
            "❌ 参数错误！\n使用 `,jpmai set <关键词> <用户ID> <群组ID> [秒数]`"
        )
        return

    try:
        keyword = params[1]
        user_id = int(params[2])
        chat_id = int(params[3])
        rate_limit = int(params[4]) if len(params) > 4 else DEFAULT_RATE_LIMIT

        msg = config_manager.add_keyword(keyword, user_id, chat_id, rate_limit)
        await message.edit(
            f"✅ {msg}\n用户ID: `{user_id}`\n群组ID: `{chat_id}`\n频率限制: {rate_limit}秒"
        )
    except ValueError:
        await message.edit("❌ ID格式错误！请输入有效的数字ID")


async def delete_keyword(message: Message):
    """删除关键词配置"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    params = message.arguments.split()
    if len(params) < 2:
        await message.edit("❌ 参数错误！\n使用 `,jpmai delete <关键词>`")
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
    if config_manager.owner_id is not None and not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    params = message.arguments.split()
    if len(params) < 2:
        await message.edit("❌ 参数错误！\n使用 `,jpmai owner <用户ID>`")
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
    api_status = "✅ 已配置" if config_manager.is_api_configured() else "❌ 未配置"
    api_url = f"`{config_manager.api_url}`" if config_manager.api_url else "未设置"
    model = f"`{config_manager.model}`"
    keywords_list = config_manager.list_keywords()

    status_text = f"""**JPMAI 插件状态:**

功能状态: {status}
主人ID: {owner_info}
API状态: {api_status}
API地址: {api_url}
模型: {model}

{keywords_list}

**频率限制:** 主人无限制，其他人按关键词独立计算

**触发方式:** `/关键词` 或 `/关键词 目标名`"""
    await message.edit(status_text)


async def manage_anchor(message: Message):
    """管理锚点消息"""
    if not check_permission(message):
        await message.edit("❌ 权限不足！只有主人可以执行此操作")
        return

    params = message.arguments.split()
    if len(params) < 2:
        await message.edit(
            "❌ 参数错误！\n使用 `,jpmai anchor <set|clear> <关键词> [消息ID]`"
        )
        return

    action = params[1].lower()
    keyword = params[2] if len(params) > 2 else None

    if not keyword:
        await message.edit("❌ 请指定关键词")
        return

    if action == "set":
        message_id = None

        if message.reply_to_message:
            message_id = message.reply_to_message.id
        elif len(params) > 3:
            try:
                message_id = int(params[3])
            except ValueError:
                await message.edit("❌ 消息ID格式错误！请输入有效的数字ID")
                return
        else:
            await message.edit(
                "❌ 请回复一条消息或指定消息ID\n使用方法：回复一条消息后发送 `,jpmai anchor set <关键词>`"
            )
            return

        result = config_manager.set_anchor(keyword, message_id)
        await message.edit(f"✅ {result}\n锚点消息ID: `{message_id}`")

    elif action == "clear":
        result = config_manager.clear_anchor(keyword)
        await message.edit(f"{'✅' if '已清除' in result else '❌'} {result}")
    else:
        await message.edit("❌ 未知操作！使用 `set` 或 `clear`")


async def get_target_user_last_message(
    client: Client, chat_id: int, user_id: int, limit: int = 100
):
    """获取指定用户在群组中的最近一条消息"""
    try:
        async for msg in client.get_chat_history(chat_id, limit=limit):
            if msg.from_user and msg.from_user.id == user_id:
                return msg
        return None
    except Exception as e:
        logs.error(f"获取用户消息失败: {e}")
        return None


@listener(is_plugin=True, incoming=True, outgoing=False, ignore_edited=True)
async def track_anchor_messages(message: Message, bot: Client):
    """自动记录目标用户的发言作为锚点消息"""
    # 只处理群组消息
    if not message.chat or message.chat.id >= 0:
        return

    # 获取发送者ID
    if not message.from_user:
        return

    sender_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.id

    # 检查是否有任何关键词配置了这个用户作为目标
    for keyword, config in config_manager.keywords.items():
        if (
            config["target_user_id"] == sender_id
            and config["target_chat_id"] == chat_id
        ):
            config["anchor_message_id"] = message_id
            config_manager.save()
            logs.debug(f"[JPMAI] 更新关键词 `{keyword}` 的锚点消息: {message_id}")
            break


@listener(is_plugin=True, incoming=True, outgoing=True, ignore_edited=True)
async def trigger_jpmai(message: Message, bot: Client):
    """触发 jpmai 回复 - 只处理 /关键词 格式的消息"""
    text = message.text or ""

    # 快速过滤：只处理以 / 开头的消息
    if not text.startswith("/"):
        return

    # 提取关键词和参数
    parts = text[1:].strip().split()
    keyword = parts[0] if parts else ""
    param = parts[1] if len(parts) > 1 else None

    if not keyword:
        return

    # 快速过滤：只处理已配置的关键词
    keyword_config = config_manager.get_keyword_config(keyword)
    if not keyword_config:
        return

    # 快速过滤：只在目标群组中处理
    if message.chat.id != keyword_config["target_chat_id"]:
        return

    # 检查功能是否开启
    if not config_manager.enabled:
        logs.info(f"[JPMAI] 关键词 `/{keyword}` 被触发，但功能未开启")
        return

    # 检查 API 是否配置
    generator = config_manager.get_generator()
    if not generator:
        logs.warning(f"[JPMAI] 关键词 `/{keyword}` 被触发，但 API 未配置")
        return

    # 获取触发用户ID
    trigger_user_id = message.from_user.id if message.from_user else None
    if not trigger_user_id:
        return

    # 检查是否是主人
    is_owner = (
        (trigger_user_id == config_manager.owner_id)
        if config_manager.owner_id
        else False
    )

    # 检查频率限制
    can_trigger, wait_time = trigger_log.can_trigger(keyword, is_owner)
    if not can_trigger:
        logs.info(
            f"[JPMAI] 用户 {trigger_user_id} 触发 `/{keyword}` 过于频繁，需等待 {wait_time} 秒"
        )
        return

    # 判断使用单人还是双人模式
    is_reply_to_someone = message.reply_to_message is not None
    has_param = param is not None
    use_dual = is_reply_to_someone or has_param

    # 生成回复内容
    with contextlib.suppress(Exception):
        target_message = None
        anchor_message_id = keyword_config.get("anchor_message_id")

        # 优先使用锚点消息
        if anchor_message_id:
            try:
                target_message = await bot.get_messages(
                    message.chat.id, anchor_message_id
                )
                logs.debug(f"[JPMAI] 使用锚点消息: {anchor_message_id}")
            except Exception as e:
                logs.warning(
                    f"[JPMAI] 获取锚点消息 {anchor_message_id} 失败: {e}，尝试查找最近发言"
                )

        # 如果没有锚点消息，则查找最近发言
        if not target_message:
            target_message = await get_target_user_last_message(
                bot, message.chat.id, keyword_config["target_user_id"]
            )

        if target_message and target_message.from_user:
            if use_dual:
                # 双人模式：确定第二个名字
                if has_param:
                    second_name = param
                elif is_reply_to_someone and message.reply_to_message.from_user:
                    replied_user = message.reply_to_message.from_user
                    second_name = (
                        replied_user.username
                        or replied_user.first_name
                        or str(replied_user.id)
                    )
                else:
                    second_name = None

                if second_name:
                    logs.info(
                        f"[JPMAI] `/{keyword}` 触发双人模式: {keyword} + {second_name}"
                    )
                    reply_text = await generator.generate_dual(keyword, second_name)
                else:
                    logs.info(f"[JPMAI] `/{keyword}` 触发单人模式: {keyword}")
                    reply_text = await generator.generate_single(keyword)
            else:
                # 单人模式
                logs.info(f"[JPMAI] `/{keyword}` 触发单人模式: {keyword}")
                reply_text = await generator.generate_single(keyword)

            await target_message.reply(reply_text)

            # 记录触发时间
            trigger_log.record_trigger(keyword)

            # 删除触发的命令消息
            with contextlib.suppress(Exception):
                await message.delete()
        else:
            logs.warning(
                f"[JPMAI] 未找到目标用户 {keyword_config['target_user_id']} 的回复目标"
            )
