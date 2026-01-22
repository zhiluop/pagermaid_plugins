"""
AI 查询插件 - 向AI模型提问并返回回复
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiohttp

from pagermaid.listener import listener
from pagermaid.enums import Message
from pagermaid.utils import logs

# 数据目录和配置文件路径
DATA_DIR = Path("ai_query")
DATA_FILE = DATA_DIR / "config.json"
PENDING_SELECTION = {}  # 待选择的模型列表消息


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
        help_text = """🤖 AI 查询插件帮助

📝 命令格式：
  ,ais <文本>              - 向AI提问
  ,ais help                - 显示此帮助
  ,ais set <api_url> <api_key>  - 设置API基础配置
  ,ais models              - 查看/切换模型
  ,ais model add <model_name>   - 添加新模型
  ,ais model del <model_name>   - 删除模型

⚙️ 配置说明：
  使用 ,ais set 命令配置API基础信息：
  • api_url: AI服务的API地址
  • api_key: API访问密钥

💡 使用示例：
  ,ais 今天天气怎么样
  ,ais 如何学习Python编程
  ,ais set https://api.openai.com/v1/chat/completions sk-xxx
  ,ais model add gpt-3.5-turbo
  ,ais models

📌 注意：
  • 首次使用前需要先配置API
  • 支持OpenAI格式的API
  • 使用 ,ais models 可通过序号选择模型"""
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

    # 调用AI API
    current_model = get_current_model(config)
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
