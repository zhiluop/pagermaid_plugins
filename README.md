# PagerMaid-Pyro 插件集合

本仓库包含 PagerMaid-Pyro Telegram 人形机器人的自定义插件。

## 开发者

本项目所有插件由 **Vibe Coding** 全权开发。

## 插件列表

| 插件 | 说明 | 文档 |
|------|------|------|
| CAI | 自动点踩插件 - 自动对目标用户的发言进行点踩 | [docs/cai.md](docs/cai.md) |
| JPM | 金瓶梅语录插件 - 关键词触发金瓶梅语录 | [docs/jpm.md](docs/jpm.md) |
| SAO NKR | 骚话生成器 - 基于关键词自动生成骚话回复 | [docs/sao_nkr.md](docs/sao_nkr.md) |

## 安装

1. 将插件文件复制到 PagerMaid-Pyro 的 `plugins/` 目录
2. 重新加载插件：`,reload` 或 `/reload`
3. 查看插件帮助：`,<插件名>`

## 项目结构

```
tegbot_plugin/
├── plugins/           # 插件目录
├── docs/             # 插件文档
└── README.md         # 本文件
```

## 许可证

MIT License
