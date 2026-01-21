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
- `get_reactions` - 表情获取辅助命令
- `share_plugins` - 分享插件

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
| Get Reactions | 表情获取辅助命令 - 用于测试环境是否支持自定义表情反应 |
| Share Plugins | 分享插件 - 将插件以文件形式分享，支持列表查看和序号选择 |

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
├── get_reactions/           # 表情获取辅助命令
│   ├── main.py             # 插件主文件
│   └── DES.md              # 插件描述
├── share_plugins/           # 分享插件
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

### 添加新插件

1. 创建插件文件夹：`mkdir your_plugin`
2. 创建 `main.py` 文件：插件主代码
3. 创建 `DES.md` 文件：插件简短描述
4. 运行 `python scripts/update_list.py`：自动更新插件列表

## 许可证

MIT License
