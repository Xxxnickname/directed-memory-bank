# Directed Memory Bank

> 给 AI Agent 用的**分层、受控、可移植**的长期记忆库。
> A portable, governed long-term memory bank for AI coding agents.

换会话就失忆、换工具就清零，是 Agent 落地里最烦人的两件事。这个项目把长期记忆当成一个**带治理规则的系统**来做：什么能记、记到哪一层、冲突时听谁的、换工具怎么带走。

## 为什么不是"直接塞进向量库"

长期记忆的难点不是存，也不是查，而是**治理**：

| 常见做法 | 后果 |
| --- | --- |
| 模型自动总结、自动改写画像 | 一次情绪、一句玩笑被固化成"用户偏好"，之后再也不会被推翻 |
| 新旧结论直接覆盖 | 冲突被抹掉，无法回溯"为什么改了" |
| 长期记忆和原始对话混在一起检索 | 上下文被重复内容灌满，Token 成本和噪声一起涨 |
| 记忆格式绑定某个工具的私有库 | 换个 Agent 工具，记忆全部归零 |

这四点分别对应四个设计：**写入门控、纠错优先、分层加载、纯 Markdown 源文件**。

## 架构

```text
会话原文（L0，只追加）
   │  ── 增量水位线：只处理上一次之后的新增内容
   ▼
提炼 → 去重 / 冲突检测 → 状态判定 ──┬─► L1 原子事实（带来源与置信度）
                                     ├─► L2 场景流水 / 项目状态 / 可复用技能
                                     ├─► L3 用户画像（需明确确认才升级）
                                     └─► 候选区 / 纠错区 / 复核区（未确认内容隔离）
                                                    │
读取：规则/纠错 → 当前项目 → 已确认画像 → 相关事实 → 少量候选 ──► 注入上下文
检索：本地向量 + BM25 + RRF 融合（只索引正式记忆层，L0 默认不参与）
```

设计理由、状态机、准入规则，以及"什么做法一定失败"的反面清单，见 [`skills/directed-memory-bank/references/architecture.md`](skills/directed-memory-bank/references/architecture.md)。

## 安装

仓库里有两部分：**技能本体**（`skills/directed-memory-bank/`）和**插件清单**（`.codex-plugin/plugin.json`）。下面四种装法任选。

### 方式一：npx 一条命令（最接近 npm，推荐）

```bash
npx skills add Xxxnickname/directed-memory-bank
```

`npx skills` 是 Vercel Labs 的 [skills CLI](https://github.com/vercel-labs/skills)（npm 包名就叫 `skills`，MIT），支持 Codex、Claude Code、Cursor 等 79 个 agent。常用变体：

```bash
npx skills add Xxxnickname/directed-memory-bank --skill directed-memory-bank   # 只装指定技能
npx skills add Xxxnickname/directed-memory-bank -a codex                       # 只装给 Codex
npx skills add Xxxnickname/directed-memory-bank -g                             # 装到全局
```

注意：它装到 **`.agents/skills/`**（项目级）或 **`~/.agents/skills/`**（加 `-g`），不是 `~/.codex/skills`。

### 方式二：用 Codex 自带的 skill-installer

用 Codex 自带的 `skill-installer`，一条命令拉取（需要 Python 3.10+）：

```powershell
python "$env:CODEX_HOME\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo Xxxnickname/directed-memory-bank --path skills/directed-memory-bank
```

macOS / Linux 把 `$env:CODEX_HOME` 换成 `$CODEX_HOME`（默认 `~/.codex`）。

### 方式三：手动安装（离线可用）

```powershell
git clone https://github.com/Xxxnickname/directed-memory-bank.git "$env:TEMP\dmb"
Copy-Item -Recurse -Force "$env:TEMP\dmb\skills\directed-memory-bank" "$env:CODEX_HOME\skills\directed-memory-bank"
Remove-Item -Recurse -Force "$env:TEMP\dmb"
```

安装完成后**新开一个对话**即可用 `$directed-memory-bank` 调用——技能清单是会话启动时加载的，旧对话里看不到。

### 方式四：作为插件源安装

仓库根目录带 `.codex-plugin/plugin.json`（`"skills": "./skills/"`）。如果你的 Codex 支持添加自定义插件源，填本仓库 URL 即可一次装齐仓库内所有技能；界面里没有这个入口时用方式二。

### 其它宿主（Claude Code / Cursor / 自建 Agent）

不依赖 Codex 的技能系统也能用，因为记忆库本体就是纯 Markdown：

1. 把 `skills/directed-memory-bank/assets/memory-bank-template/` 复制到任意目录。
2. 把模板里的 `AGENTS.md` 内容贴进宿主的指令文件（`CLAUDE.md`、`.cursor/rules`、系统提示词）。
3. 可选：`scripts/memory_search.py` 可独立运行，只依赖 Python。

## 开始使用

### 1. 建库

```powershell
Copy-Item -Recurse -Force "$env:CODEX_HOME\skills\directed-memory-bank\assets\memory-bank-template" "$env:USERPROFILE\ai-memory"
```

然后把 `ai-memory\AGENTS.md` 挂到宿主的会话入口（Codex 里的做法是把这段规则写进项目的 `AGENTS.md`）。

### 2. 让 Agent 写记忆

- **手动**：直接说"更新记忆 / 记忆存档"，Agent 按 SKILL.md 的门控规则写入。
- **自动**：按 [`references/sync-pipeline.md`](skills/directed-memory-bank/references/sync-pipeline.md) 配一个每日定时任务（含开机补跑），它只处理水位线之后的新增内容。

### 3. 读记忆

会话内的读取顺序是固定的：`规则/纠错 → 当前项目 → 已确认画像 → 相关事实 → 少量候选`。
需要批量召回时用自带混合检索：

```powershell
pwsh -File "$env:CODEX_HOME\skills\directed-memory-bank\scripts\memory-search.ps1" -Query "当初为什么选这个方案" -Top 8
```

### 4. 迁移到别的工具或电脑

按 [`references/migration.md`](skills/directed-memory-bank/references/migration.md)：记忆本体整体拷贝，胶水层（读日志 + 定时）在新宿主重写，最后跑 12 项验证。

### 可直接用的示例提示词

- `用 $directed-memory-bank 给这个项目建一个记忆库，先只写规则，不写内容。`
- `把今天的结论按受控学习规则存入记忆库，单次推断只能进候选区。`
- `检索记忆库：上次为什么否掉那个方案？`
- `把记忆库迁移到另一台机器，并列出需要在新环境重写的东西。`

## 目录结构

```text
directed-memory-bank/                    # 仓库根
├── README.md
├── LICENSE
├── .codex-plugin/plugin.json            # 插件清单（插件源安装用）
└── skills/directed-memory-bank/         # 技能本体：整个目录拷进 $CODEX_HOME/skills/ 即可
    ├── SKILL.md                         # Agent 入口：规则 + 路由
    ├── agents/openai.yaml               # 宿主 UI 元数据
    ├── references/
    │   ├── architecture.md              # 分层、状态机、准入规则、检索顺序、取舍
    │   ├── sync-pipeline.md             # 增量同步、水位线、提炼提示词、报告格式
    │   └── migration.md                 # 可移植边界 + 迁移后 12 项验证
    ├── scripts/
    │   ├── memory_search.py             # 本地混合检索（向量 + BM25 + RRF）
    │   └── memory-search.ps1            # PowerShell 包装
    └── assets/memory-bank-template/     # 记忆库骨架（复制即用，不含任何个人数据）
```

## 环境变量

| 变量 | 作用 | 默认 |
| --- | --- | --- |
| `MEMORY_ROOT` | 记忆库根目录 | `~/ai-memory` |
| `MEMORY_VAULT_ROOT` | 额外索引的 Markdown 根目录（如个人笔记库），可留空 | 空 |
| `MEMORY_DB_PATH` | 索引数据库路径 | `<MEMORY_ROOT>/indexes/index.sqlite` |
| `MEMORY_EMBED_MODEL` | 向量模型名 | `BAAI/bge-small-zh-v1.5` |
| `MEMORY_EMBED_DIR` | 本地模型目录（离线用） | 空，回退到按模型名下载 |

首次运行会自动下载 `BAAI/bge-small-zh-v1.5`（中文小模型，CPU 可跑）。网络受限可设 `HF_ENDPOINT=https://hf-mirror.com`。

## 它是怎么被验证的

用四条**行为断言**验收，而不是"文件存在"：

1. 已确认偏好：能被召回并影响行为。
2. 未确认推断：只出现在 `candidates.md`，行为不变。
3. 用户纠正：压过旧画像，且冲突记录里留有旧值。
4. 已过期事实：不出现在注入内容里。

完整清单见 [`references/migration.md`](skills/directed-memory-bank/references/migration.md)。技能结构本身可用 `skill-creator` 的 `quick_validate.py` 校验。

## 局限（先说清楚）

- **没有量化评测。** 目前靠行为断言验收，缺检索命中率、记忆引用正确率这类指标，这是下一步要补的。
- **面向单用户。** 多人协作下的权限与隐私分区尚未设计。
- **依赖宿主能读到会话日志。** 这条胶水层与平台绑定，换宿主必须重写。
- **检索是本地小模型。** 纯中文短句表现良好，长英文文档建议换更大的嵌入模型或加 reranker。

## 许可

[MIT](LICENSE) © 2026 Xxxnickname
