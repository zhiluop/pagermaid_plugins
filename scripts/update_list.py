#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件列表更新脚本
自动扫描插件目录，更新 list.json 文件
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# 设置输出编码为 UTF-8（Windows 兼容）
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# 配置
PLUGIN_DIR = Path(__file__).parent.parent
LIST_FILE = PLUGIN_DIR / "list.json"
MAINTAINER = "Vibe Coding"
SECTION = "chat"


def format_size(size_bytes: float) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 b"
    for unit in ["b", "kb", "mb", "gb"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.3f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.3f} tb"


def get_plugin_description(plugin_name: str) -> tuple[str, str]:
    """
    获取插件描述
    返回: (short_des, des)
    """
    des_file = PLUGIN_DIR / plugin_name / "DES.md"

    if des_file.exists():
        with open(des_file, "r", encoding="utf-8") as f:
            des = f.read().strip()
        # 短描述取前50个字符
        short_des = des[:50] + "..." if len(des) > 50 else des
        return short_des, des
    else:
        return "暂无描述", "暂无描述"


def normalize_version(version: str) -> str:
    """
    将版本号转换为 PagerMaid 兼容的 float 格式
    PagerMaid 的 LocalPlugin.version 是 Optional[float] 类型，
    因此版本号必须能被 float() 解析。

    示例:
    - "1.0.0" -> "1.0"
    - "1.2.3" -> "1.23"
    - "2.0" -> "2.0"
    """
    parts = version.split(".")
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]}.{parts[1]}"
    else:
        # 将第二部分和第三部分合并，如 1.2.3 -> 1.23
        return f"{parts[0]}.{parts[1]}{parts[2]}"


def get_plugin_version(plugin_name: str) -> str:
    """从 main.py 中提取版本号，并转换为 float 兼容格式"""
    main_file = PLUGIN_DIR / plugin_name / "main.py"
    if not main_file.exists():
        return "1.0"

    try:
        with open(main_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 尝试匹配版本号模式
            import re

            version_patterns = [
                r'version\s*=\s*["\']([^"\']+)["\']',
                r'__version__\s*=\s*["\']([^"\']+)["\']',
                r'VERSION\s*=\s*["\']([^"\']+)["\']',
            ]
            for pattern in version_patterns:
                match = re.search(pattern, content)
                if match:
                    return normalize_version(match.group(1))
    except Exception as e:
        print(f"警告: 无法读取 {plugin_name} 的版本号: {e}")

    return "1.0"


def scan_plugins() -> List[Dict]:
    """扫描插件目录，返回插件列表"""
    plugins = []

    # 遍历所有子目录
    for item in PLUGIN_DIR.iterdir():
        if not item.is_dir():
            continue

        # 跳过特殊目录
        if item.name.startswith(".") or item.name in [
            "scripts",
            "docs",
            ".vps",
            ".claude",
            "__pycache__",
        ]:
            continue

        # 检查是否是有效的插件目录（包含 main.py）
        main_file = item / "main.py"
        if not main_file.exists():
            continue

        plugin_name = item.name

        # 获取文件大小
        size_bytes = main_file.stat().st_size
        size_formatted = format_size(size_bytes)

        # 获取版本号
        version = get_plugin_version(plugin_name)

        # 获取描述
        short_des, des = get_plugin_description(plugin_name)

        # 构建插件信息
        plugin_info = {
            "name": plugin_name,
            "version": version,
            "section": SECTION,
            "maintainer": MAINTAINER,
            "size": size_formatted,
            "supported": True,
            "des_short": short_des,
            "des": des,
        }

        plugins.append(plugin_info)
        print(f"[OK] 找到插件: {plugin_name} ({size_formatted})")

    return plugins


def save_list_file(plugins: List[Dict]):
    """保存 list.json 文件"""
    data = {"list": plugins}

    with open(LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"\n[OK] 已更新 {LIST_FILE}")
    print(f"[OK] 共 {len(plugins)} 个插件")


def main():
    """主函数"""
    print("=" * 60)
    print("插件列表更新脚本")
    print("=" * 60)

    # 扫描插件
    plugins = scan_plugins()

    if not plugins:
        print("\n[WARNING] 未找到任何插件")
        return

    # 按 name 排序
    plugins.sort(key=lambda x: x["name"])

    # 保存文件
    save_list_file(plugins)

    print("\n[COMPLETE] 完成！")


if __name__ == "__main__":
    main()
