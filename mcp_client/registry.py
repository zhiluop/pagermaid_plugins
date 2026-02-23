"""
MCP 工具注册表模块

负责收集、管理和查找 MCP 工具
支持从多个 MCP 服务器自动发现工具
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional


class ToolRegistry:
    """MCP 工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, ToolInfo] = {}
        self._mcp_tools: Dict[str, List[str]] = {}  # {mcp_name: [tool_names]}
        self._initialized = False

    class ToolInfo:
        """工具信息"""

        def __init__(
            self,
            name: str,
            description: str,
            mcp_server: str,
            input_schema: Optional[Dict[str, Any]] = None
        ):
            self.name = name
            self.description = description
            self.mcp_server = mcp_server
            self.input_schema = input_schema or {}

        def to_dict(self) -> Dict[str, Any]:
            """转换为字典"""
            return {
                "name": self.name,
                "description": self.description,
                "mcp_server": self.mcp_server,
                "input_schema": self.input_schema
            }

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def tools(self) -> Dict[str, ToolInfo]:
        """获取所有工具"""
        return self._tools

    @property
    def tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

    def register(
        self,
        name: str,
        description: str,
        mcp_server: str,
        input_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            description: 工具描述
            mcp_server: MCP 服务器名称
            input_schema: 输入参数 schema
        """
        tool_info = self.ToolInfo(
            name=name,
            description=description,
            mcp_server=mcp_server,
            input_schema=input_schema
        )
        self._tools[name] = tool_info

        # 维护 MCP 服务器到工具的映射
        if mcp_server not in self._mcp_tools:
            self._mcp_tools[mcp_server] = []
        if name not in self._mcp_tools[mcp_server]:
            self._mcp_tools[mcp_server].append(name)

    def unregister(self, name: str) -> bool:
        """
        注销工具

        Args:
            name: 工具名称

        Returns:
            是否注销成功
        """
        if name not in self._tools:
            return False

        tool_info = self._tools[name]
        mcp_server = tool_info.mcp_server

        # 从 MCP 服务器映射中移除
        if mcp_server in self._mcp_tools and name in self._mcp_tools[mcp_server]:
            self._mcp_tools[mcp_server].remove(name)

        del self._tools[name]
        return True

    def unregister_by_mcp(self, mcp_server: str) -> int:
        """
        注销指定 MCP 服务器的所有工具

        Args:
            mcp_server: MCP 服务器名称

        Returns:
            注销的工具数量
        """
        if mcp_server not in self._mcp_tools:
            return 0

        tool_names = self._mcp_tools[mcp_server][:]
        count = 0
        for name in tool_names:
            if self.unregister(name):
                count += 1

        del self._mcp_tools[mcp_server]
        return count

    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """获取工具信息"""
        return self._tools.get(name)

    def find_tools(
        self,
        query: str,
        limit: int = 5
    ) -> List[ToolInfo]:
        """
        根据查询关键词查找工具

        Args:
            query: 查询关键词
            limit: 最多返回数量

        Returns:
            匹配的工具列表
        """
        query_lower = query.lower()
        results = []

        for tool in self._tools.values():
            # 在名称和描述中搜索
            if (
                query_lower in tool.name.lower() or
                query_lower in tool.description.lower()
            ):
                results.append(tool)

        # 按相关度排序（名称匹配优先）
        results.sort(
            key=lambda t: (
                query_lower not in t.name.lower(),
                t.name
            )
        )

        return results[:limit]

    def get_tools_by_mcp(self, mcp_server: str) -> List[ToolInfo]:
        """获取指定 MCP 服务器的所有工具"""
        tool_names = self._mcp_tools.get(mcp_server, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def list_tools(
        self,
        group_by_mcp: bool = False
    ) -> List[Dict[str, Any]]:
        """
        列出所有工具

        Args:
            group_by_mcp: 是否按 MCP 服务器分组

        Returns:
            工具信息列表
        """
        if group_by_mcp:
            # 按 MCP 分组
            result = []
            for mcp_name, tool_names in self._mcp_tools.items():
                tools = [
                    self._tools[name].to_dict()
                    for name in tool_names
                    if name in self._tools
                ]
                result.append({
                    "mcp_server": mcp_name,
                    "tool_count": len(tools),
                    "tools": tools
                })
            return result
        else:
            # 扁平化列表
            return [tool.to_dict() for tool in self._tools.values()]

    def format_tools_list(self, group_by_mcp: bool = False) -> str:
        """
        格式化工具列表为可读文本

        Args:
            group_by_mcp: 是否按 MCP 服务器分组

        Returns:
            格式化的工具列表文本
        """
        if group_by_mcp:
            lines = []
            for mcp_name, tool_names in self._mcp_tools.items():
                lines.append(f"\n📦 {mcp_name}:")
                for name in tool_names:
                    if name in self._tools:
                        tool = self._tools[name]
                        lines.append(f"  • {tool.name}: {tool.description[:60]}...")
            return "\n".join(lines)
        else:
            lines = []
            for tool in self._tools.values():
                lines.append(f"• {tool.name}: {tool.description[:60]}...")
            return "\n".join(lines)

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
        self._mcp_tools.clear()
        self._initialized = False

    def mark_initialized(self) -> None:
        """标记为已初始化"""
        self._initialized = True


class SmartToolRouter:
    """智能工具路由器 - 根据用户输入选择合适的工具"""

    def __init__(self, registry: ToolRegistry):
        """
        初始化路由器

        Args:
            registry: 工具注册表
        """
        self.registry = registry
        # 关键词到工具的映射
        self._keyword_map: Dict[str, str] = {}

    def build_keyword_map(self) -> None:
        """构建关键词映射（用于简单路由）"""
        self._keyword_map = {}

        for tool in self.registry.tools.values():
            # 从工具描述中提取关键词
            desc = tool.description.lower()

            # 常见关键词映射
            keywords = self._extract_keywords(desc, tool.name)
            for kw in keywords:
                if kw not in self._keyword_map:
                    self._keyword_map[kw] = tool.name

    def _extract_keywords(self, description: str, tool_name: str) -> List[str]:
        """从描述中提取关键词"""
        keywords = []

        # 常见关键词模式
        keyword_patterns = {
            "search": ["search", "搜索", "查找", "find", "query"],
            "read": ["read", "读取", "get", "获取", "load"],
            "write": ["write", "写入", "save", "保存", "create"],
            "web": ["web", "网页", "website", "internet", "网络"],
            "file": ["file", "文件", "directory", "目录", "folder"],
            "image": ["image", "图片", "photo", "照片", "picture"],
            "weather": ["weather", "天气", "temperature", "温度"],
        }

        for category, patterns in keyword_patterns.items():
            if category in tool_name.lower() or any(p in description for p in patterns):
                keywords.extend(patterns)

        # 添加工具名本身
        keywords.append(tool_name.lower())

        return list(set(keywords))

    def find_tool_for_query(self, query: str) -> Optional[str]:
        """
        根据查询找到合适的工具

        Args:
            query: 用户查询

        Returns:
            工具名称，如果找不到则返回 None
        """
        query_lower = query.lower()

        # 1. 精确匹配
        if query_lower in self._keyword_map:
            return self._keyword_map[query_lower]

        # 2. 关键词匹配
        for keyword, tool_name in self._keyword_map.items():
            if keyword in query_lower:
                return tool_name

        # 3. 使用工具注册表的搜索
        results = self.registry.find_tools(query, limit=1)
        if results:
            return results[0].name

        return None
