# 迁移（换工具 / 换电脑）

完整步骤与验证清单见技能目录下的 `references/migration.md`。要点：

1. 记忆本体（L0-portable、L0-manifest、L1-L3、controlled-memory、AGENTS.md）整体拷贝。
2. `L0-raw/`、索引数据库、水位线状态文件不拷，按需重建。
3. 在新宿主重写三件事：读会话日志、定时触发、会话开始的规则加载。
4. 冒烟验证：`python scripts/memory_search.py search -q "记忆迁移"` 能返回结果。
5. 行为验证四条：已确认偏好被召回、未确认推断只进候选、纠错压过旧画像、过期事实不注入。
