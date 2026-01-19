# PagerMaid-Pyro 插件集合

本仓库包含 PagerMaid-Pyro Telegram 人形机器人的自定义插件。

## 开发者

本项目所有插件由 **Vibe Coding** 全权开发。

## 插件列表

| 插件 | 说明 | 文档 |
|------|------|------|
| CAI | 自动点踩插件 - 自动对目标用户的发言进行点踩 | [docs/cai.md](docs/cai.md) |
| JPM | 关键词触发回复插件 - 支持多关键词、频率限制、锚点消息系统 | [docs/jpm.md](docs/jpm.md) |
| SharePlugins | 分享插件 - 将插件以文件形式分享，支持列表查看和序号选择 | [docs/share_plugins.md](docs/share_plugins.md) |

## 安装

1. 将插件文件复制到 PagerMaid-Pyro 的 `plugins/` 目录
2. 重新加载插件：`,reload` 或 `/reload`
3. 查看插件帮助：`,<插件名>`

## 项目结构

```
tegbot_plugin/
├── plugins/           # 插件目录
├── docs/             # 插件文档
├── .vps/             # VPS 部署脚本
└── README.md         # 本文件
```

## 开发说明

本项目遵循严格的开发流程，详见 [`.claude/CLAUDE.md`](.claude/CLAUDE.md)。

## 许可证

MIT License
