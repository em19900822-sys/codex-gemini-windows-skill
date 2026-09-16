# 来源与复现基线

维护日期：2026-09-16。安装前重新检查目标电脑与上游变化，不把历史版本描述为最新。

## 官方文档

- Codex Skills：https://developers.openai.com/codex/skills
- 高级配置：https://developers.openai.com/codex/config-advanced
- 配置项：https://developers.openai.com/codex/config-reference
- 桌面后台协议：https://developers.openai.com/codex/app-server
- Python Windows 安装：https://www.python.org/downloads/windows/

`thread/start`、`thread/resume` 与 `turn/start` 是不同操作。测试一个新线程不能证明用户的旧线程也改用了新提供商。具体字段以目标电脑版本的协议与官方文档为准。

## 第三方组件

- Antigravity Tools / Antigravity-Manager：https://github.com/lbjlaq/Antigravity-Manager
- 统一中转：https://github.com/Reedtrullz/codex-antigravity-auth
- 已部署中转提交：`3b34116913969d24c120ed9c3f0e41ff71c551da`（包版本 2.2.0）。
- 已核对反重力同步实现提交：`c3c10844963ce371050fe4302887edd554daaaae`。不同版本是否仍有相同写入行为必须再检查。

已成功环境：Antigravity Tools 4.7.2；Codex CLI 0.154.0-alpha.6.2；Windows Python 3.14.4。

如果复用固定提交，先读取该提交的 README、安装元数据和依赖要求；不要把网络上任意“一键脚本”直接执行。本仓库引用这些项目，不复制其安装程序、源码或账户数据，不代表上游官方支持本 Skill。

## 证据分级

- **已观察**：旧对话绑定 `openai` 时 Gemini 被 OpenAI 拒绝；新对话绑定 `local-unified`。
- **已复现实测**：无本机代理例外时测试进程得到 502，加入本机 `NO_PROXY` 后桌面后台协议返回正常 Gemini 文本。
- **已观察**：测试后两个服务进程退出；独立后台启动后，在后续多个检查中仍存活。不能把具体退出原因或长期可靠性一概推断为已证实。
- **用户验收**：原 GPT 与 Gemini 3.7 两个模型都在桌面实际回答。
- **新增模型后台实测（2026-09-16）**：`gemini-3.5-flash-lite`、`gemini-3.8-flash-high`、`gemini-3.1-pro-high` 分别通过反代回复和 Codex 新临时对话的正常回复；正式 `model/list` 读取包含三者与原 GPT/3.7。3.8 通过一次只打印确认文字的工具调用，GPT 复测正常。新增三者尚未获用户桌面分别切换验收；详见 [add-models.md](add-models.md)。
- **源码核对**：固定中转版本的 `byok.py` 中 `set_provider_config` 替换整个 `models` 字段、保留未指定连接字段；`storage.py` 负责加密读写；`server.py` 的模型清单及 BYOK 路由按请求加载 provider 配置。默认 provider 配置路径位于用户 `.codex`，不随 `CODEX_HOME` 改变。应通过其只读/API接口操作，不把加密文件当普通 JSON。
- **未扩展验证**：新电脑、其他账号、后续版本、所有多模态功能，以及 Windows 重新登录后的自启动，需要分别验收。
