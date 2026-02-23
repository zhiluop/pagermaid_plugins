"""
MCP 客户端模块 - 为 PagerMaid 插件提供 MCP 服务调用能力

此模块提供：
- MCP 服务器连接管理
- 工具自动发现和注册
- 统一的工具调用接口
- 优雅的降级机制
- 自动安装依赖（如果缺少）

使用示例：
    from mcp_client import MCPClient

    client = MCPClient()
    result = await client.call_tool("search_web", {"query": "..."})
"""

import subprocess
import sys

# 检查是否安装了 mcp 包
try:
    import mcp
    HAS_MCP_PKG = True
except ImportError:
    HAS_MCP_PKG = False
    # 尝试自动安装
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "mcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        # 重新尝试导入
        import mcp
        HAS_MCP_PKG = True
    except Exception:
        pass

from .client import MCPClient
from .config import load_config, save_config, ConfigManager
from .registry import ToolRegistry

__version__ = "0.1.0"
__all__ = ["MCPClient", "load_config", "save_config", "ConfigManager", "ToolRegistry", "HAS_MCP_PKG"]
