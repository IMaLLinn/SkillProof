# 测试指南

本目录保留团队可重复执行的测试方法、验收标准和题库发布依据。测试代码位于 `backend/tests/` 和 `frontend/tests/`，测试运行和 CI 检查工具位于 `scripts/`。

## 本地运行检查

按根目录 README 启动后端后，另开终端执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

预期返回 `Status: ok`。接口文档位于 http://127.0.0.1:8000/docs 。

## 自动化测试

按根目录 README 准备 Python 环境，在仓库根目录 PowerShell 执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

后端与脚本静态规范检查（Ruff）：

```powershell
.\backend\.venv\Scripts\python.exe -m ruff check backend scripts
.\backend\.venv\Scripts\python.exe -m ruff check --fix backend scripts
```

后端用例使用临时数据库或独立夹具，不写入开发数据库。需要单独运行某个测试模块时，例如：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p test_question_bank_sync.py -v
```

| 测试文件 | 持续验证的行为 |
|---|---|
| `test_auth_catalog.py` | 注册、登录、会话、CSRF、输入边界及岗位能力树 |
| `test_database.py` | 迁移、持久化、约束、事务及题库模型 |
| `test_scoring.py` | 难度加权综合分、六维分数、多选判分及排序 |
| `test_reports.py` | 本人报告查询、权限、异常响应及快照稳定性 |
| `test_assessments.py` | 抽题、保存、提交、权限和重复请求 |
| `test_assessment_flow.py` | 默认题库、真实会话和评分下的完整测评流程 |
| `test_answer_save_order.py` | 真实 HTTP 下延迟和并发保存的版本保护 |
| `test_question_bank_sync.py` | 旧草稿升级、题库增改归档、版本冲突及快照保护 |
| `test_reset_local_db.py` | 本地重置确认、环境限制、备份和失败保护 |
| `test_qa_checks.py` | CI 运行器及 Issue 必测清单检查逻辑 |
| `test_coverage_report.py` | 分层覆盖率门禁、防回退与改动代码覆盖率提醒检查逻辑 |
| `test_lint_checks.py` | Ruff 静态规范配置与检查执行逻辑 |

前端检查：

```powershell
Set-Location frontend
npm run lint
npm run build
npm test
```

| 测试文件 | 持续验证的行为 |
|---|---|
| `historyUtils.test.ts` | 历史对比计算与限制 |
| `historyApi.test.ts` | 历史接口数据校验 |
| `HistoryPage.test.tsx` | 历史页面展示与交互 |
| `LearningRecommendations.test.tsx` | 学习建议展示与失败重试 |

## 覆盖率标准与报告

PR 对应的前端、后端、QA 三项 CI 检查必须全部通过。覆盖率按层设置门槛，报告文件已被 Git 忽略，不要提交：

| 范围 | 统计指标 | 固定底线 | 防回退规则 | 未达标处理 |
|---|---|---|---|---|
| 后端（`backend/app/`） | 语句 / 分支 | 语句 ≥ 90%，分支 ≥ 80% | 不低于 `main`（允许 0.5 个百分点波动） | 阻断合并 |
| 前端逻辑层（`frontend/src/lib/*`、`frontend/src/api.ts`、`frontend/src/authValidation.ts`） | 语句 / 分支 | 语句 ≥ 85%，分支 ≥ 80% | 不低于 `main`（允许 0.5 个百分点波动） | 阻断合并 |
| 前端页面与组件层（`frontend/src/pages/*`、`frontend/src/components/*`、`App.tsx`、`main.tsx`） | 语句 / 分支 | 不设总百分比门槛 | 仅输出参考数据，已有组件测试须全部通过 | 不阻断 |
| 本次 PR 改动代码（后端 + 前端逻辑层） | 新增/修改语句 | 建议 ≥ 80% | — | CI 警告提醒，暂不阻断 |

约定与边界：

- 前端计算、表单校验与数据整理逻辑统一抽离到逻辑层 `.ts`，避免塞进 `.tsx` 页面文件绕过覆盖率检查。
- 纯展示页面不凑覆盖率，复杂交互规则按需补充组件测试；视觉样式与完整主流程（登录 → 选岗 → 答题 → 提交 → 查看报告）本阶段暂不引入浏览器自动化，继续按验收清单人工验证。

后端统计 `backend/app/` 的语句覆盖率和分支覆盖率。在仓库根目录 PowerShell 执行：

```powershell
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 -m coverage run scripts/run_backend_tests.py
.\backend\.venv\Scripts\python.exe -X utf8 -m coverage html
.\backend\.venv\Scripts\python.exe -X utf8 -m coverage json
.\backend\.venv\Scripts\python.exe -X utf8 scripts/report_coverage.py backend --check
```

最后一条命令分别列出语句覆盖率和分支覆盖率，并校验固定底线；附加 `--baseline <main报告>` 和 `--diff-base <基线提交>` 可在本地模拟 CI 的防回退与改动代码检查。`coverage report` 和网页报告里的 `Cover` 列是语句与分支合并计算的结果，不要当作语句覆盖率。网页报告位于 `htmlcov/index.html`，未执行的代码行标红，只执行了部分分支的行标黄。

前端统计 `frontend/src/` 的分层和整体覆盖率：

```powershell
Set-Location frontend
npm run coverage
Set-Location ..
.\backend\.venv\Scripts\python.exe -X utf8 scripts/report_coverage.py frontend --check
```

`npm run coverage` 会在终端输出各文件覆盖率并生成 `frontend/coverage/index.html`、`coverage-summary.json` 与 `coverage-final.json`；`report_coverage.py frontend --check` 会拆分逻辑层与页面/组件层并校验逻辑层底线。

## CI 与必测清单

`backend-checks` 先执行 `python -m ruff check backend scripts` 做静态规范检查，再调用 `scripts/run_backend_tests.py` 执行后端测试；`frontend-checks` 在 lint 和构建后调用 `scripts/run_frontend_tests.py` 执行前端测试。两个任务都会在同一次 CI 中检出本次 PR 合并基线（`main`）跑一次基线覆盖率，随后运行 `scripts/report_coverage.py --check` 校验固定底线与防回退规则，并在 GitHub Actions 运行页摘要（Summary）中展示分层结果和改动代码覆盖率提醒。完整的网页报告作为附件（Artifacts）`backend-coverage` 和 `frontend-coverage` 挂在同一运行页底部，保留 14 天（即使覆盖率门禁未通过也会上传，便于排查未覆盖代码）。

`qa-checks` 根据 PR 描述中的 `Closes #编号` 或 `Refs #编号` 读取 `tests/acceptance/issues/编号.json`，检查清单里的每个测试是否在本轮前端或后端测试中通过。前端 ID 由仓库相对路径、各层 `describe` 标题和测试标题组成，以 ` > ` 分隔，例如 `frontend/tests/historyUtils.test.ts > historyUtils > compares two reports`。

测试文件只允许放在 `backend/tests/test_*.py` 或 `frontend/tests/`（含子目录，文件名为 `*.test.ts` 或 `*.test.tsx`）。PR 变更中，文件名匹配 `test_*.py`、`*_test.py`、`*.test.*` 或 `*.spec.*`，但不符合上述目录和命名要求，CI 会报错。

新增或调整功能时同步维护对应 Issue 的 `required_tests`。允许登记已有测试。如果 PR 修改了 `frontend/src/` 或 `backend/app/`，却没有登记对应层的测试，CI 会给出不阻断的审查提示，由审查者判断覆盖是否充分。

CI 检查器需要工作流提供 PR 元数据、变更文件及本轮测试结果，不能用历史日志替代，也不支持旧的 `--pr` 调用方式。

## 人工验收与题库维护

- 完整浏览器流程及异常场景按 [Alpha 测试计划](alpha-test-plan.md) 执行。
- 默认题库创建测评的检查方法见 [Issue #41 回归说明](issue-41-default-question-bank.md)。
- 更新题目和清理本地测试数据见 [题库同步与本地重置](question-bank-sync.md)。
- [题库人工复核记录](question-bank-review.md) 是发布题库的审核依据，应随题库维护。
