# PagerMaid-Pyro 插件集合

本仓库包含 PagerMaid-Pyro Telegram 人形机器人的自定义插件。

## 开发者

本项目所有插件由 **Vibe Coding** 全权开发。

## 快速开始

### 使用 apt_source 安装（推荐）

在 PagerMaid-Pyro 中添加插件源：

```
,apt_source add https://raw.githubusercontent.com/zhiluop/tegbot_plugin/main/
```

> **重要**: URL 末尾必须带 `/`，否则无法正常获取插件列表。

安装插件：

```
,apt install <插件名>
```

可用插件：
- `cai` - 自动点踩插件
- `jpm` - 关键词触发回复插件
- `jpmai` - AI 生成艳情文案插件
- `ais` - AI 查询插件
- `get_reactions` - 表情获取辅助命令
- `share_plugins` - 分享插件
- `stfollow` - 贴纸跟随插件
- `sar` - 贴纸自动回复插件

### 手动安装

1. 下载插件文件夹
2. 将插件文件夹复制到 PagerMaid-Pyro 的 `plugins/` 目录
3. 重新加载插件：`,reload` 或 `/reload`
4. 查看插件帮助：`,<插件名>`

## 插件列表

| 插件 | 说明 |
|------|------|
| CAI | 自动点踩插件 - 自动对目标用户的发言进行点踩 |
| JPM | 关键词触发回复插件 - 支持多关键词、频率限制、锚点消息系统 |
| JPMAI | AI 生成艳情文案插件 - 调用 AI 模型实时生成仿明清艳情小说风格的回复 |
| AIS | AI 查询插件 - 向 AI 模型提问并返回回复，支持自定义 API 配置和 MCP 工具集成 |
| Get Reactions | 表情获取辅助命令 - 用于测试环境是否支持自定义表情反应 |
| Share Plugins | 分享插件 - 将插件以文件形式分享，支持列表查看和序号选择 |
| StFollow | 贴纸跟随插件 - 在特定群组中自动跟随发送特定贴纸，管理命令自动撤回 |
| SAR | 贴纸自动回复插件 - 当有人用贴纸回复你的消息时，自动回复相同的贴纸，管理命令自动撤回 |

## 项目结构

```
tegbot_plugin/
├── cai/                     # 自动点踩插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── jpm/                     # 关键词触发回复插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── jpmai/                   # AI 生成艳情文案插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── ais/                     # AI 查询插件
│   ├── main.py             # 插件主文件
│   ├── mcp_config.json     # MCP 配置文件（运行时生成）
│   └── DES.md              # 插件描述
├── mcp_client/              # MCP 客户端模块（可选依赖）
│   ├── __init__.py         # 模块入口
│   ├── client.py           # MCP 客户端主逻辑
│   ├── config.py           # 配置管理
│   └── registry.py         # 工具注册表
├── get_reactions/           # 表情获取辅助命令
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── share_plugins/           # 分享插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── stfollow/               # 贴纸跟随插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── sar/                    # 贴纸自动回复插件
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── list.json               # 插件列表（apt_source 使用）
├── index.html              # 插件展示页面
├── scripts/                # 维护脚本
│   └── update_list.py      # 自动更新插件列表
└── README.md               # 本文件
```

## 开发说明

本项目遵循严格的开发流程，详见 [`.claude/CLAUDE.md`](.claude/CLAUDE.md)。

### MCP 工具集成（可选）

`ais` 插件支持集成 MCP（Model Context Protocol）工具，提供增强的 AI 能力。

**安装 MCP 客户端**（可选）：
```bash
# 在 PagerMaid-Pyro 的虚拟环境中安装
pip install mcp
```

**配置 MCP 服务器**：
```
# 列出所有 MCP 服务器
,ais mcp list

# 添加 stdio 方式的 MCP 服务器
,ais mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /allowed/path

# 添加 SSE 方式的 MCP 服务器
,ais mcp add my-server --url http://localhost:8080/sse

# 从 VSCode/Claude Desktop 配置导入
,ais mcp import ~/.config/claude/claude_desktop_config.json

# 查看可用工具
,ais mcp tools

# 启用/禁用服务器
,ais mcp enable filesystem
,ais mcp disable filesystem
```

**MCP 配置文件**：`ais/mcp_config.json`

**注意**：MCP 是可选功能，未安装时 ais 插件仍可正常使用 API 查询。

### 添加新插件

1. 创建插件文件夹：`mkdir your_plugin`
2. 创建 `main.py` 文件：插件主代码
3. 创建 `DES.md` 文件：插件简短描述
4. 运行 `python scripts/update_list.py`：自动更新插件列表

## 许可证

MIT License
