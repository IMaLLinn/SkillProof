# 协作指南

> 要改东西，先有 Issue；一个 Issue 对应一个明确任务；完成后通过 PR 合并，不直接在 `main` 上开发。

流程：建立 Issue → 认领 → 创建分支 → 开发与自测 → Commit → PR → Review → 合并到 `main` → 关闭 Issue。

## Issue

标题格式 `[类型] 简短描述`，描述一个明确、可完成的任务，例如 `[Backend] 实现测评提交与自动评分接口`。

| 类型 | 含义 |
|---|---|
| `Feature` | 新功能 |
| `Bug` | 缺陷修复 |
| `Frontend` / `Backend` | 前端 / 后端任务 |
| `Content` | 题库、岗位能力树、学习资源 |
| `Test` | 测试 |
| `Docs` | 文档 |
| `Deploy` | 部署与环境 |

优先级：`P0` Alpha 必须完成；`P1` 应尽量完成，不影响核心流程；`P2` 优化项。一个 Issue 可以同时有多个类型标签和一个优先级标签。

正文至少包含：

```markdown
## 任务描述
## 背景 / 原因
## 验收标准
- [ ] 可验证的条件
## 负责人
@GitHub用户名
## 优先级
P0 / P1 / P2
```

Bug Issue 标题用 `[Bug] 简短描述`，正文写明 Bug 描述、复现步骤、实际结果、期望结果、严重程度和环境（浏览器、操作系统、Commit / 版本）。

认领后把自己设为 Assignee，确认验收标准后再建分支。每人同时进行中的核心 Issue 不超过 2 个。

## 分支

`main` 保持可运行，禁止直接在 `main` 上开发。分支名格式 `类型/Issue编号-简短名称`：

```text
feature/18-assessment-submit
fix/25-score-error
docs/32-scrum-week6
test/40-assessment-api
content/19-database-questions
```

## Commit

一个 Commit 对应一次明确的修改，格式 `类型: 修改内容 (#Issue编号)`：

| 类型 | 含义 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构，不改变功能 |
| `style` | 页面样式或格式调整 |
| `chore` | 配置、依赖、工程维护 |

例如 `fix: correct multi-choice scoring (#25)`。避免 `update`、`修改`、`final` 这类说明。

## Pull Request

一个主要 Issue 原则上对应一个 PR，标题 `[类型] 功能描述 (#Issue编号)`。正文：

```markdown
## 对应 Issue
Closes #12

## 本次修改
- ...

## 验证方式
1. ...

## 尚存问题
无 / 当前仍存在……
```

`Closes #编号` 会在合并后自动关闭 Issue。提交前按[测试指南](docs/testing/README.md)完成本地检查（含后端 Ruff 静态规范检查与前端 ESLint），并维护对应 Issue 的必测清单；CI 全部通过后再请求 Review。

前端代码请将计算、表单校验与数据整理逻辑统一放在逻辑层（`frontend/src/lib/*`、`frontend/src/api.ts`、`frontend/src/authValidation.ts`），不要塞进 `.tsx` 页面组件。CI 会强制检查：

- 前端、后端、集成、QA 四项检查 100% 通过；
- 后端（`backend/app/`）语句 ≥ 90%、分支 ≥ 80%，且不低于 `main` 超过 0.5 个百分点；
- 前端逻辑层语句 ≥ 85%、分支 ≥ 80%，且不低于 `main` 超过 0.5 个百分点（页面与组件层仅作参考，不设总百分比门槛）；
- 本次 PR 新增/修改的后端与前端逻辑层语句覆盖率建议 ≥ 80%（低于时 CI 提醒，暂不阻断）。

## Review

PR 至少经另一名成员批准（Approve）后，再由其他成员合并。重点检查：

- 是否符合 Issue 验收标准
- 能否正常运行，是否影响已有功能
- 是否有明显逻辑问题，接口是否符合约定，前端业务逻辑是否按约定抽离到逻辑层
- 是否提交了不应提交的文件（如 `.env`、数据库文件）
- 改动代码覆盖率提醒与必要测试是否充分

有问题在 PR 中提出，开发者继续提交到原分支，PR 会自动更新。

## 完成标准

Issue 满足以下全部条件才算完成：功能已实现 → 开发者自测 → Commit → 建立 PR → 至少一名成员 Review → 问题已修改 → 合并到 `main` → 必要的文档 / Scrum 记录已更新 → 关闭 Issue。

## 文档与命名

- 项目文档放在 `docs/`：`design/` 设计、`testing/` 测试、`scrum/` 每周 Scrum 记录。
- Markdown 和图片文件名使用小写英文和 `-`，如 `alpha-test-report.md`、`alpha-login-page.png`。
