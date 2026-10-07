---
name: directed-memory-bank
description: 帮 AI Agent 建立并运行一套可移植的分层长期记忆库（L0 原始证据 → L1 原子事实 → L2 场景/项目/技能 → L3 用户画像），写入走候选/纠错/复核三重门控，读取按优先级加载，并可选本地混合检索。Use when 用户要求跨会话记忆、定义"什么能记什么不能记"、在工具或电脑之间迁移记忆、检索个人记忆库，或想让 Agent 随着长期使用逐步理解自己。
metadata:
  short-description: Portable layered memory bank for AI agents
---

# Directed Memory Bank（导向式记忆库）

核心主张：**把"证据"和"结论"分开存，并规定谁能把什么升级成结论。**
源文件是纯 Markdown/JSONL，所以换工具、换电脑都带得走；向量索引只是可重建的缓存。

## 四层结构

| 层 | 存什么 | 谁能写 |
| --- | --- | --- |
| `L0-raw/`、`L0-portable/`、`L0-manifest/` | 完整会话原文（原件 + 脱敏副本）与定位清单 | 只追加，永不修改 |
| `L1-facts/YYYY-MM-DD.md` | 原子事实：做了什么、规则变化、遗留问题 | 已验证的才可直写，必须带来源与置信度 |
| `L2-scenarios/`、`L2-projects/`、`L2-skills/` | 每日会话流水、进行中项目状态、可复用方法 | 每轮增量追加；项目状态原地更新 |
| `L3-profile/user-profile.md` | 稳定背景、长期偏好、固定规则 | 门槛最高：用户明确确认才可升级 |
| `controlled-memory/` | `candidates.md`、`corrections.md`、`review.md` | 未确认内容的隔离区 |

状态机、准入规则、检索顺序与设计取舍见 [references/architecture.md](references/architecture.md)。

## 硬约束

1. 单次观察、模型推断、未确认偏好只能进 `candidates.md`，不改变行为规则。
2. 升级到 L3 需要用户明确确认，或至少两次独立一致证据。
3. 用户纠正优先于一切旧结论：在 `corrections.md` 记下旧值、新值、证据和影响范围，禁止静默覆盖。
4. 时间敏感、低置信度、长期未验证的内容进 `review.md`，不当作当前事实注入。
5. 每条记忆都带类型、状态（`confirmed`/`probable`/`observed`/`rejected`/`expired`）、来源、更新时间和置信度。
6. 不写 API Key、密码、Cookie、Token，一律用 *** 打码。
7. L0 只追加。删证据是唯一不可逆的错误。

## 四种用法

**建库**：把 `assets/memory-bank-template/` 复制到目标目录，让宿主每次会话先读其中的 `AGENTS.md`：

```powershell
Copy-Item -Recurse -Force assets/memory-bank-template "$env:USERPROFILE\ai-memory"
```

**写记忆**：按 [references/sync-pipeline.md](references/sync-pipeline.md) 走增量水位线、提炼提示词和收尾报告；用户说"更新记忆/存档"即触发同一流程。

**读记忆**：按 `规则/纠错 → 当前项目 → 已确认画像 → 相关 L1/L2 → 少量候选` 的顺序加载。需要批量召回时用自带混合检索：

```powershell
pwsh -File scripts/memory-search.ps1 -Query "当初为什么选这个方案" -Top 8
```

**迁移**：按 [references/migration.md](references/migration.md) 执行，它区分了"可移植核心"与"必须在新宿主重写的薄层"，并给出迁移后的验证清单。

## 交付前验证

要证明四种行为，而不是证明文件存在：已确认偏好能被召回；未确认推断只落在 `candidates.md`；纠正能压过旧画像行；`expired` 事实不被注入。
