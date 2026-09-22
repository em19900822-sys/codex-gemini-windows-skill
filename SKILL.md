---
name: codex-gemini-windows-skill
description: 在 Windows 电脑安装、迁移、追加模型或排查 Codex 桌面的 Gemini 与原生 GPT 共存接入；适用于 Antigravity Tools、本地反代、多款 Gemini 同时接入、模型列表出现但不能聊天、ChatGPT 账号不支持 Gemini、502/503 和后台退出。保留原 ChatGPT 登录，不用于普通网页 Gemini 或替换付费 API。
---

# Windows 上让 Codex 同时使用 GPT 与 Gemini

完成标准是用户在目标电脑的 Codex 桌面新对话中，分别收到 GPT 和 Gemini 的实际回答。`/health` 成功、模型出现在菜单、命令行返回成功，都只是中间证据。

## 适用结构

```text
Codex 新对话 → local-unified → 本机统一中转
                              ├─ GPT → 原 ChatGPT/Codex 登录
                              └─ Gemini → 本机 Antigravity Tools → 用户独立授权的账号
```

这是第三方工具接入方案，不代表 OpenAI 官方提供 Gemini。已知可用基线见 [references/sources.md](references/sources.md)，每台电脑仍需重新验收。

## 先选任务

- 全新安装或另一台电脑：读 [references/install.md](references/install.md)，先检查已有环境，再部署。
- 已能使用、需要增加 Gemini：读 [references/add-models.md](references/add-models.md)。包含 3.5 Flash-Lite、3.8 Flash、3.1 Pro 的本机验证记录、多个模型一起追加及保留原 GPT/3.7 的流程；新电脑仍以账号实际可用 ID 为准。
- 已经安装但报错：读 [references/troubleshooting.md](references/troubleshooting.md)，先定位失败层，不先重装。
- 重启代理后再次断连、Google 授权刷新连接失败，或要保留后台自动连接但手动打开 Codex：读 [references/proxy-port-recovery.md](references/proxy-port-recovery.md)。先比较当前代理地址与后台实际继承的地址，再恢复；不要把所有 502/503 都归因于启动顺序。
- 用户只问状态：使用 `scripts/diagnose.py` 做只读检查；不要自动重写配置。
- 回退：读取目标电脑自己的备份和安装记录。优先恢复本次修改项，不从其他电脑复制配置覆盖。

## 操作边界

- 所有路径在目标电脑发现。使用 `CODEX_HOME`（如有）或用户目录；不可照搬创建者用户名、磁盘、版本目录或账号文件。
- 保留当前 GPT 模型、ChatGPT 登录、项目、插件和其他提供商设置。修改前做本机备份，不导出或公开认证备份。
- 用户在办公室电脑自行完成必要的 ChatGPT/Google 登录。Skill、GitHub 仓库和压缩包中不得包含 `auth.json`、实际 `gui_config.json`、令牌、Cookie、密钥、聊天日志或完整原生模型缓存。
- 沿用现有账号额度前说明会做少量连接测试。需要新增付费 API、订阅、充值或用量计费时，先说明费用并获得明确同意；不要把“免费”“不限量”写成保证。
- 只监听回环地址。不要把 GPT 请求映射成 Gemini；不要点击可能覆盖 Codex 配置的“同步 Codex”按钮。
- Codex 桌面窗口自启动与模型后台自启动是两项设置。用户只要求关闭窗口自启动时，不停用后台；没有发现桌面自启动项就如实说明，不能拿停用后台代替。
- `openai` 是内置提供商 ID。不要覆盖其定义，不要编辑正在运行的对话数据库来强改历史绑定。
- 当前任务是否允许写文件、联网或启动进程，以运行环境实际权限为准；权限不足应使用正式提权流程，不能把“访问被拒绝”报告为“服务不存在”。

## 脚本

Python 脚本使用 Python 3.11+ 标准库，不要求额外库。

| 脚本 | 用途 | 修改范围 |
| --- | --- | --- |
| `scripts/diagnose.py` | 检查提供商、端口、本机代理例外、服务和指定旧对话 | 只读；无模型生成 |
| `scripts/build_catalog.py` | 初始化目录，或用 `--base-catalog` 和重复 `--model` 一次追加多个模型 | 只写候选输出；追加模式完整保留已有条目，不碰账号 |
| `scripts/probe_app_server.py` | 用桌面后台协议测试一个临时新对话 | 消耗现有模型额度；不保存对话，需传本机 Codex 路径和模型 ID |
| `scripts/Start-Bridge.ps1` | 启动已配置的两段本机连接 | 本机进程、运行日志；不修改 Codex 配置和用户代理设置 |

先执行脚本的 `--help` 或查看 PowerShell 参数。脚本不能替代安装文档中的前置检查、目标电脑登录与用户桌面验收。

## 验收记录

分别记录以下状态，不合并为一句“全部成功”：

1. 原 GPT 基线、备份和实际软件版本。
2. 两个本机服务的监听地址、进程和健康检查。
3. 实际 Gemini 模型 ID 及正常文本响应（不是下线/错误提示）。
4. 临时新对话中的 GPT、Gemini 与一次必要的工具调用。
5. 用户完全退出并重开桌面后，在新对话分别发送消息并收到回答。
6. 后台启动是否在发起测试的进程退出后仍有效；登录自启动是否经过实际重新登录验证。

旧对话仍绑定 `openai` 时，新建工作对话使用新连接，旧记录保留。不要让用户在同一条旧对话里反复切 Gemini 和重启。

最终只说明已验证的范围、用户下一步与回退方式。未接触办公室电脑时，可以说 Skill 已完成；不能说办公室电脑已经安装成功。
