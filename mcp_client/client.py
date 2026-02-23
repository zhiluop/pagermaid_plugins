"""
MCP 客户端主模块

提供 MCP 服务器连接、工具发现和调用功能
支持 stdio、SSE 等多种连接方式
采用懒加载模式，首次调用时初始化
"""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Union

from .config import ConfigManager, load_config
from .registry import ToolRegistry, SmartToolRouter


class MCPClient:
    """MCP 客户端 - 统一的 MCP 服务调用接口"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 MCP 客户端

        Args:
            config_path: 配置文件路径（可选）
        """
        self.config_manager = ConfigManager(config_path)
        self.registry = ToolRegistry()
        self.router = SmartToolRouter(self.registry)

        # 连接状态
        self._initialized = False
        self._initializing = False
        self._connections: Dict[str, Any] = {}  # {mcp_name: connection}
        self._ready_event = asyncio.Event()

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def is_ready(self) -> bool:
        """是否就绪（初始化完成或无配置）"""
        return self._ready_event.is_set()

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """
        等待客户端就绪

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否就绪
        """
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def initialize(self) -> bool:
        """
        初始化 MCP 客户端（懒加载）

        Returns:
            是否初始化成功
        """
        # 防止重复初始化
        if self._initializing:
            await self._ready_event.wait()
            return self._initialized

        if self._initialized:
            return True

        self._initializing = True

        try:
            # 获取启用的服务器配置
            servers = self.config_manager.get_enabled_servers()

            if not servers:
                # 没有配置任何 MCP 服务器，标记为就绪
                self._ready_event.set()
                return False

            # 连接各个 MCP 服务器并收集工具
            for name, config in servers.items():
                try:
                    await self._connect_and_discover(name, config)
                except Exception as e:
                    # 单个服务器连接失败不影响其他
                    pass

            # 构建关键词映射
            self.router.build_keyword_map()

            self._initialized = True
            self.registry.mark_initialized()
            return True

        finally:
            self._initializing = False
            self._ready_event.set()

    async def _connect_and_discover(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> None:
        """
        连接 MCP 服务器并发现工具

        Args:
            name: 服务器名称
            config: 服务器配置
        """
        connection = None

        # 根据配置类型选择连接方式
        if "url" in config:
            # SSE 方式
            connection = await self._connect_sse(config["url"])
        elif "command" in config:
            # stdio 方式
            connection = await self._connect_stdio(
                config["command"],
                config.get("args", []),
                config.get("env", {})
            )
        elif "module" in config:
            # Python 模块方式
            connection = await self._connect_module(config["module"])
        else:
            raise ValueError(f"Unknown config type for server {name}")

        # 保存连接
        self._connections[name] = connection

        # 发现工具
        tools = await self._discover_tools(connection, name)

        # 注册到注册表
        for tool in tools:
            self.registry.register(
                name=tool["name"],
                description=tool.get("description", ""),
                mcp_server=name,
                input_schema=tool.get("inputSchema", {})
            )

    async def _connect_stdio(
        self,
        command: str,
        args: List[str],
        env: Dict[str, str]
    ) -> Any:
        """
        通过 stdio 连接 MCP 服务器

        Args:
            command: 命令
            args: 参数列表
            env: 环境变量

        Returns:
            连接对象
        """
        # 创建子进程
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**__import__("os").environ, **env}
        )

        return {"type": "stdio", "process": process}

    async def _connect_sse(self, url: str) -> Any:
        """
        通过 SSE 连接 MCP 服务器

        Args:
            url: SSE URL

        Returns:
            连接对象
        """
        import aiohttp

        session = aiohttp.ClientSession()
        return {"type": "sse", "url": url, "session": session}

    async def _connect_module(self, module_path: str) -> Any:
        """
        通过 Python 模块连接 MCP 服务器

        Args:
            module_path: 模块路径

        Returns:
            连接对象
        """
        # 动态导入模块
        parts = module_path.split(".")
        module = __import__(module_path)
        for part in parts[1:]:
            module = getattr(module, part)

        return {"type": "module", "module": module}

    async def _discover_tools(
        self,
        connection: Any,
        server_name: str
    ) -> List[Dict[str, Any]]:
        """
        从 MCP 服务器发现工具

        Args:
            connection: 连接对象
            server_name: 服务器名称

        Returns:
            工具列表
        """
        # 这里需要实现实际的 MCP 协议通信
        # 由于 MCP 协议较复杂，这里先返回模拟数据

        # 实际实现需要：
        # 1. 发送 tools/list 请求
        # 2. 解析响应
        # 3. 返回工具列表

        # 模拟返回工具列表
        return await self._simulate_discovery(connection, server_name)

    async def _simulate_discovery(
        self,
        connection: Any,
        server_name: str
    ) -> List[Dict[str, Any]]:
        """
        模拟工具发现（用于测试）

        实际使用时需要替换为真实的 MCP 协议通信
        """
        conn_type = connection.get("type", "")

        if conn_type == "stdio":
            # 从 stdio 读取工具列表
            command = connection.get("process", {}).get("args", [""])

            if "filesystem" in " ".join(command):
                return [
                    {
                        "name": "read_file",
                        "description": "读取文件内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "write_file",
                        "description": "写入文件内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "list_directory",
                        "description": "列出目录内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"}
                            }
                        }
                    }
                ]

            elif "search" in " ".join(command):
                return [
                    {
                        "name": "search_web",
                        "description": "搜索网络内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            }
                        }
                    }
                ]

        elif conn_type == "sse":
            # SSE 方式
            return []

        return []

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Optional[str]:
        """
        调用指定的 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果，失败返回 None
        """
        # 确保已初始化
        if not self._initialized:
            await self.initialize()

        # 查找工具
        tool_info = self.registry.get_tool(tool_name)
        if not tool_info:
            return None

        # 获取连接
        connection = self._connections.get(tool_info.mcp_server)
        if not connection:
            return None

        # 调用工具
        return await self._execute_tool(connection, tool_name, arguments)

    async def _execute_tool(
        self,
        connection: Any,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Optional[str]:
        """
        执行工具调用

        Args:
            connection: 连接对象
            tool_name: 工具名称
            arguments: 参数

        Returns:
            执行结果
        """
        conn_type = connection.get("type", "")

        # 实际实现需要通过 MCP 协议调用工具
        # 这里返回模拟结果
        return f"工具 {tool_name} 已调用，参数: {json.dumps(arguments, ensure_ascii=False)}"

    async def smart_call(
        self,
        user_query: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        智能调用 - 根据用户查询自动选择合适的工具

        Args:
            user_query: 用户查询
            arguments: 可选的额外参数

        Returns:
            工具执行结果
        """
        # 确保已初始化
        if not self._initialized:
            success = await self.initialize()
            if not success:
                return None

        # 查找合适的工具
        tool_name = self.router.find_tool_for_query(user_query)
        if not tool_name:
            return None

        # 构建参数
        args = arguments or {}
        if "query" not in args and "path" not in args:
            # 尝试从查询中提取参数
            args["query"] = user_query

        # 调用工具
        return await self.call_tool(tool_name, args)

    async def reload(self) -> bool:
        """
        重新加载配置和连接

        Returns:
            是否重载成功
        """
        # 清理现有连接
        await self._cleanup()

        # 重置状态
        self._initialized = False
        self._initializing = False
        self._connections.clear()
        self.registry.clear()
        self._ready_event.clear()

        # 重新初始化
        return await self.initialize()

    async def _cleanup(self) -> None:
        """清理资源"""
        for name, connection in self._connections.items():
            try:
                if connection.get("type") == "stdio":
                    process = connection.get("process")
                    if process:
                        process.terminate()
                        await process.wait()
                elif connection.get("type") == "sse":
                    session = connection.get("session")
                    if session:
                        await session.close()
            except Exception:
                pass

        self._connections.clear()

    async def close(self) -> None:
        """关闭客户端"""
        await self._cleanup()

    def list_tools(
        self,
        group_by_mcp: bool = False
    ) -> List[Dict[str, Any]]:
        """
        列出所有可用工具

        Args:
            group_by_mcp: 是否按 MCP 分组

        Returns:
            工具列表
        """
        return self.registry.list_tools(group_by_mcp=group_by_mcp)

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            工具信息
        """
        tool = self.registry.get_tool(tool_name)
        if tool:
            return tool.to_dict()
        return None


# 创建全局客户端实例
_global_client: Optional[MCPClient] = None


def get_client() -> MCPClient:
    """获取全局 MCP 客户端实例"""
    global _global_client
    if _global_client is None:
        _global_client = MCPClient()
    return _global_client


# 便捷函数
async def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    """调用 MCP 工具（使用全局客户端）"""
    client = get_client()
    return await client.call_tool(tool_name, arguments)


async def smart_call(user_query: str, arguments: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """智能调用 MCP 工具（使用全局客户端）"""
    client = get_client()
    return await client.smart_call(user_query, arguments)
