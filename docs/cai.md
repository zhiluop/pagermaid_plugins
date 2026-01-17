# 自动点踩插件 (CAI - Auto Click Icon)

## 功能概述

自动对目标群组中目标用户的发言进行点踩（添加表情反应）。支持多目标配置、冷却时间限制、标准表情和自定义表情（需环境支持）。

## 文件结构

```
plugins/
├── cai.py                # 自动点踩插件主文件
├── get_reactions.py      # 表情获取辅助命令
└── cai_config.json       # 配置文件（自动生成）
```

## 功能介绍

- **自动点踩**：监听目标用户的发言，自动添加表情反应
- **冷却机制**：每个目标独立计时，防止频繁点踩
- **多目标支持**：可配置多个用户+群组组合
- **表情支持**：支持标准表情和自定义表情（需 Pyrogram fork 支持）

## 使用方法

### 管理命令

| 命令 | 说明 |
|------|------|
| `,cai` | 显示帮助信息 |
| `,cai on` | 开启自动点踩功能 |
| `,cai off` | 关闭自动点踩功能 |
| `,cai set <用户ID> <群组ID> <频率(秒)>` | 添加目标配置 |
| `,cai remove <序号>` | 删除指定配置 |
| `,cai list` | 查看所有目标配置 |
| `,cai emoji <表情>` | 设置点踩表情 |
| `,cai stats` | 查看统计信息 |

### 辅助命令

| 命令 | 说明 |
|------|------|
| `,get_reactions` | 回复一条带表情反应的消息，获取表情详情 |
| `,test_react [表情]` | 测试发送表情反应 |

### 使用示例

```bash
# 开启功能
,cai on

# 添加目标配置（用户ID 123456789，群组ID -1001234567890，1小时间隔）
,cai set 123456789 -1001234567890 3600

# 设置标准表情
,cai emoji 👎

# 查看所有配置
,cai list

# 查看统计信息
,cai stats

# 删除第1个配置
,cai remove 1
```

### 自定义表情使用（需环境支持）

```bash
# 获取自定义表情ID
,reply_to_message ,get_reactions

# 设置自定义表情（纯数字ID）
,cai emoji 5352930934257484526

# 测试自定义表情
,reply_to_message ,test_react 5352930934257484526
```

## 配置说明

### cai_config.json 结构

```json
{
  "enabled": false,
  "emoji": "👎",
  "targets": [
    {
      "user_id": 123456789,
      "chat_id": -1001234567890,
      "rate_limit": 3600,
      "last_react_time": 0
    }
  ],
  "stats": {
    "total_reacts": 0
  }
}
```

### 配置项说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 功能开关 |
| `emoji` | string | 点踩表情（标准 emoji 或自定义表情ID） |
| `targets` | array | 目标配置列表 |
| `targets[].user_id` | integer | 目标用户ID |
| `targets[].chat_id` | integer | 目标群组ID |
| `targets[].rate_limit` | integer | 冷却时间（秒） |
| `targets[].last_react_time` | integer | 最后点踩时间戳 |
| `stats.total_reacts` | integer | 累计点踩次数 |

## 技术实现

### 核心逻辑

```
用户发言 → 监听检测 → 检查是否在目标列表
    ↓
检查冷却时间 → 已过冷却 → 发送表情反应 → 重置计时
    ↓
未过冷却 → 忽略本次发言
```

### 冷却时间检查

```python
def can_react(self, user_id: int, chat_id: int) -> bool:
    target = self.get_target(user_id, chat_id)
    if not target:
        return False

    current_time = int(time.time())
    elapsed = current_time - target["last_react_time"]
    return elapsed >= target["rate_limit"]
```

### 表情类型判断

插件会自动判断表情类型：

- **纯数字** → 自定义表情ID → 使用 `ReactionTypeCustomEmoji`
- **其他字符** → 标准表情 → 使用 `ReactionTypeEmoji`

### 环境支持检测

启动时自动检测是否支持自定义表情：

```python
try:
    from pyrogram.types import ReactionTypeEmoji, ReactionTypeCustomEmoji
    HAS_CUSTOM_EMOJI = True
except ImportError:
    HAS_CUSTOM_EMOJI = False
```

## 注意事项

### 频率限制建议

- 最小间隔：60 秒（1 分钟）
- 推荐间隔：3600 秒（1 小时）
- 频繁点踩可能影响群组氛围

### 自定义表情支持

自定义表情功能需要 Pyrogram fork 支持（如 PyroTGFork）。

检查环境是否支持：
```bash
,get_reactions  # 查看输出中的"环境支持"状态
```

PagerMaid-Pyro 使用的 TeamPGM/pyrogram fork **不支持**自定义表情。

要支持自定义表情，需要切换到支持自定义表情的 Pyrogram fork。

### Docker 环境部署

在 Docker 容器中修改依赖不会持久化，需要修改 Docker 配置：

**方案1：修改 Docker Compose**
```yaml
services:
  pagermaid:
    command: >
      sh -c "
      pip install --force-reinstall git+https://github.com/Mayuri-Chan/pyrogram@master &&
      python3 -m pagermaid
      "
```

**方案2：自定义 Dockerfile**
```dockerfile
FROM ghcr.io/teamspgm/pagermaid_pyro:latest
RUN pip uninstall -y pyrogram && \
    pip install git+https://github.com/Mayuri-Chan/pyrogram@master
```

## 版本历史

### v1.0.0 (2025-01-17)
- 初始版本
- 支持自动点踩功能
- 支持多目标配置
- 支持冷却时间限制
- 支持标准表情
- 添加自定义表情支持检测
- 添加表情获取和测试辅助命令
