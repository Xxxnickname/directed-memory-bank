# Memory Bank Index

与上级 `AGENTS.md` 一起跨会话、跨工具使用。每次会话开始先读本文件。

## 分层结构（L0→L3）

- L0 原始证据：`L0-raw/YYYY/MM/`（完整会话，只读）
- L0 可移植记录：`L0-portable/YYYY/MM/`（脱敏 JSONL）
- L0 清单：`L0-manifest/manifest.jsonl`
- L1 原子事实：`L1-facts/YYYY-MM-DD.md`
- L2 场景/项目/技能：`L2-scenarios/`、`L2-projects/`、`L2-skills/`
- L3 画像：`L3-profile/user-profile.md`
- 受控记忆：`controlled-memory/`
- 本地索引：`<MEMORY_ROOT>/indexes/index.sqlite`（可重建，不属于核心记忆）

## 使用规则

- 新增/修改记忆：先读对应文件，再追加或更新；保持简洁。
- 写入前标注类型、状态、来源、时间和置信度；单次推断只能进候选区。
- 检索优先级：规则/纠错 > 当前任务 > 已确认画像 > 相关事实/经历 > 候选记忆。
- 不要在记忆里放密钥、Token、Cookie、密码等敏感信息。
- 原始记录归档后，日常检索使用 `L0-portable` 和 L1-L3。
- 删除索引后用 `python scripts/memory_search.py index --rebuild` 重建。
