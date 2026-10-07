# Portable Memory Boot

启动时优先读取：

1. `AGENTS.md`
2. `memory-bank/_index.md`
3. `L3-profile/user-profile.md`
4. 当前相关的 `L2-projects/` 与 `L2-scenarios/`

不要默认加载全部 L0 原始会话、全部日志或索引数据库。需要追溯时，再按 `L0-manifest/manifest.jsonl` 定位到 `L0-portable` 或 `L0-raw`。

记忆源文件是 Markdown/JSONL；SQLite 与向量索引只是可重建的加速缓存。
