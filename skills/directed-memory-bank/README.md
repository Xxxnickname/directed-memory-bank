# directed-memory-bank

> 给 AI Agent 用的**分层、受控、可移植**的长期记忆库。
> 设计理念、架构图和取舍说明见仓库根目录的 [README.md](../../README.md)。

本目录是**技能本体**：整个文件夹复制到 `$CODEX_HOME\skills\` 下即可使用。

## 安装

### 方式一：npx 一条命令（推荐）

```bash
npx skills add Xxxnickname/directed-memory-bank
```

`npx skills` 是 Vercel Labs 的 [skills CLI](https://github.com/vercel-labs/skills)（npm 包名 `skills`）。它装到 `.agents/skills/`（项目级）或 `~/.agents/skills/`（加 `-g`），不是 `~/.codex/skills`；只装给 Codex 加 `-a codex`。

### 方式二：用 Codex 自带的 skill-installer

用 Codex 自带的 `skill-installer` 拉取（需要 Python 3.10+）：

```powershell
python "$env:CODEX_HOME\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo Xxxnickname/directed-memory-bank --path skills/directed-memory-bank
```

### 方式三：手动复制（离线可用）

```powershell
git clone https://github.com/Xxxnickname/directed-memory-bank.git "$env:TEMP\dmb"
Copy-Item -Recurse -Force "$env:TEMP\dmb\skills\directed-memory-bank" "$env:CODEX_HOME\skills\directed-memory-bank"
Remove-Item -Recurse -Force "$env:TEMP\dmb"
```

安装后**新开一个对话**，用 `$directed-memory-bank` 调用。技能清单在会话启动时加载，旧对话里不会出现。

## 使用

### 1. 建库

把记忆库骨架复制到任意目录，作为记忆库根：

```powershell
Copy-Item -Recurse -Force "$env:CODEX_HOME\skills\directed-memory-bank\assets\memory-bank-template" "$env:USERPROFILE\ai-memory"
```

再把 `ai-memory\AGENTS.md` 挂到宿主的会话入口（Codex 里就是写进项目的 `AGENTS.md`）。

### 2. 写记忆

直接说「更新记忆 / 记忆存档」，Agent 会按 `SKILL.md` 的门控规则写入：单次推断只进候选区，升级画像需要明确确认。

### 3. 读记忆

会话内加载顺序固定为 `规则/纠错 → 当前项目 → 已确认画像 → 相关事实 → 少量候选`。需要批量召回时用自带混合检索（向量 + BM25 + RRF）：

```powershell
pwsh -File "$env:CODEX_HOME\skills\directed-memory-bank\scripts\memory-search.ps1" -Query "当初为什么选这个方案" -Top 8
```

### 4. 迁移

按 `references/migration.md` 执行：记忆本体整体拷贝，胶水层（读日志 + 定时任务）在新宿主重写，最后跑迁移后的验证清单。

### 示例提示词

- `用 $directed-memory-bank 给这个项目建一个记忆库，先只写规则，不写内容。`
- `把今天的结论按受控学习规则存入记忆库，单次推断只能进候选区。`
- `检索记忆库：上次为什么否掉那个方案？`
- `把记忆库迁移到另一台电脑，并列出需要在新环境重写的东西。`

## 目录

| 路径 | 作用 |
| --- | --- |
| `SKILL.md` | Agent 入口：规则 + 路由（Codex 自动加载的就是它） |
| `agents/openai.yaml` | 宿主 UI 元数据 |
| `references/` | 架构、同步流水线、迁移说明 |
| `scripts/` | 本地混合检索（向量 + BM25 + RRF） |
| `assets/memory-bank-template/` | 记忆库骨架，复制即用，不含任何个人数据 |

## 许可

[MIT](../../LICENSE)
