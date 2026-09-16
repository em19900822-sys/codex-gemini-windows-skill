# 在已有接入中增加 Gemini 模型

用于 GPT 与 Gemini 已经接通后，继续增加模型。全新安装先完成 [install.md](install.md)。本流程同时更新上游路由和 Codex 模型目录；只改菜单名称不能接通模型。

## 已有验证记录

以下是 2026-09-16 的本机记录，不是每个账号均有权限的承诺：

| 显示名称 | 反重力上游 ID | Codex 统一中转 ID |
| --- | --- | --- |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | `google-antigravity:gemini-3.5-flash-lite` |
| Gemini 3.8 Flash | `gemini-3.8-flash-high` | `google-antigravity:gemini-3.8-flash-high` |
| Gemini 3.1 Pro | `gemini-3.1-pro-high` | `google-antigravity:gemini-3.1-pro-high` |
| Gemini 3.7 Flash（原有） | `gemini-3.7-flash-high` | `google-antigravity:gemini-3.7-flash-high` |

新增三个模型均通过了反代短回复、Codex 临时新对话实际回复和正式 `model/list` 读取。3.8 Flash 另通过一次无副作用的 shell 输出调用，原 GPT 复测正常。新增三模型尚未获得用户在桌面逐一点击的验收，不能写成“桌面全部通过”。

3.1 Pro 的一次直接上游响应中，`model` 字段是 `gemini-pro-agent`。这是观察到的返回标识，应如实记录；不能仅凭这个字段推断或承诺底层模型版本。

## 1. 读取当前状态并备份

- 记录实际 Codex 目录、网关地址、当前模型目录路径和提供商 ID，保留默认 GPT 模型。
- 本机备份拟修改的模型目录、配置和加密提供商文件，记录时间。备份不加入 Skill、GitHub 或跨电脑安装包。
- 通过带认证的本机反重力 `/v1/models` 和少量短回复核验目标 ID。密钥由本机程序读取，不放命令行或输出。确认使用现有账号额度；需要新增收费时先征求同意。
- 账号没有某个模型权限、额度不足或返回“不可用”时，只跳过该模型并报告原因。不要换个名称伪装成功，不把网页菜单当作反代权限证明。

## 2. 追加到现有提供商，保留全部旧模型

固定基线 `codex-antigravity-auth 2.2.0` 的 `antigravity-providers.json` 是 Fernet 加密文件，不能当普通 JSON 编辑。使用已安装包的 `byok.load_provider_config_read_only` 读取结构，只提取当前提供商的模型字段进行检查，不打印整份配置。

该版本的提供商文件默认位于用户 `~/.codex`，即使设置了另一个 `CODEX_HOME` 也要核实这个实际位置。加密文件依赖本机密钥；可在本机备份，不复制到办公室电脑复用账号。

更新前检查安装版本的函数签名或 CLI `--help`，按以下规则操作：

- `provider set` 的重复 `--model` 参数表示**整体替换模型列表**，不是逐项追加。
- 动态读取已有列表，把确认可用的新 ID 按顺序去重追加。不要直接用上表四个 ID 覆盖；用户可能还装有更多模型。
- 原列表全是字符串 ID 时，可用 `provider set google-antigravity`，为合并后的每个 ID 重复传 `--model`，同时保留原 URL、密钥环境变量名称和显示名。
- 原列表含字典元数据时，不用字符串 CLI 压平。该固定版本的 `set_provider_config(models=...)` 也只接受字符串列表，不能直接传字典；先检查当前版本是否有保留元数据的受支持更新方式，无法确认就保留现状并说明限制。
- 不使用 `models add` 完成此步骤：它属于不同的原生 Google 路由，不是这里的 `google-antigravity` 本机上游。

保存后重新读取并比较：旧条目、其他提供商和原设置应保持一致。统一中转的模型列表和路由会随请求读取提供商配置；环境变量及服务设置未变时，通常无需重启网关。先检查 `/v1/models` 中新增的带前缀 ID，出现异常再查具体原因。

## 3. 生成候选模型目录

已有接入必须以当前正式目录作为 `--base-catalog`，这样既有 GPT、Gemini、条目字段及顶层元数据全部保留。`--native` 仅用于从原生 GPT 快照初始化新接入，不用于重建已有多模型目录。

变量使用目标电脑实际值；候选输出必须与输入是不同文件。以下示例假定三个新模型均已确认可用：

~~~powershell
$newModels = @(
    'google-antigravity:gemini-3.5-flash-lite'
    'google-antigravity:gemini-3.8-flash-high'
    'google-antigravity:gemini-3.1-pro-high'
)
$modelNames = @{
    'google-antigravity:gemini-3.5-flash-lite' = 'Gemini 3.5 Flash-Lite'
    'google-antigravity:gemini-3.8-flash-high' = 'Gemini 3.8 Flash'
    'google-antigravity:gemini-3.1-pro-high' = 'Gemini 3.1 Pro'
}
$catalogArgs = @(
    "$skillRoot\scripts\build_catalog.py"
    '--base-catalog', $catalogPath
    '--gateway', $gatewayUrl
    '--output', $candidateCatalogPath
)
foreach ($modelId in $newModels) {
    $catalogArgs += @('--model', $modelId)
    if ($modelNames.ContainsKey($modelId)) {
        $catalogArgs += @('--display-name', ($modelId + '=' + $modelNames[$modelId]))
    }
}
& $bridgePython @catalogArgs
if ($LASTEXITCODE -ne 0) { throw '候选目录生成失败，保留当前配置。' }
~~~

只将已验证有权限的模型放入 `$newModels`。脚本从网关读取真实元数据，已有 ID 会跳过；`--display-name` 只命名新增条目。不要借增加模型顺便重写已有条目。候选文件已存在时优先选新文件名；确需更新已有候选输出才使用 `--replace`，它不能授权覆盖输入。

## 4. 测试候选配置，再发布目录

建立独立的测试 TOML，保留现有连接设置，令 `model_catalog_json` 指向候选目录。测试文件只含 `probe_app_server.py --test-config` 支持的模型及提供商字段，不复制认证信息。对每个新增模型运行：

~~~powershell
foreach ($modelId in $newModels) {
    $probeArgs = @(
        "$skillRoot\scripts\probe_app_server.py"
        '--codex', $codexExe
        '--cwd', $testWorkDir
        '--model', $modelId
        '--expected-provider', $providerId
        '--test-config', $testConfigPath
    )
    & $bridgePython @probeArgs
    if ($LASTEXITCODE -ne 0) { throw "模型验证失败：$modelId；保留当前正式目录。" }
}
~~~

- 逐一确认临时新对话使用预期提供商，生成完成且实际回复符合要求；不能只看进程退出码或 HTTP 200。
- 复测原 GPT 和原 Gemini；涉及工具使用时，再做一次无副作用工具调用。验证文本通过不等于所有工具或多模态能力均已验证。
- 发布前按 JSON 结构深度比较：原有每个模型条目及顶层元数据不变，只增加已通过的条目；同时确认未遗漏其他既有模型。
- 备份仍有效且正式目录未被其他任务改动时，用同目录临时文件原子替换正式目录。若正式配置继续引用原路径，无需改默认 GPT 或提供商；失败即保留或恢复原目录。
- 通过 Codex 正式 `model/list` 再读一次，核对新增名称和旧模型均在。目录可读取仍不等于桌面会话已经成功。

## 5. 用户桌面验收与回退

完全退出并重新打开 Codex，在使用统一中转的新工作对话里逐一选择新增模型发送消息，再复测 GPT。旧对话可能仍绑定 `openai`；不要改活动数据库，也不要在旧对话中反复切换重试。

记录每个模型的“上游短回复、临时对话、正式列表、工具调用、桌面点击”状态。尚未做的项目写“未验收”。失败时恢复本次目录备份，并只撤销本次新增的提供商模型；若期间有其他改动，按差异恢复，保留那些改动与原 GPT 登录。
