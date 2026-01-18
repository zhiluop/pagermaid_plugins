#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS 部署脚本 - 上传插件到 PagerMaid-Pyro VPS

使用方法:
    python .vps/deploy.py              # 上传所有插件
    python .vps/deploy.py jpm          # 上传指定插件

配置说明:
    复制 .vps/config.example.json 为 .vps_config.json 并填写你的 VPS 信息
"""
import json
import os
import sys
from pathlib import Path

import paramiko

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / ".vps_config.json"
CONFIG_EXAMPLE = Path(__file__).parent / "config.example.json"
PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


def load_config():
    """加载 VPS 配置"""
    if not CONFIG_FILE.exists():
        print(f"错误: 配置文件不存在: {CONFIG_FILE}")
        print(f"\n请按以下步骤配置:\n1. 复制配置模板: cp {CONFIG_EXAMPLE} {CONFIG_FILE}")
        print(f"2. 编辑配置文件，填写你的 VPS 信息")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 验证必要字段
            required_fields = ["host", "username", "password", "plugin_dir"]
            for field in required_fields:
                if field not in config:
                    print(f"错误: 配置文件缺少必要字段: {field}")
                    sys.exit(1)
            return config
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件格式错误: {e}")
        sys.exit(1)


def upload_file(sftp, local_path: Path, remote_path: str):
    """上传单个文件（会覆盖已存在的文件）"""
    try:
        # 检查远程文件是否存在
        try:
            remote_stat = sftp.stat(remote_path)
            file_exists = True
        except FileNotFoundError:
            file_exists = False

        # 上传文件（自动覆盖）
        sftp.put(str(local_path), remote_path)

        action = "已覆盖" if file_exists else "已上传"
        print(f"✅ {action}: {local_path.name}")
    except Exception as e:
        print(f"❌ 上传失败 {local_path.name}: {e}")


def deploy_plugin(plugin_name: str = None):
    """部署插件到 VPS"""
    config = load_config()

    # 连接 VPS
    print(f"连接到 VPS: {config['host']}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=config['host'],
            port=22,
            username=config['username'],
            password=config['password'],
            timeout=10
        )
        print("✅ 连接成功")

        # 创建 SFTP 客户端
        sftp = client.open_sftp()

        # 确保远程目录存在
        remote_dir = config['plugin_dir']
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            print(f"创建远程目录: {remote_dir}")
            sftp.mkdir(remote_dir)

        # 上传文件
        if plugin_name:
            # 上传指定插件
            plugin_file = PLUGINS_DIR / f"{plugin_name}.py"
            if not plugin_file.exists():
                print(f"❌ 插件文件不存在: {plugin_file}")
                return
            upload_file(sftp, plugin_file, f"{remote_dir}/{plugin_name}.py")
        else:
            # 上传所有 .py 文件（跳过 .disabled 文件）
            for plugin_file in PLUGINS_DIR.glob("*.py"):
                if not plugin_file.name.endswith(".disabled"):
                    upload_file(sftp, plugin_file, f"{remote_dir}/{plugin_file.name}")

        sftp.close()
        print("\n部署完成！")

    except paramiko.AuthenticationException:
        print("❌ 认证失败，请检查用户名和密码")
    except paramiko.SSHException as e:
        print(f"❌ SSH 连接错误: {e}")
    except Exception as e:
        print(f"❌ 部署失败: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        deploy_plugin(sys.argv[1])
    else:
        deploy_plugin()
