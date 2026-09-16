# Codex 接入 Gemini：Windows 安装与排错 Skill

把 Gemini 接到 Codex 桌面，同时保留原来使用 ChatGPT 登录的 GPT。

这个仓库提供给 Codex 执行的操作流程、排错表和辅助脚本，**不是模型、账号包，也不是反代软件本体**。没有附带登录凭据或软件安装程序。

## 在办公室电脑使用

1. 下载仓库 ZIP 并解压。
2. 打开 Codex，把解压后的文件夹路径发给它，并说：

   > 请安装这个文件夹里的 Skill，然后用它检查这台 Windows 电脑，配置 Gemini 与我原来的 GPT 共存。保留现有登录和配置，需要新增费用先告诉我，最后验收桌面实际对话。

也可以在解压目录运行 `Install-Skill.ps1`。它只把 Skill 复制到当前用户的 Codex 技能目录，不会安装反代、替换登录或修改模型配置。已安装相同内容会跳过，存在不同版本时会停止，避免覆盖。

重开或刷新 Codex 后，可直接说：

> 使用 $codex-gemini-windows-skill，帮我在这台电脑安装并验证 Gemini 和 GPT 都能用。

如果已经安装但报错：

> 使用 $codex-gemini-windows-skill 排查。GPT 能回答，但 Gemini 提示 ChatGPT 账号不支持，先检查当前对话的提供商和本地连接。

## 覆盖的重点问题

- Gemini 出现在模型列表，但旧对话仍连接 OpenAI。
- GPT 能回答，Gemini 提示 `not supported when using Codex with a ChatGPT account`。
- 本机请求也走系统代理，出现 502；`NO_PROXY` 新值没有进入已打开的桌面进程。
- 服务端口有响应，却提示 `Proxy service is currently disabled`。
- 后台进程随测试进程或软件退出，重开以后失联。
- Windows PowerShell 读取 UTF-8 文件出错、错误配置层级、认证混用。
- 模型旧别名返回下线提示，不能把 HTTP 200 当作成功。
- 权限检查失败、端口被别的软件占用，以及安全回退。

## 验证范围

流程来自 2026-09-16 一台 Windows 电脑的实际部署，最终用户确认 GPT 和 Gemini 均能在桌面回答。本仓库新增的脚本另有本地检查和隔离测试；办公室电脑尚需独立部署和验收。

发布前已通过 17 项 Python 离线测试、Windows PowerShell 5.1 安装与启动保护测试，以及 Skill 格式检查。只读诊断和模型目录生成也已在基线电脑运行验证；这些检查没有代替新电脑的实际聊天验收。

历史成功组合：Antigravity Tools 4.7.2、codex-antigravity-auth 2.2.0、Codex CLI 0.154.0-alpha.6.2。它们是复现基线，不是“最新版本”声明。`gemini-3.7-flash-high` 是当时实际通过的模型 ID，新电脑必须以账号实际可用模型和调用结果为准。

已验证的主要能力是文字对话及一次本地工具调用；不据此承诺所有图片、语音、插件或其他模型能力。

## 文件入口

- [SKILL.md](SKILL.md)：Codex 执行入口。
- [完整安装流程](references/install.md)：从检查环境到桌面验收。
- [报错排查表](references/troubleshooting.md)：按实际症状定位。
- [来源与版本基线](references/sources.md)：上游项目与官方文档。
- `scripts/`：不含账号的辅助脚本。
- `tests/`：无需联网和登录的隔离测试。

不要上传目标电脑的账号文件、密钥、日志原文或模型缓存到本仓库。遇到问题时只提供经过筛选的状态和错误信息。
