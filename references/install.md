# 安装流程：供执行此 Skill 的 Codex 使用

这些步骤由助手执行。用户主要负责账号登录、需要费用时的决定，以及最后在桌面发送消息。保存检查记录的位置沿用用户已确认目录；若目标电脑尚无约定，先问一次。

## 1. 检查与备份

- 确认 Windows、Codex 桌面及其实际配套 CLI。先用 Get-Command 查找；若返回 .ps1/.cmd 包装脚本，继续定位真实 codex.exe。优先使用桌面配套可执行文件；找不到时检查正在运行程序及用户安装目录，不固定某个版本子目录。probe_app_server.py 的 --codex 需要真实可执行文件，不能传 PowerShell 包装脚本。
- 确认 Python 3.11+ 的真实可执行路径。没有时从 Python 官方来源安装；不要覆盖其他项目 Python。
- 解析 CODEX_HOME 或用户 .codex 目录。读取配置时只输出 model、model_provider、base_url 等需要的字段，不输出整个认证文件。
- 先让原 GPT 完成一次正常对话。若原 GPT 已坏，先查清现有故障，再考虑新接入。
- 在目标电脑本地创建带时间的备份：config.toml、拟修改的反重力配置，以及用户 NO_PROXY 原值。认证文件只有确需修复时才本机备份，绝不打包上传。
- 保留原生 models_cache.json 的本机快照，用于生成模型目录；它可能包含很长的内部说明，不应公开发布。

只读检查：

~~~powershell
& $pythonExe "$skillRoot\scripts\diagnose.py" --codex-home $codexRoot
~~~

可用 --rollout 指定当前任务的确切 rollout 文件，只读取首条元数据确认 model_provider，不扫描全部聊天内容。

## 2. 准备 Antigravity Tools

从 references/sources.md 指向的官方项目 Releases 获取适合目标电脑的 Windows 安装包，核对版本、来源和发布方提供的校验信息。历史基线为 4.7.2；不把旧资料文件夹里的安装程序当成当前已安装版本。

用户自行完成该电脑的账号授权。不要复制另一台电脑的账号目录、Cookie 或 token。若登录、地区、账号资格或可用额度不满足，报告具体阻碍；不自动购买替代 API。

在反重力中确认：

- 代理服务 enabled=true。
- 仅本机访问（allow_lan_access=false），记录实际端口，示例为 8045。
- 记录本机密钥的位置，只让本机程序读入内存；不要把密钥写进命令行、聊天或 Skill。
- 不执行“同步 Codex”。
- 健康接口成功不等于模型能生成。使用带认证的 /v1/models 确认可用 ID；再用小请求验证实际文本。HTTP 200 中的“模型已下线”不是成功。

不要硬编码 Gemini 模型名称。历史通过的是 gemini-3.7-flash-high；办公室电脑使用实际列出且调用成功的 ID。

## 3. 安装独立中转

在目标电脑 Codex 目录下的 tools/codex-antigravity-unified 建独立 Python 环境。该目录如有现成安装，先检查而不是覆盖。

~~~powershell
$toolRoot = Join-Path $codexRoot 'tools\codex-antigravity-unified'
& $pythonExe -m venv $toolRoot
$bridgePython = Join-Path $toolRoot 'Scripts\python.exe'
& $bridgePython -m pip install 'https://github.com/Reedtrullz/codex-antigravity-auth/archive/3b34116913969d24c120ed9c3f0e41ff71c551da.zip'
~~~

固定提交用于可复现；依赖解析仍可能随时间变化。核对安装结果与 --help，记录版本。遇到上游不兼容时先定位，更新提交后重新验收，不声称沿用历史验证。

用已确认的 $proxyPort、$geminiId 注册本机上游：

~~~powershell
$bridgeCli = Join-Path $toolRoot 'Scripts\codex-antigravity.exe'
& $bridgeCli provider set google-antigravity --base-url "http://127.0.0.1:$proxyPort/v1" --api-key-env LOCAL_GEMINI_PROXY_KEY --model $geminiId --display-name 'Gemini'
~~~

这是 CLI 的配置动作，不要直接把真实密钥作为参数。LOCAL_GEMINI_PROXY_KEY 要由运行中转的进程读取本机反重力配置后设置；只保存变量名不会让模型自动可见。

确认 GPT 走原 ChatGPT 认证：

- 启用 ANTIGRAVITY_OPENAI_USE_CODEX_AUTH=1。
- 清除中转子进程中的 OPENAI_API_KEY 和 OPENAI_BASE_URL，不改用户其他应用的全局 API 环境变量。
- 同时检查 CodexHome 和用户默认 .codex 中的 antigravity-openai.json。这个固定版本会读取默认目录的 API 配置，即使设置了自定义 CODEX_HOME。存在任一就停止自动启动并核对，不擅自删除。任何 GPT 生成前还要检查网关 /health 的 openai_upstream.kind 必须是 codex_oauth；只看环境变量不够。
- 不覆盖 auth.json，也不把 ChatGPT 登录令牌当成反重力密钥。
- 当前上游中转依赖 Codex 维护登录；过期时在目标电脑重新登录，不能声称中转会自动刷新一切凭据。

## 4. 启动与网络例外

复制 scripts/Start-Bridge.ps1 到 $toolRoot。将原生模型缓存快照保存为该目录 native-models.json，保留原文件内容，仅供本机读取。

根据实际安装路径调用：

~~~powershell
& "$toolRoot\Start-Bridge.ps1" -ToolRoot $toolRoot -CodexRoot $codexRoot -AntigravityExe $antigravityExe -ProxyConfigPath $proxyConfigPath -GatewayPort $gatewayPort
~~~

脚本使用 UTF-8 读取 JSON，任何解析失败都会中止而不是输出整份文件。模型缓存读取失败先检查编码，不直接推断源文件损坏。脚本不自动修改反重力 enabled，须在第 2 步确认。

如果网关端口已有进程，脚本会停止并保留现状：同一模块名不足以证明它属于这次安装。先检查其实际 Python、CodexHome、上游和启动记录；需要重启时只操作已确认的具体进程。脚本会在退出时恢复调用者的环境变量，密钥只由已启动的子进程继承。

NO_PROXY 必须覆盖 localhost、127.0.0.1、::1，并保留已有例外。分别检查测试进程、用户环境和重新启动后的 Codex 桌面进程。只给测试进程设置 NO_PROXY 不代表桌面也继承了它。

需要持久化时，备份原用户值，合并后用当前用户环境设置保存（例如 setx NO_PROXY $merged）；不要覆盖系统级环境或原有域名。不要把密钥放入用户环境。已运行的桌面要完全退出并重新打开才能读取新环境。

Start-Process -WindowStyle Hidden 只表示隐藏窗口，不证明脱离执行工具生命周期。若运行环境会回收子进程，可在权限允许时用 Win32_Process.Create 启动同一个已审查的脚本，或由用户从桌面快捷方式启动。不要绕过被拒绝的执行权限。启动器退出后再检查两端服务，不能只在同一工具调用里看到端口就宣称持久运行。

登录自启动可以是当前用户 Startup 目录中指向该脚本的快捷方式，传入这台电脑实际参数，并使用隐藏窗口。记录捷径路径供撤销；无需管理员或系统服务。自启动尚未实测重新登录时写“已配置、未验收”，不是“已验证”。

## 5. 模型目录与配置

运行中转后，其 /v1/models 应包含带前缀的 Gemini ID，例如 google-antigravity:gemini-3.7-flash-high。冒号是当前统一中转命名，不能照搬截图中的斜杠名称。

使用本机原生目录与中转返回的实际元数据生成目录：

~~~powershell
& $bridgePython "$skillRoot\scripts\build_catalog.py" --native "$toolRoot\native-models.json" --gateway "http://127.0.0.1:$gatewayPort" --model $qualifiedGeminiId --output "$toolRoot\combined-models.json"
~~~

必须保留 GPT 的原生元数据。不要把 GPT 完整模板与模型指令复制给 Gemini；不要将所有 GPT 名称重命名映射到 Gemini。目录是静态文件，以后增加模型需要刷新。

先把下面连接字段写入独立 bridge-test.toml，用验证脚本的 --test-config 参数测试；该参数只用于临时对话，不修改全局配置。验证后才把这些字段合并进全局 config.toml。下面不是替换整份配置的模板。顶层字段必须位于所有表之前：

~~~toml
model = "目标电脑原来的GPT模型ID"
model_provider = "local-unified"
model_catalog_json = '目标电脑生成的combined-models.json完整路径'

[model_providers.local-unified]
name = "GPT + Gemini"
base_url = "http://127.0.0.1:51122/v1"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
~~~

把端口、路径替换成实际值。如果 local-unified 已存在且属于其他配置，先识别归属，选择独立 ID，不直接覆盖；后续验收的提供商 ID 保持一致。

使用 TOML 解析器验证修改结果。比较修改前后结构，除计划中的顶层 model_provider、model_catalog_json 和新增提供商外，其他配置应保留；默认 GPT model 保持原值。不要将 model 写进 [model_providers.xxx] 内。

内置 openai ID 不可覆盖。给 openai_base_url 改地址也不是已验证的旧对话迁移方案：可能引入 WebSocket 与 HTTP 兼容问题。旧对话优先保留，新建工作对话使用新提供商。

## 6. 四层验收

1. **本机服务层**：两个端口由预期程序占用，均为回环监听；反重力 enabled=true；健康与模型列表符合预期。未知占用者不杀进程。
2. **真实请求层**：GPT 路由记录为 openai，Gemini 为 byok/google-antigravity；两者返回正常文本。日志只提取时间、模型、路由、状态，不复制原始请求/响应或凭据。
3. **桌面后台层**：用 probe_app_server.py 通过 thread/start、turn/start 创建临时新对话；分别传真实 GPT/Gemini ID，要求 completed 和指定回显。此脚本的 NO_PROXY 明确记录为测试进程设置，不能取代第 4 层。
4. **用户桌面层**：完全退出并重开，在新建的 Codex/ChatGPT Work 工作对话中分别发送“你好”。以桌面实际收到回复作为最终验收。普通 ChatGPT 网页聊天不等同于本机 Codex 工作对话。

示例：

~~~powershell
& $bridgePython "$skillRoot\scripts\probe_app_server.py" --codex $codexExe --model $qualifiedGeminiId --cwd $testWorkDir --expected-provider local-unified
~~~

全局配置尚未切换时，在上述命令末尾加 --test-config $testConfigPath，指向第 5 步的独立 TOML 文件。临时配置验收成功后合并全局，再去掉 --test-config 重测新对话默认连接。脚本在生成前检查网关报告的 GPT 认证必须是 codex_oauth。

第一次文本通过后，再按用户需要做一次无副作用本地工具调用，例如打印确认文字。不用“你是什么模型”的自报家门代替路由核验。

若用户仍在旧对话，先查询其 modelProvider，确认与新配置区别后再指导操作。保留旧记录，不改活动数据库或进行批量会话迁移。

## 7. 回退与交付

- 记录本次实际新增的提供商、目录、启动项、进程和 NO_PROXY 值。
- 如果配置自备份后没被别人修改，可恢复该备份；若有其他更改，只撤销本次字段，保留其他改动。
- 停用本次启动项，恢复原 GPT 提供商及原模型目录设置，重开并验证原 GPT。
- 只停止已确认属于本次中转的具体进程，不按名称批量结束所有 Python。
- 用户 NO_PROXY 只在当前值仍等于本次写入值时恢复原值；若已有新增例外，合并处理。
- 登录与模型缓存不进入迁移包。用户未要求卸载时无需删除安装目录。
- 交付状态写清：桌面两模型是否实际验收、工具调用范围、重启/自启动是否验证，以及恢复入口。
