# 排错：先找请求在哪一层失败

## 按症状查

| 症状或原文 | 先取的证据 | 处理与验收 |
| --- | --- | --- |
| GPT 能用；Gemini 报 not supported when using Codex with a ChatGPT account | 当前对话 modelProvider；新对话默认提供商；中转有无对应请求 | 旧对话若为 openai，请求仍送到 OpenAI。新建使用 local-unified 的工作对话；不靠重启自动迁移历史 |
| 菜单看到 Gemini，但实际聊天失败 | 新对话实际请求地址、状态、后台路由；不仅看 model/list | 模型目录只影响可选项；需要检查实际连接、认证和传输 |
| 502，URL 是 127.0.0.1 的 /responses | 直接绕过系统代理的本机健康请求，与原进程请求对照；NO_PROXY 进程值/用户值 | 保留已有例外并加入本机地址；完全退出并重开桌面。仅测试进程成功仍不能算桌面成功 |
| 代理重启后 GPT 502 / OpenAI upstream is unreachable，或 Gemini 503 / Token refresh failed / client error (Connect) | 当前系统代理地址、该端口监听者、中转实际进程的 HTTP_PROXY/HTTPS_PROXY、进程启动时间；用当前代理做无认证连通检查 | 地址不一致且旧端口不可达时，只重载确认身份的后台进程，使其继承当前代理；随后验证两款模型回复。参见 [端口变化与恢复](proxy-port-recovery.md) |
| Google 授权服务器连接失败，但本机 /health 为 200 | oauth2.googleapis.com 的无认证连通性、失败层及脱敏异常类型 | 本机存活不代表能访问 Google；Connect 错误不能直接当作登录失效或账号被封。先修连接，不删除登录 |
| 开机等待代理后正常，使用途中重开代理又断线 | 启动器是否在启动成功后退出；是否只等待一次、没有处理地址变化 | 按用户所需设置后台端口跟随，不新增用户手动操作；端口不变时不反复重启，不打开 Codex 窗口 |
| 503 / Proxy service is currently disabled | 反重力 proxy.enabled；请求时间对应日志 | 备份后通过受支持设置启用；重载后复查，端口在监听不代表内部服务已启用 |
| Connection refused / 10061 | 两段端口与实际进程，权限状态 | 确认服务启动。命令被沙箱拒绝要提权检查，不先宣称端口不存在 |
| 服务测试时在，结束后不在 | 启动器退出后的进程、退出时间和日志 | 检查执行工具是否回收子进程，使用经允许的独立启动方式；复查进程持续存在 |
| 401/403 / Invalid token | 失败发生在哪一段；本机上游密钥是否注入进程，仅输出是否存在 | Antigravity 用本机反代密钥，GPT 用原 ChatGPT 认证，不互换，不把秘密粘贴到日志 |
| ConvertFrom-Json 报错、出现乱码 | 用显式 UTF-8 重新解析；确认读取的确是预期文件 | PowerShell 5.1 默认编码可能误读。不要直接把缓存当损坏，不将整份异常对象输出 |
| Python “拒绝访问”/ Unable to create process | 沙箱结果、基础 Python、venv 的 pyvenv.cfg 和实际文件 | 先区别权限与解释器丢失。授权后使用同一已验证路径运行；不要盲目重装 |
| WebSocket 405 / Unsupported upgrade request | 错误 URL 是否 ws://；选中的 provider 和 supports_websockets | 本方案使用 Responses HTTP，并设置自定义 provider supports_websockets=false；不只安装 websocket 库就宣称解决 |
| model_providers contains reserved built-in provider IDs: openai | 配置中是否写了 model_providers.openai | 撤销测试性覆盖，用新的自定义 ID；不修改内置实现 |
| HTTP 200，但文本说旧模型不可用 | 实际文本；/v1/models 与当前账号状态 | 选择实际可用的新 ID并完成生成测试。健康码与回显字符串不是模型资格保证 |
| Gemini 未出现在中转 /v1/models | 运行中转的进程是否有 LOCAL_GEMINI_PROXY_KEY；provider 注册是否完成 | --api-key-env 只记录变量名；必须把值注入实际服务进程，重启后验证 |
| 切模型后已有聊天记录不可用 | 该任务 provider、创建时间、恢复方式 | 新任务验收；旧任务保留。不要直接编辑活动 rollout 或数据库 |
| 重开后菜单仍旧 | 桌面是否完全退出；实际 CodexHome/项目配置；目录路径 | 找实际加载来源，不把“文件已经写好”等同于应用已重载 |
| 端口被占用 | 监听 PID、可执行路径和服务身份 | 未知程序不终止；选空闲端口并同步修改上游注册、启动参数、Codex 配置和测试 |
| ChatGPT 登录过期 | Codex 登录状态，不输出 token | 用户在该电脑重新登录；中转只读现有认证，不能承诺自动续期 |
| 存在 antigravity-openai.json | 配置是否另有合法用途、是否会选付费 API | 暂停依赖该配置的部署并核对，不删除、不自动使用付费连接 |
| 新增模型后原来的 Gemini 消失 | provider 注册前后的完整 models 列表；原目录和新目录的 ID | provider set 的 --model 是整体替换。合并完整旧列表，再生成候选目录；不要用原生 GPT 快照替代已有混合目录 |
| antigravity-providers.json 用 JSON 解析在开头报错 | 文件是否由当前中转的安全存储接口生成 | 该版本使用 Fernet 加密；扩展名不是明文保证。用 load_provider_config_read_only 取必要字段，写入用 CLI 或 set_provider_config，不按 UTF-8 错误重建或打印全文 |
| 扩展列表时发现旧 Gemini 的 use_responses_lite 被改变 | 追加前后每个已有模型的完整字段及字段是否存在 | 用 --base-catalog 保留旧条目，只有 --native 初始化才调整原生传输标记。发现差异停止发布，不能忽略保护断言 |
| 3.8 Flash 没有无后缀 ID，或 Pro 返回其他模型标识 | 8045 实际列出的 ID、请求 ID、正常回复、返回 model 字段 | 本机用过 gemini-3.8-flash-high；3.1-pro-high 响应曾为 gemini-pro-agent。按实际可用路由测试并记录，不自行创造别名或凭返回标识猜版本 |

## 最小证据输出

保留：时间、软件版本、模型 ID、提供商 ID、回环地址与端口、启用状态、HTTP 状态、脱敏错误、是否收到正常文本、用户是否在桌面确认。

不保留到公开材料：账号文件内容、真实 API Key、Authorization 请求头、Cookie、OAuth 参数、完整环境变量、完整模型缓存、聊天全文和未脱敏截图。

scripts/diagnose.py 只读取必要字段。检查历史会话时传入明确的 --rollout；不要为寻找一个 provider 把整份大型会话文件打印出来。

## 三个容易误判的边界

1. 新建临时测试任务使用新连接，用户旧对话可能仍用原连接。
2. 临时测试进程的环境与已经运行的桌面进程不同。
3. 程序在监听、接口返回 200、实际生成成功、用户桌面收到回复，是四种不同证据。

同一方案反复出现新问题时暂停叠加修改，回到最小原 GPT 基线，再逐层验证。只修已定位的原因。
