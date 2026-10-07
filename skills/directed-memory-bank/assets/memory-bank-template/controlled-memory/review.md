# 复核与衰减

> 时间敏感、低置信度、长期未验证的记忆放这里。**未复核前不主动当作当前事实注入。**

## 记录模板

```yaml
- id: review-YYYY-MM-DD-NNN
  memory_ref: <记忆文件与条目标识>
  reason: <过期 | 低置信度 | 时间敏感 | 新旧冲突 | 长期未验证>
  last_verified_at: YYYY-MM-DD
  review_after: YYYY-MM-DD
  action: <保留 | 更新 | 降级为候选 | 标记过期>
```

复核时要么补证据升级，要么降级/标过期；不要既不处理也不删除，任其长期堆积。
