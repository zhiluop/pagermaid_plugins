# VPS 插件部署指南

本文档说明如何使用部署脚本将本地开发的插件快速上传到 VPS 上的 PagerMaid-Pyro 环境。

## 前提条件

1. **VPS 环境**：
   - VPS 上已安装并配置好 PagerMaid-Pyro
   - PagerMaid-Pyro 已完成持久化（systemd/supervisor/docker 等）
   - 插件目录存在且可写（默认：`/home/workdir/plugins`）

2. **本地环境**：
   - Python 3.7+
   - 已安装 paramiko 库：`pip install paramiko`

## 配置步骤

### 1. 创建配置文件

复制配置模板并填写你的 VPS 信息：

```bash
cp .vps/config.example.json .vps_config.json
```

### 2. 编辑配置文件

编辑 `.vps_config.json`，填入你的 VPS 连接信息：

```json
{
  "host": "your-vps-ip.com",
  "username": "your_username",
  "password": "your_password",
  "plugin_dir": "/home/workdir/plugins",
  "description": "PagerMaid-Pyro VPS 插件部署目标"
}
```

**配置说明**：
- `host`：VPS 的 IP 地址或域名
- `username`：SSH 登录用户名
- `password`：SSH 登录密码
- `plugin_dir`：VPS 上 PagerMaid-Pyro 的插件目录路径

## 使用方法

### 上传指定插件

```bash
python .vps/deploy.py jpm
```

### 上传所有插件

```bash
python .vps/deploy.py
```

### 上传效果

- ✅ 自动覆盖同名文件
- ✅ 显示上传进度和结果
- ✅ 配置文件不会被上传（已在 .gitignore 中）

## 部署后操作

插件上传完成后，需要在 Telegram 中重载插件：

```
/reload
```

或使用命令模式：

```
,reload
```

## 常见问题

### 1. 连接失败

**错误**：`认证失败，请检查用户名和密码`

**解决**：检查 `.vps_config.json` 中的用户名和密码是否正确

### 2. 目录不存在

**错误**：` FileNotFoundError`

**解决**：登录 VPS 手动创建插件目录：
```bash
mkdir -p /home/workdir/plugins
```

### 3. 权限不足

**错误**：`Permission denied`

**解决**：确保 SSH 用户对插件目录有写权限

## 安全提示

- ⚠️ `.vps_config.json` 包含敏感信息，已在 `.gitignore` 中，不会被提交到 Git
- ⚠️ 不要将包含真实密码的配置文件分享给他人
- ⚠️ 建议使用 SSH 密钥认证代替密码（需修改部署脚本支持）

## 文件结构

```
tegbot_plugin/
├── .vps/                          # VPS 部署相关
│   ├── deploy.py                  # 部署脚本
│   ├── config.example.json        # 配置模板
│   └── README.md                  # 本文档
├── .vps_config.json               # 你的 VPS 配置（不提交）
├── plugins/                       # 本地插件目录
│   ├── jpm.py
│   └── ...
└── docs/                          # 插件文档
```

## 更新日志

- **v1.0** - 初始版本，支持 SSH 上传插件到 VPS
