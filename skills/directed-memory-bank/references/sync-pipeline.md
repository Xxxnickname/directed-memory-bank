# 增量同步流水线

目标：把"新发生的会话"转成 L1/L2/L3，**只处理新增部分**，重复运行不产生重复记忆。

## 1. 输入契约

调度脚本在启动前写一个清单文件，每行一条：

```text
<会话文件绝对路径>|<起始行号>
```

- `<起始行号>` 来自水位线（上次处理到哪一行）；首次处理写 0。
- 清单只列**未处理**的会话，避免把整个会话目录灌进上下文。
- 水位线文件放在记忆库根目录（如 `.sync-state.json`），是**唯一**判定"处理到哪"的依据；不要用文件修改时间去推断。

## 2. 幂等规则

1. 处理前先读水位线；只处理起始行号之后的内容。
2. 写入一律**追加**（L2 场景流水绝不覆盖）。
3. 成功写入后才推进水位线；失败则不推进，下次重跑。
4. 机器关机或休眠错过触发，用"登录时补跑"而不是回填时间。

## 3. 提炼提示词（可直接复用）

> 任务：把尚未保存的会话内容按 L0→L3 分层增量写入记忆库，并执行受控自动学习。
>
> 输入：清单文件中每行 `<会话文件绝对路径>|<起始行号>`；只处理起始行号之后的新增内容，之前已处理部分不要重复。
>
> 步骤：
> 1. 按行读取，跳过前 N 行，只提取新增部分里的**真实用户消息**与**助手最终回复**；跳过注入的规则文件、环境上下文、技能说明和助手内部思考步骤。不要把整个文件灌进上下文。
> 2. 提炼 L1 原子事实，写入 `L1-facts/YYYY-MM-DD.md`（不存在则新建，存在则追加）。只记：做了什么、关键决定、方案或规则变化、遗留问题、用户偏好，不写闲聊。
> 3. 写 L2 会话流水到 `L2-scenarios/YYYY-MM-DD.md`（追加，绝不覆盖）。
> 4. 有进行中任务则更新 `L2-projects/` 对应文件（一任务一文件）。
> 5. 把"稳定偏好 / 长期背景 / 固定规则"追加到 `L3-profile/user-profile.md`，去重，不写一次性任务细节。
> 6. 受控自动学习：单次观察、模型推断、未确认偏好写入 `controlled-memory/candidates.md`；只有用户明确确认，或至少两次独立一致证据，才升级到 L3。
> 7. 冲突或纠错写入 `controlled-memory/corrections.md`，记录旧结论、新结论、来源和影响范围，不得静默覆盖。
> 8. 时间敏感、低置信度或长期未验证的内容写入 `controlled-memory/review.md`，不主动当作当前事实注入。
> 9. 每条新增或升级记忆记录类型、状态、来源、创建/更新时间和置信度；候选用 `observed`/`probable`，已确认用 `confirmed`。
> 10. API Key、密码、Cookie、令牌一律用 *** 打码，绝不写入任何笔记。
> 11. 只更新记忆库，不修改任何代码。结束后报告新增事实、更新任务、候选、画像升级、纠错/复核和未处理风险。

## 4. 收尾报告格式

```text
新增事实：<文件:条数>
更新任务：<项目文件 —— 变化>
候选记忆：<条数 + 一句话>
画像升级：<条数；无则写 无>
纠错 / 复核：<条数；无则写 无>
未处理风险：<清单>
```

## 5. 调度

Windows 示例（每天 21:10，错过则登录补跑）：

```powershell
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<记忆库>\automations\memory-sync.ps1"'
$trigger = @(
  (New-ScheduledTaskTrigger -Daily -At 21:10),
  (New-ScheduledTaskTrigger -AtLogOn)
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'AgentMemorySync' -Action $action -Trigger $trigger -Settings $settings -Force
```

触发词同样可用：用户说"更新记忆 / 记忆存档 / 存档并结束"时，直接跑同一流程，不等定时任务。

## 6. 常见失败与处置

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| 记忆里出现"规则文件原文" | 把注入上下文当成了用户发言 | 过滤：只保留真实用户消息与助手最终回复 |
| 同一段内容被记两次 | 水位线没推进或中途失败仍推进 | 先写后推水位线，失败不推进 |
| 候选区里堆了旧内容 | 缺少去重与衰减 | 写入前查重；长期未验证的移入复核区 |
| 提炼时上下文爆炸 | 直接把整份会话读进模型 | 改成按行跳过 + 只取增量片段 |
| 索引指向已删除文件 | 只增不删 | 增量索引时删除"已不存在的路径" |
