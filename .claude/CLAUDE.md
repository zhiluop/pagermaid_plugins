# CLAUDE.md

此文件为 Claude Code (claude.ai/code) 提供在此代码库中工作的指导。

## 项目概述

**tegbot_plugin** 是 PagerMaid-Pyro Telegram 人形机器人的插件开发项目。

PagerMaid-Pyro 是一个基于 Pyrogram 的开源 Telegram Userbot 框架，支持通过插件扩展功能。本项目专注于开发自定义插件。

## 插件目录结构

```
tegbot_plugin/
├── plugins/                    # 插件目录
│   ├── example_plugin.py      # 示例插件
│   └── your_plugin.py.disabled # 禁用的插件 (.disabled 后缀)
└── LICENSE                     # MIT 许可证
```

## 插件开发基础

### 核心组件

1. **@listener 装饰器** - 注册命令监听器
   - `command`: 命令名称
   - `description`: 命令描述
   - `parameters`: 参数说明
   - `is_plugin`: 是否为插件（默认 True）
   - `outgoing`: 响应自己的消息（默认 True）
   - `incoming`: 响应传入消息（默认 False）
   - `priority`: 执行优先级 0-100（默认 50）

2. **@Hook 装饰器** - 生命周期钩子
   - `on_startup()`: 启动时执行
   - `on_shutdown()`: 关闭时执行
   - `command_preprocessor()`: 命令预处理
   - `command_postprocessor()`: 命令后处理
   - `process_error()`: 错误处理

3. **Message 类型** - 来自 `pagermaid.enums`，提供消息操作方法

### 命令使用方式

- `,命令` - 自己发送的命令
- `/命令` - sudo 命令（需要权限）

### 插件管理

```bash
# 列出已安装的插件
/plugin

# 安装远程插件
/plugin install <url>

# 卸载插件
/plugin remove <插件名>

# 重载所有插件
/reload
```

## VPS 部署流程

**强制要求**：每次修改插件脚本或完成新插件开发后，必须部署到 VPS。

### 部署步骤

1. **自动生成插件副本并上传**：
   ```bash
   # 上传指定插件（会自动创建副本并重命名）
   python .vps/deploy.py jpm

   # 上传所有插件
   python .vps/deploy.py
   ```

2. **在 Telegram 中重载插件**：
   ```
   /reload
   ```

### 部署说明

- **自动重命名**：脚本会自动将插件 main.py 复制到 `debug/` 目录，并重命名为 `<插件名>.py`
  - 例如：`jpm/main.py` → `debug/jpm.py`
- **自动上传**：重命名后的副本会自动上传到 VPS 的 `/home/workdir/plugins/` 目录
- **自动覆盖**：上传会直接覆盖 VPS 上的同名文件，无需手动删除
- **配置隔离**：VPS 连接配置存储在 `.vps_config.json`，已加入 `.gitignore`
- **安全性**：
  - `debug/` 目录已加入 `.gitignore`，不会上传到 GitHub
  - `.vps/` 目录已加入 `.gitignore`，包含敏感配置
  - 所有敏感信息不会上传到 GitHub 仓库

### 部署时机

**每次**修改或开发插件后**必须**执行：
- [ ] 插件脚本修改完成
- [ ] 运行 `python .vps/deploy.py <插件名>` 上传插件
- [ ] 在 Telegram 中执行 `/reload` 重载插件

### 参考文档

- [PagerMaid-Pyro 官方文档](https://xtaolabs.com/)
- [Pyrogram API 文档](https://docs.pyrogram.org/)
- [PagerMaid-Pyro 源码](https://github.com/TeamPGM/PagerMaid-Pyro)

## 语言约定

- 所有文档使用中文编写
- 代码注释使用中文
- 对话交流使用中文

## 隐私保护规则

**强制要求**：严禁将任何敏感信息提交到 Git 仓库。

### 敏感信息清单

以下信息绝对不能出现在代码、文档或配置文件中：

- **服务器信息**：IP 地址、域名、端口号
- **认证信息**：用户名、密码、API 密钥、SSH 密钥
- **令牌信息**：Token、Cookie、Session ID、JWT
- **个人隐私**：真实姓名、邮箱、手机号、身份证号
- **数据库信息**：数据库连接字符串、凭证
- **第三方服务**：API 密钥、Webhook URL、Bot Token

### 安全编码规范

1. **配置文件管理**：
   - 所有包含敏感信息的配置文件必须加入 `.gitignore`
   - 使用 `.example` 或 `.template` 后缀创建配置模板
   - 模板中只包含字段说明，不包含真实值

2. **文档编写规范**：
   - 文档示例使用虚构数据（如 `your-vps-ip.com`、`your_username`）
   - 禁止在文档中出现真实的 IP、用户名、密码
   - 代码注释中不得包含敏感信息

3. **提交前检查清单**：
   ```bash
   # 检查是否包含敏感信息
   git diff --cached | grep -E "(password|token|key|secret|api_key|cookie|session)"
   ```

4. **强制要求**：
   - **每次 git commit 前必须执行隐私检查**
   - **每次 git push 前必须再次确认无敏感信息**
   - 使用 `.gitignore` 排除所有包含敏感信息的文件

5. **违反处理**：
   - 如发现敏感信息已提交，立即用新提交覆盖
   - 不要尝试删除历史记录（会造成更大问题）
   - 考虑更新已泄露的凭证/密钥

### 示例

**❌ 错误示例**（包含真实信息）：
```json
{
  "host": "192.168.1.100",
  "username": "admin",
  "password": "mySecretPassword123"
}
```

**✅ 正确示例**（使用模板）：
```json
{
  "host": "your-vps-ip.com",
  "username": "your_username",
  "password": "your_password"
}
```

## 项目文档管理规则

### README 更新规则

**强制要求**：每次插件发生变化（新增、删除、重大更新）时，必须同步更新项目根目录的 `README.md`。

1. **插件列表同步**：
   - 新增插件 → 在插件列表中添加条目
   - 删除插件 → 从插件列表中移除条目
   - 更新插件 → 更新插件说明文字

2. **更新时机**：
   - [ ] 插件文档 (`docs/*.md`) 更新完成
   - [ ] 插件代码提交前

3. **README 维护内容**：
   - 插件列表（名称、说明、文档链接）
   - 项目结构（如有变更）
   - 开发说明链接

### 文档存储规范

1. **单文档迭代原则**：每个项目的所有文档必须使用单一文档进行迭代开发，禁止创建多个文档碎片
2. **文档目录结构**：在当前工作区创建 `docs/` 目录，用于集中存放所有项目文档
3. **文档命名规范**：使用项目名称或功能模块命名文档，例如 `sao_nkr.md` 而不是分散的多个文档
4. **文档位置**：
   - 所有项目设计文档、需求文档、技术文档统一存放在 `docs/` 目录
   - 插件代码内可以保留简短的注释文档，但详细文档必须放在 `docs/` 目录
   - 示例结构：
     ```
     docs/
     ├── sao_nkr.md          # 骚话生成器完整文档
     ├── other_project.md    # 其他项目文档
     └── ...
     ```

### 文档迭代工作流

1. **初始创建**：在 `docs/` 目录创建项目文档
2. **更新迭代**：所有更新都在同一文档中进行，通过版本标记或章节组织内容
3. **避免多文档**：不要为同一项目创建 `DES.md`、`REQ.md`、`API.md` 等多个文档
4. **统一管理**：确保所有相关讨论和文档内容集中在单一文档中

### 代码与文档同步规则

**强制要求**：每次修改插件脚本后，必须同步更新对应的文档。

1. **脚本修改触发文档更新**：
   - 新增/删除/修改命令 → 更新使用方法和命令列表
   - 修改功能逻辑 → 更新功能介绍和技术实现
   - 新增配置项 → 更新配置说明和数据结构
   - 调整文件结构 → 更新文件结构说明
   - 修复重要bug → 在版本历史中记录

2. **文档更新检查清单**：
   - [ ] 版本历史是否需要更新
   - [ ] 功能介绍是否准确
   - [ ] 使用方法是否完整
   - [ ] 命令列表是否最新
   - [ ] 配置说明是否正确
   - [ ] 数据结构是否匹配
   - [ ] 注意事项是否需要补充

3. **文档更新时机**：
   - 脚本修改完成后立即更新文档
   - 完成功能开发后更新文档
   - 重大bug修复后更新文档

### 迁移说明

- 如果项目中存在旧的文档（如 `DES.md`），需迁移到 `docs/` 目录并合并为主要文档
- 新项目直接在 `docs/` 目录创建单一文档
