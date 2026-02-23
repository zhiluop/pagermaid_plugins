"""
MCP 配置管理模块

负责 MCP 服务器的配置加载、保存和管理
支持多种配置格式：stdio (命令行)、SSE (HTTP)、Python 模块
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# 默认配置文件路径
DEFAULT_CONFIG_PATH = Path("ais/mcp_config.json")


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    加载 MCP 配置文件

    Args:
        path: 配置文件路径，默认为 ais/mcp_config.json

    Returns:
        配置字典，如果文件不存在返回空配置
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return {"servers": {}, "default_servers": []}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        # 确保基本结构存在
        if "servers" not in data:
            data["servers"] = {}
        if "default_servers" not in data:
            data["default_servers"] = []
        return data
    except Exception as e:
        # 配置文件损坏时返回空配置
        return {"servers": {}, "default_servers": []}


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> bool:
    """
    保存 MCP 配置到文件

    Args:
        config: 配置字典
        path: 配置文件路径，默认为 ais/mcp_config.json

    Returns:
        是否保存成功
    """
    config_path = path or DEFAULT_CONFIG_PATH

    try:
        # 确保目录存在
        config_path.parent.mkdir(exist_ok=True, parents=True)

        # 写入配置
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        return False


class ConfigManager:
    """MCP 配置管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config_cache = None

    @property
    def config(self) -> Dict[str, Any]:
        """获取配置（带缓存）"""
        if self._config_cache is None:
            self._config_cache = load_config(self.config_path)
        return self._config_cache

    def reload(self) -> Dict[str, Any]:
        """重新加载配置"""
        self._config_cache = None
        return self.config

    def save(self) -> bool:
        """保存当前配置"""
        if self._config_cache:
            result = save_config(self._config_cache, self.config_path)
            return result
        return False

    def get_servers(self) -> Dict[str, Any]:
        """获取所有服务器配置"""
        return self.config.get("servers", {})

    def get_enabled_servers(self) -> Dict[str, Any]:
        """获取所有启用的服务器配置"""
        servers = self.config.get("servers", {})
        return {
            name: cfg
            for name, cfg in servers.items()
            if cfg.get("enabled", True)
        }

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定服务器配置"""
        return self.config.get("servers", {}).get(name)

    def add_server(
        self,
        name: str,
        config: Dict[str, Any],
        set_default: bool = False
    ) -> bool:
        """
        添加或更新服务器配置

        Args:
            name: 服务器名称
            config: 服务器配置（command/args 或 url）
            set_default: 是否添加到默认服务器列表

        Returns:
            是否添加成功
        """
        # 确保配置已加载（使用 self.config 触发加载）
        if "servers" not in self.config:
            self._config_cache["servers"] = {}

        self._config_cache["servers"][name] = config

        # 如果是第一个服务器或指定为默认，添加到默认列表
        if set_default or not self._config_cache.get("default_servers"):
            if "default_servers" not in self._config_cache:
                self._config_cache["default_servers"] = []
            if name not in self._config_cache["default_servers"]:
                self._config_cache["default_servers"].append(name)

        return self.save()

    def remove_server(self, name: str) -> bool:
        """
        删除服务器配置

        Args:
            name: 服务器名称

        Returns:
            是否删除成功
        """
        # 确保配置已加载
        servers = self.config.get("servers", {})
        if name not in servers:
            return False

        del servers[name]
        self._config_cache["servers"] = servers

        # 从默认列表中移除
        default_servers = self._config_cache.get("default_servers", [])
        if name in default_servers:
            default_servers.remove(name)
        self._config_cache["default_servers"] = default_servers

        return self.save()

    def enable_server(self, name: str) -> bool:
        """启用服务器"""
        server = self.get_server(name)
        if not server:
            return False

        server["enabled"] = True
        return self.save()

    def disable_server(self, name: str) -> bool:
        """禁用服务器"""
        server = self.get_server(name)
        if not server:
            return False

        server["enabled"] = False
        return self.save()

    def import_from_vscode_config(
        self,
        vscode_config_path: Path
    ) -> List[str]:
        """
        从 VSCode/Claude Desktop 配置文件导入 MCP 服务器

        Args:
            vscode_config_path: VSCode 配置文件路径

        Returns:
            导入的服务器名称列表
        """
        try:
            vscode_data = json.loads(vscode_config_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        mcp_servers = vscode_data.get("mcpServers", {})
        imported_names = []

        for name, config in mcp_servers.items():
            # 添加 enabled 标记（默认启用）
            config["enabled"] = True
            self.add_server(name, config)
            imported_names.append(name)

        return imported_names

    def list_servers(self) -> List[Dict[str, Any]]:
        """
        列出所有服务器的信息

        Returns:
            服务器信息列表，包含名称、类型、启用状态
        """
        servers = self.config.get("servers", {})
        default_servers = self.config.get("default_servers", [])

        result = []
        for name, config in servers.items():
            # 判断服务器类型
            if "url" in config:
                server_type = "SSE"
            elif "command" in config:
                server_type = "stdio"
            elif "module" in config:
                server_type = "module"
            else:
                server_type = "unknown"

            result.append({
                "name": name,
                "type": server_type,
                "enabled": config.get("enabled", True),
                "is_default": name in default_servers,
                "config": config
            })

        return result


# 导出便捷函数
def create_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """创建配置管理器实例"""
    return ConfigManager(config_path)
