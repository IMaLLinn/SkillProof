# 错题本验证记录

对应 Issue #66。2026-11-27，本地分支 `feature/66-wrongbook`，基于 `1fdadce`。Python 3.12.14，独立 SQLite 测试数据库。

## 已通过

- 后端全量180项测试，其中错题本12项。覆盖收集、筛选、账号隔离、重练幂等、手动掌握、旧数据库升级及原报告保护。
- 前端85项测试，其中错题本6项。类型检查、lint和生产构建通过。
- 后端覆盖率：语句93.58%、分支82.75%；前端逻辑层语句90.43%、分支92.60%。均达到阈值，并通过同环境主分支基线回归比较。
- 使用独立数据库运行 `python scripts/run_integration_tests.py`，5项真实接口集成测试全部通过，包含新增错题本用例和原有历史对比用例。测试服务关闭逐请求日志，避免Windows下未消费的输出管道填满后阻塞；错误日志仍保留。
- 使用实际通过的后端、前端和集成测试结果核对必跑清单，`scripts/check_qa.py`通过，Issue #66的16项必跑用例均已覆盖。
- 浏览器使用本机服务和演示数据，完成登录、打开错题、重练提交、标记已掌握、刷新保留、移回待复习和维度筛选。重练时不显示答案解析；提交后显示结果和累计次数。
- 检查1280px桌面和390px窄屏，未发现横向溢出；窄屏可在列表与详情之间返回。检查时未捕获浏览器控制台错误。

后端执行：`python -B -m unittest discover -s backend/tests -p "test_*.py" -v`；覆盖率使用 `python -m coverage run scripts/run_backend_tests.py` 和 `scripts/report_coverage.py`。

前端执行：`vitest run --coverage`、`tsc -b`、`eslint .`、`vite build`。

## 待完成

推送后仍需完成远程CI、成员Review及合并。上述检查均为本地验证，不代表正式网站已部署。
