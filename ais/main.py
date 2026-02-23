"""
AI 查询插件 - 向AI模型提问并返回回复

支持：
- OpenAI 格式的 API 调用
- MCP（Model Context Protocol）工具集成（可选）
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiohttp

from pagermaid.listener import listener
from pagermaid.enums import Message
from pagermaid.utils import logs

# 尝试导入 MCP 客户端（可选依赖）
try:
    from mcp_client import MCPClient, ConfigManager
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    MCPClient = None
    ConfigManager = None

# 数据目录和配置文件路径
DATA_DIR = Path("ai_query")
DATA_FILE = DATA_DIR / "config.json"
PENDING_SELECTION = {}  # 待选择的模型列表消息

# MCP 相关
if HAS_MCP:
    mcp_client: Optional[MCPClient] = None
    mcp_config_manager: Optional[ConfigManager] = None


def load_config() -> dict:
    """加载AI配置"""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            logs.error(f"加载配置失败: {e}")
            return {}
    return {}


def save_config(config: dict) -> bool:
    """保存AI配置"""
    try:
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        DATA_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except Exception as e:
        logs.error(f"保存配置失败: {e}")
        return False


def get_current_model(config: dict) -> str:
    """获取当前使用的模型"""
    return config.get("current_model", "") or config.get("model", "")


async def call_ai_api(
    api_url: str, api_key: str, model: str, prompt: str
) -> Optional[str]:
    """调用AI API获取回复"""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 支持OpenAI格式的API
        # 添加system message以禁用thinking过程，只输出最终答案
        data = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "请直接回答用户的问题，不要展示思考过程或推理步骤，只输出最终的简洁答案。",
                },
                {"role": "user", "content": prompt},
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url, headers=headers, json=data, timeout=60
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    # 尝试从不同格式中提取回复
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                    elif "message" in result:
                        return result["message"]["content"]
                    elif "content" in result:
                        return result["content"]
                    else:
                        return str(result)
                else:
                    error_text = await response.text()
                    logs.error(f"API调用失败: {response.status} - {error_text}")
                    return f"API调用失败: {response.status}"
    except asyncio.TimeoutError:
        return "请求超时"
    except Exception as e:
        logs.error(f"调用AI API异常: {e}")
        return f"调用异常: {str(e)}"


@listener(command="ais", description="向AI模型提问", parameters="[文本]")
async def ais_query(message: Message):
    """处理AI查询命令"""
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
        mcp_status = "✅ 已启用" if HAS_MCP else "⚪ 未安装"

        help_text = f"""🤖 AI 查询插件帮助

📝 基础命令：
  ,ais <文本>              - 向AI提问
  ,ais help                - 显示此帮助

⚙️ API 配置：
  ,ais set <api_url> <api_key>  - 设置API基础配置

🤖 模型管理：
  ,ais models              - 查看/切换模型
  ,ais model add <名称>    - 添加新模型
  ,ais model del <名称>    - 删除模型

{'🔌 MCP 管理：' if HAS_MCP else ''}
{'  ,ais mcp list          - 列出所有MCP服务器' if HAS_MCP else ''}
{'  ,ais mcp add-raw <名称> <JSON>  - 添加MCP服务器（推荐，直接粘贴JSON）' if HAS_MCP else ''}
{'  ,ais mcp add <名称> <命令> [参数]  - 添加MCP服务器（简单）' if HAS_MCP else ''}
{'  ,ais mcp add-json <名称>  - 添加MCP服务器（回复方式）' if HAS_MCP else ''}
{'  ,ais mcp remove <名称>  - 删除MCP服务器' if HAS_MCP else ''}
{'  ,ais mcp enable <名称>  - 启用MCP服务器' if HAS_MCP else ''}
{'  ,ais mcp disable <名称> - 禁用MCP服务器' if HAS_MCP else ''}
{'  ,ais mcp tools         - 列出所有可用工具' if HAS_MCP else ''}

📌 MCP 状态：{mcp_status}

💡 使用示例：
  ,ais 今天天气怎么样
  ,ais set https://api.openai.com/v1/chat/completions sk-xxx
  ,ais model add gpt-3.5-turbo"""
        await message.edit(help_text)
        return

    # 检查是否是models命令
    if text.strip().lower() == "models":
        config = load_config()

        # 检查API配置是否存在
        if "api_url" not in config or "api_key" not in config:
            await message.edit(
                "⚠️ 请先配置API\n\n使用命令: ,ais set <api_url> <api_key>"
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        # 获取所有模型
        models = config.get("models", [])
        current_model = get_current_model(config)

        if not models:
            # 如果没有模型，提示添加
            await message.edit(
                "📋 模型列表为空\n\n"
                "当前未添加任何模型，请使用以下命令添加：\n"
                ",ais model add <模型名称>\n\n"
                "示例: ,ais model add gpt-3.5-turbo"
            )
            await asyncio.sleep(5)
            await message.delete()
            return

        # 构建模型列表消息
        models_list = ""
        for i, model in enumerate(models, 1):
            if model == current_model:
                models_list += f"✅ **{i}. {model}** (当前使用)\n"
            else:
                models_list += f"   {i}. {model}\n"

        help_text = f"""🤖 模型列表

📋 可用模型：
{models_list}

💡 操作说明：
  • 切换模型: 回复此消息并输入序号
  • 添加模型: ,ais model add <模型名称>
  • 删除模型: ,ais model del <模型名称>

📌 回复消息输入 **1-9** 的序号快速切换模型"""

        sent_msg = await message.edit(help_text)

        # 记录待选择的消息
        chat_id = str(message.chat.id)
        PENDING_SELECTION[chat_id] = {
            "models": models,
            "message_id": sent_msg.id,
        }
        return

    # 检查是否是model子命令
    if text.strip().lower().startswith("model"):
        parts = text.strip().split()
        action = parts[1].lower() if len(parts) > 1 else ""
        model_name = parts[2] if len(parts) > 2 else ""

        if action == "add":
            # 添加新模型
            if not model_name:
                await message.edit("❌ 请指定模型名称\n\n示例: ,ais model add gpt-4")
                await asyncio.sleep(3)
                await message.delete()
                return

            config = load_config()

            # 检查API配置是否存在
            if "api_url" not in config or "api_key" not in config:
                await message.edit(
                    "⚠️ 请先配置API\n\n使用命令: ,ais set <api_url> <api_key>"
                )
                await asyncio.sleep(3)
                await message.delete()
                return

            models = config.get("models", [])

            if model_name in models:
                await message.edit(f"⚠️ 模型 '{model_name}' 已存在")
                await asyncio.sleep(3)
                await message.delete()
                return

            models.append(model_name)
            config["models"] = models

            # 如果是第一个模型，自动设为当前模型
            if len(models) == 1:
                config["current_model"] = model_name

            if save_config(config):
                await message.edit(
                    f"✅ 成功添加模型: {model_name}\n\n"
                    f"📋 当前模型列表：\n" + "\n".join([f"  • {m}" for m in models])
                )
            else:
                await message.edit("❌ 保存配置失败")

            await asyncio.sleep(3)
            await message.delete()
            return

        elif action == "del" or action == "delete" or action == "rm":
            # 删除模型
            if not model_name:
                await message.edit(
                    "❌ 请指定要删除的模型名称\n\n示例: ,ais model del gpt-3.5-turbo"
                )
                await asyncio.sleep(3)
                await message.delete()
                return

            config = load_config()
            models = config.get("models", [])

            if model_name not in models:
                await message.edit(f"⚠️ 模型 '{model_name}' 不存在")
                await asyncio.sleep(3)
                await message.delete()
                return

            if len(models) <= 1:
                await message.edit("⚠️ 至少保留一个模型")
                await asyncio.sleep(3)
                await message.delete()
                return

            models.remove(model_name)
            config["models"] = models

            # 如果删除的是当前模型，切换到第一个
            if config.get("current_model") == model_name:
                config["current_model"] = models[0]

            if save_config(config):
                await message.edit(
                    f"✅ 已删除模型: {model_name}\n\n"
                    f"📋 当前模型列表：\n" + "\n".join([f"  • {m}" for m in models])
                )
            else:
                await message.edit("❌ 保存配置失败")

            await asyncio.sleep(3)
            await message.delete()
            return

        else:
            # 未知的model子命令
            await message.edit(
                "❌ 未知的model子命令\n\n"
                "可用命令：\n"
                "  • ,ais model add <名称> - 添加模型\n"
                "  • ,ais model del <名称> - 删除模型\n"
                "  • ,ais models - 通过序号选择模型"
            )
            await asyncio.sleep(3)
            await message.delete()
            return

    # 检查是否是 MCP 子命令
    if HAS_MCP and text.strip().lower().startswith("mcp"):
        await handle_mcp_command(message, text.strip())
        return

    # 检查是否是配置命令
    if text.strip().lower().startswith("set"):
        # 提取配置参数
        parts = text.strip()[3:].strip().split()

        if len(parts) != 2:
            await message.edit(
                "❌ 配置格式错误\n\n"
                "正确格式: ,ais set <api_url> <api_key>\n\n"
                "示例: ,ais set https://api.openai.com/v1/chat/completions sk-xxx"
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        api_url, api_key = parts

        # 加载现有配置
        config = load_config()

        # 保存API配置，保留现有的模型配置
        config["api_url"] = api_url
        config["api_key"] = api_key

        # 如果没有模型列表，使用model字段作为当前模型
        if "model" in config and "models" not in config:
            config["models"] = [config["model"]]
            config["current_model"] = config["model"]
            del config["model"]

        if save_config(config):
            current_model = get_current_model(config)
            await message.edit(
                f"✅ API配置保存成功！\n\n"
                f"🔗 API URL: {api_url}\n"
                f"🔑 API Key: {api_key[:8]}...\n"
                f"🤖 当前模型: {current_model}\n\n"
                f"💡 使用 ,ais model add <模型名> 添加更多模型"
            )
        else:
            await message.edit("❌ 配置保存失败，请重试")

        await asyncio.sleep(3)
        await message.delete()
        return

    # 加载配置
    config = load_config()

    # 检查API配置是否完整
    if "api_url" not in config or "api_key" not in config:
        await message.edit("⚠️ 请先配置API\n\n使用命令: ,ais set <api_url> <api_key>")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 检查是否有模型配置
    models = config.get("models", [])
    if not models:
        await message.edit(
            "⚠️ 请先添加模型\n\n"
            "使用命令: ,ais model add <模型名>\n\n"
            "示例: ,ais model add gpt-3.5-turbo"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    # 调用AI API（优先尝试 MCP，如果可用）
    current_model = get_current_model(config)

    # 尝试使用 MCP 增强查询（如果可用）
    mcp_result = None
    if HAS_MCP:
        try:
            client = get_mcp_client()
            if client and client.is_ready:
                await message.edit(
                    f"🔌 正在通过 MCP 处理...\n\n问题: {text}"
                )
                mcp_result = await client.smart_call(text)
        except Exception as e:
            logs.warning(f"MCP 调用失败，降级到 API: {e}")
            mcp_result = None

    # 如果 MCP 不可用或调用失败，使用原有 API
    if mcp_result:
        await message.edit(f"🔌 MCP 回复:\n\n{mcp_result}")
    else:
        await message.edit(f"🤖 正在向AI提问...\n\n问题: {text}\n\n模型: {current_model}")

        result = await call_ai_api(
            api_url=config["api_url"],
            api_key=config["api_key"],
            model=current_model,
            prompt=text,
        )

        # 显示结果
        if (
            result
            and not result.startswith("API调用失败")
            and not result.startswith("调用异常")
            and not result == "请求超时"
        ):
            await message.edit(f"🤖 AI 回复（{current_model}）：\n\n{result}")
        else:
            await message.edit("❌ AI回复获取失败，请检查配置或网络连接")


@listener(incoming=True, outgoing=True)
async def model_selection_handler(message: Message):
    """监听模型选择回复"""
    # 只处理回复消息
    if not message.reply_to_message:
        return

    chat_id = str(message.chat.id)

    # 检查是否有待处理的模型选择
    if chat_id not in PENDING_SELECTION:
        return

    selection_data = PENDING_SELECTION[chat_id]
    models = selection_data["models"]

    # 获取用户输入的序号
    user_text = (message.text or "").strip()

    # 只处理单数字符（1-9）
    if not user_text.isdigit() or len(user_text) != 1:
        return

    choice = int(user_text)

    if choice < 1 or choice > len(models):
        await message.reply_to_message.edit(
            f"❌ 无效序号，请输入 1-{len(models)} 之间的数字"
        )
        # 清理待选择状态
        del PENDING_SELECTION[chat_id]
        await message.delete()
        return

    # 获取选择的模型
    selected_model = models[choice - 1]
    current_model = get_current_model(load_config())

    # 如果选择的是当前模型
    if selected_model == current_model:
        await message.reply_to_message.edit(f"🤖 当前已是模型: **{selected_model}**")
        # 清理待选择状态
        del PENDING_SELECTION[chat_id]
        await message.delete()
        return

    # 更新配置
    config = load_config()
    config["current_model"] = selected_model

    if save_config(config):
        await message.reply_to_message.edit(
            f"✅ 已切换到模型: **{selected_model}**\n\n(原模型: {current_model})"
        )
    else:
        await message.reply_to_message.edit("❌ 切换失败")

    # 清理待选择状态
    del PENDING_SELECTION[chat_id]
    await message.delete()


# ============================================================================
# MCP 配置管理函数
# ============================================================================

def get_mcp_client() -> Optional[MCPClient]:
    """获取或创建 MCP 客户端实例"""
    global mcp_client, mcp_config_manager

    if not HAS_MCP:
        return None

    if mcp_client is None:
        mcp_config_manager = ConfigManager()
        mcp_client = MCPClient()

    return mcp_client


async def handle_mcp_command(message: Message, text: str):
    """处理 MCP 配置命令"""
    parts = text.split()
    action = parts[1].lower() if len(parts) > 1 else ""

    if action == "list":
        await mcp_list_servers(message)
    elif action == "add":
        await mcp_add_server(message, parts)
    elif action == "add-json":
        await mcp_add_server_json(message)
    elif action == "add-raw":
        # 新增：直接在命令后面粘贴 JSON
        await mcp_add_server_raw(message, text)
    elif action == "remove" or action == "rm" or action == "del":
        await mcp_remove_server(message, parts)
    elif action == "enable":
        await mcp_enable_server(message, parts)
    elif action == "disable":
        await mcp_disable_server(message, parts)
    elif action == "tools":
        await mcp_list_tools(message)
    elif action == "reload":
        await mcp_reload(message)
    elif action == "import":
        await mcp_import_config(message, parts)
    else:
        await mcp_show_help(message)


async def mcp_show_help(message: Message):
    """显示 MCP 帮助信息"""
    help_text = """🔌 MCP 配置管理

📝 可用命令：
  ,ais mcp list              - 列出所有MCP服务器
  ,ais mcp add-raw <名称> <JSON>  - 添加MCP服务器（推荐）
  ,ais mcp add <名称> <命令> [参数]  - 添加MCP服务器（简单）
  ,ais mcp add-json <名称>   - 添加MCP服务器（回复方式）
  ,ais mcp remove <名称>      - 删除MCP服务器
  ,ais mcp enable <名称>      - 启用MCP服务器
  ,ais mcp disable <名称>     - 禁用MCP服务器
  ,ais mcp tools             - 列出所有可用工具
  ,ais mcp reload            - 重新加载MCP配置
  ,ais mcp import <路径>     - 从文件导入配置

💡 配置示例：
  # 推荐方式（一条消息完成，支持环境变量）
  ,ais mcp add-raw minimax {"command":"uvx","args":["minimax-coding-plan-mcp","-y"],"env":{...}}

  # 简单方式（无环境变量）
  ,ais mcp add fs npx -y @modelcontextprotocol/server-filesystem /path

📌 配置文件：ais/mcp_config.json"""
    await message.edit(help_text)


async def mcp_list_servers(message: Message):
    """列出所有 MCP 服务器"""
    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    config_manager = client.config_manager
    servers = config_manager.list_servers()

    if not servers:
        await message.edit(
            "📋 MCP 服务器列表\n\n"
            "暂未配置任何MCP服务器\n\n"
            "使用 ,ais mcp add 添加服务器"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    # 构建服务器列表
    lines = ["📋 MCP 服务器列表\n\n"]
    for server in servers:
        status = "✅" if server["enabled"] else "⏸️"
        default = " (默认)" if server["is_default"] else ""
        type_emoji = {"stdio": "💻", "SSE": "🌐", "module": "📦"}.get(server["type"], "❓")

        lines.append(
            f"{status} **{server['name']}** {default}\n"
            f"   {type_emoji} 类型: {server['type']}"
        )

        # 显示配置详情（隐藏敏感信息）
        config = server["config"]
        if "command" in config:
            cmd = config["command"]
            args = " ".join(config.get("args", []))
            # 截断过长的命令
            if len(args) > 40:
                args = args[:37] + "..."
            lines.append(f"   命令: {cmd} {args}")
        elif "url" in config:
            url = config["url"]
            lines.append(f"   URL: {url}")

        lines.append("")

    await message.edit("\n".join(lines))


async def mcp_add_server(message: Message, parts: list):
    """添加 MCP 服务器"""
    if len(parts) < 4:
        await message.edit(
            "❌ 参数不足\n\n"
            "格式: ,ais mcp add <名称> <命令> [参数]\n\n"
            "示例:\n"
            "  ,ais mcp add fs npx -y @modelcontextprotocol/server-filesystem /path\n"
            "  ,ais mcp add search npx -y @modelcontextprotocol/server-brave-search\n\n"
            "如需设置环境变量，请使用:\n"
            "  ,ais mcp add-json <名称> <JSON配置>"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    name = parts[2]
    command = parts[3]
    args = parts[4:] if len(parts) > 4 else []

    # 检查是否是 URL 方式
    if command == "--url" and args:
        config = {"url": args[0], "enabled": True}
    else:
        config = {
            "command": command,
            "args": args,
            "enabled": True
        }

    config_manager = client.config_manager
    if config_manager.add_server(name, config):
        await message.edit(
            f"✅ 成功添加 MCP 服务器: {name}\n\n"
            f"命令: {command} {' '.join(args)}\n\n"
            f"使用 ,ais mcp list 查看所有服务器\n"
            f"使用 ,ais mcp tools 查看可用工具"
        )
    else:
        await message.edit("❌ 添加失败")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_add_server_json(message: Message):
    """通过 JSON 添加 MCP 服务器（支持环境变量）"""
    # 检查是否回复了消息
    if not message.reply_to_message:
        await message.edit(
            "❌ 请回复包含 JSON 配置的消息\n\n"
            "格式: ,ais mcp add-json <名称>\n\n"
            "然后回复此消息，粘贴 JSON 配置:\n"
            "{\n"
            '  "command": "uvx",\n'
            '  "args": ["minimax-coding-plan-mcp", "-y"],\n'
            '  "env": {"KEY": "value"}\n'
            "}"
        )
        await asyncio.sleep(5)
        await message.delete()
        return

    # 检查回复的消息是否有文本内容
    reply_text = message.reply_to_message.text or ""
    if not reply_text.strip():
        await message.edit(
            "❌ 回复的消息不包含文本\n\n"
            "请回复包含 JSON 配置的文本消息"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 获取名称
    parts = message.text.split()
    if len(parts) < 3:
        await message.edit("❌ 请指定服务器名称\n\n格式: ,ais mcp add-json <名称>")
        await asyncio.sleep(3)
        await message.delete()
        return

    name = parts[2]

    # 解析 JSON
    try:
        json_text = reply_text
        # 提取 JSON（如果消息中有其他文本）
        import re
        json_match = re.search(r'\{[\s\S]*\}', json_text)
        if json_match:
            json_text = json_match.group(0)

        config = json.loads(json_text)
    except json.JSONDecodeError as e:
        await message.edit(f"❌ JSON 解析失败: {str(e)}\n\n请检查 JSON 格式是否正确")
        await asyncio.sleep(3)
        await message.delete()
        return
    except Exception as e:
        await message.edit(f"❌ 读取失败: {str(e)}")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 验证必要字段
    if "command" not in config and "url" not in config:
        await message.edit("❌ 配置必须包含 command 或 url 字段")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 添加 enabled 标记
    config["enabled"] = True

    # 保存配置
    config_manager = client.config_manager
    if config_manager.add_server(name, config):
        # 统计配置内容
        info_parts = []
        if "command" in config:
            info_parts.append(f"命令: {config['command']} {' '.join(config.get('args', []))}")
        if "url" in config:
            info_parts.append(f"URL: {config['url']}")
        if "env" in config:
            env_count = len(config["env"])
            info_parts.append(f"环境变量: {env_count} 个")

        await message.edit(
            f"✅ 成功添加 MCP 服务器: {name}\n\n"
            + "\n".join(info_parts)
            + f"\n\n使用 ,ais mcp list 查看所有服务器"
        )
    else:
        await message.edit("❌ 添加失败")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_add_server_raw(message: Message, text: str):
    """直接在命令后面粘贴 JSON（最简单的方式）"""
    # 获取名称
    parts = text.split()
    if len(parts) < 3:
        await message.edit(
            "❌ 格式错误\n\n"
            "正确格式: ,ais mcp add-raw <名称> <JSON>\n\n"
            "示例:\n"
            ",ais mcp add-raw minimax {\"command\":\"uvx\",\"args\":[\"minimax-coding-plan-mcp\",\"-y\"],\"env\":{...}}"
        )
        await asyncio.sleep(5)
        await message.delete()
        return

    name = parts[2]

    # 提取 JSON（从名称后开始）
    import re
    # 查找第一个 { 及其之后的所有内容
    json_match = re.search(r'\{[\s\S]*\}', text)
    if not json_match:
        await message.edit(
            "❌ 未找到 JSON 配置\n\n"
            "请在命令后粘贴完整的 JSON 配置"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    json_text = json_match.group(0)

    # 解析 JSON
    try:
        config = json.loads(json_text)
    except json.JSONDecodeError as e:
        await message.edit(f"❌ JSON 解析失败: {str(e)}\n\n请检查 JSON 格式是否正确")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 验证必要字段
    if "command" not in config and "url" not in config:
        await message.edit("❌ 配置必须包含 command 或 url 字段")
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 添加 enabled 标记
    config["enabled"] = True

    # 保存配置
    config_manager = client.config_manager
    if config_manager.add_server(name, config):
        # 统计配置内容
        info_parts = []
        if "command" in config:
            info_parts.append(f"命令: {config['command']} {' '.join(config.get('args', []))}")
        if "url" in config:
            info_parts.append(f"URL: {config['url']}")
        if "env" in config:
            env_count = len(config["env"])
            info_parts.append(f"环境变量: {env_count} 个")

        await message.edit(
            f"✅ 成功添加 MCP 服务器: {name}\n\n"
            + "\n".join(info_parts)
            + f"\n\n使用 ,ais mcp list 查看所有服务器"
        )
    else:
        await message.edit("❌ 添加失败")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_remove_server(message: Message, parts: list):
    """删除 MCP 服务器"""
    if len(parts) < 3:
        await message.edit(
            "❌ 请指定要删除的服务器名称\n\n"
            "格式: ,ais mcp remove <名称>"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    name = parts[2]
    config_manager = client.config_manager

    if not config_manager.get_server(name):
        await message.edit(f"⚠️ 服务器 '{name}' 不存在")
        await asyncio.sleep(3)
        await message.delete()
        return

    if config_manager.remove_server(name):
        await message.edit(f"✅ 已删除 MCP 服务器: {name}")
    else:
        await message.edit("❌ 删除失败")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_enable_server(message: Message, parts: list):
    """启用 MCP 服务器"""
    if len(parts) < 3:
        await message.edit(
            "❌ 请指定要启用的服务器名称\n\n"
            "格式: ,ais mcp enable <名称>"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    name = parts[2]
    config_manager = client.config_manager

    if config_manager.enable_server(name):
        await message.edit(f"✅ 已启用 MCP 服务器: {name}")
    else:
        await message.edit(f"⚠️ 服务器 '{name}' 不存在")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_disable_server(message: Message, parts: list):
    """禁用 MCP 服务器"""
    if len(parts) < 3:
        await message.edit(
            "❌ 请指定要禁用的服务器名称\n\n"
            "格式: ,ais mcp disable <名称>"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    name = parts[2]
    config_manager = client.config_manager

    if config_manager.disable_server(name):
        await message.edit(f"✅ 已禁用 MCP 服务器: {name}")
    else:
        await message.edit(f"⚠️ 服务器 '{name}' 不存在")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_list_tools(message: Message):
    """列出所有可用工具"""
    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    # 确保客户端已初始化
    await client.wait_ready(timeout=10)

    tools = client.list_tools(group_by_mcp=True)

    if not tools:
        await message.edit(
            "🔧 MCP 工具列表\n\n"
            "暂无可用工具\n\n"
            "请先添加并启用 MCP 服务器"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    # 构建工具列表
    lines = ["🔧 MCP 工具列表\n\n"]

    for group in tools:
        mcp_name = group["mcp_server"]
        tool_count = group["tool_count"]
        lines.append(f"📦 **{mcp_name}** ({tool_count} 个工具)")

        for tool in group["tools"][:10]:  # 每个 MCP 最多显示 10 个
            lines.append(f"  • {tool['name']}: {tool['description'][:50]}...")

        if tool_count > 10:
            lines.append(f"  ... 还有 {tool_count - 10} 个工具")

        lines.append("")

    await message.edit("\n".join(lines))


async def mcp_reload(message: Message):
    """重新加载 MCP 配置"""
    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    await message.edit("🔄 正在重新加载 MCP 配置...")

    success = await client.reload()

    if success:
        await message.edit("✅ MCP 配置已重新加载")
    else:
        await message.edit("⚠️ 未配置任何 MCP 服务器")

    await asyncio.sleep(3)
    await message.delete()


async def mcp_import_config(message: Message, parts: list):
    """从文件导入 MCP 配置"""
    if len(parts) < 3:
        await message.edit(
            "❌ 请指定配置文件路径\n\n"
            "格式: ,ais mcp import <文件路径>\n\n"
            "支持 VSCode/Claude Desktop 的 claude_desktop_config.json 格式"
        )
        await asyncio.sleep(3)
        await message.delete()
        return

    client = get_mcp_client()
    if not client:
        await message.edit("❌ MCP 模块未安装")
        await asyncio.sleep(3)
        await message.delete()
        return

    config_path = Path(parts[2])

    if not config_path.exists():
        await message.edit(f"⚠️ 文件不存在: {parts[2]}")
        await asyncio.sleep(3)
        await message.delete()
        return

    try:
        imported = client.config_manager.import_from_vscode_config(config_path)

        if imported:
            await message.edit(
                f"✅ 成功导入 {len(imported)} 个 MCP 服务器:\n\n"
                + "\n".join([f"  • {name}" for name in imported])
                + f"\n\n使用 ,ais mcp list 查看详情"
            )
        else:
            await message.edit("⚠️ 配置文件中未找到 MCP 服务器")

    except Exception as e:
        await message.edit(f"❌ 导入失败: {str(e)}")

    await asyncio.sleep(5)
    await message.delete()
