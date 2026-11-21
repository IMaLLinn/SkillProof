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

## CI 与必测清单

`backend-checks` 调用 `scripts/run_backend_tests.py` 执行后端测试。`frontend-checks` 在 lint 和构建后调用 `scripts/run_frontend_tests.py` 执行前端测试。两个任务都输出本轮通过的测试 ID。

`qa-checks` 根据 PR 描述中的 `Closes #编号` 或 `Refs #编号` 读取 `tests/acceptance/issues/编号.json`，检查清单里的每个测试是否在本轮前端或后端测试中通过。前端 ID 由仓库相对路径、各层 `describe` 标题和测试标题组成，以 ` > ` 分隔，例如 `frontend/tests/historyUtils.test.ts > historyUtils > compares two reports`。

测试文件只允许放在 `backend/tests/test_*.py` 或 `frontend/tests/`（含子目录，文件名为 `*.test.ts` 或 `*.test.tsx`）。PR 变更中，文件名匹配 `test_*.py`、`*_test.py`、`*.test.*` 或 `*.spec.*`，但不符合上述目录和命名要求，CI 会报错。

新增或调整功能时同步维护对应 Issue 的 `required_tests`。允许登记已有测试。如果 PR 修改了 `frontend/src/` 或 `backend/app/`，却没有登记对应层的测试，CI 会给出不阻断的审查提示，由审查者判断覆盖是否充分。

CI 检查器需要工作流提供 PR 元数据、变更文件及本轮测试结果，不能用历史日志替代，也不支持旧的 `--pr` 调用方式。

## 人工验收与题库维护

- 完整浏览器流程及异常场景按 [Alpha 测试计划](alpha-test-plan.md) 执行。
- 默认题库创建测评的检查方法见 [Issue #41 回归说明](issue-41-default-question-bank.md)。
- 更新题目和清理本地测试数据见 [题库同步与本地重置](question-bank-sync.md)。
- [题库人工复核记录](question-bank-review.md) 是发布题库的审核依据，应随题库维护。
