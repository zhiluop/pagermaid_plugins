"""
示例插件 - PagerMaid-Pyro 插件开发模板
文件名: example_plugin.py
"""

from pagermaid.listener import listener
from pagermaid.hook import Hook
from pagermaid.enums import Message
from pagermaid.utils import logs


# 使用 listener 装饰器注册命令
# 命令使用方式: ,hello 或 /hello (sudo)
@listener(
    command="hello",  # 命令名称
    description="向用户打招呼",  # 命令描述
    parameters="[名字]",  # 参数说明
    is_plugin=True,  # 标识为插件
    outgoing=True,  # 响应自己的消息
    incoming=False,  # 不响应传入消息
    priority=50,  # 执行优先级 (0-100)
)
async def hello_command(message: Message):
    """处理 hello 命令"""
    # 获取命令参数
    name = message.arguments if message.arguments else "世界"

    # 编辑消息回复用户
    await message.edit(f"你好, {name}!")


# 启动时执行的钩子
@Hook.on_startup()
async def plugin_startup():
    """插件初始化时执行"""
    logs.info("示例插件已加载")


# 关闭时执行的钩子
@Hook.on_shutdown()
async def plugin_shutdown():
    """插件关闭时执行"""
    logs.info("示例插件已卸载")
