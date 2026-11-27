# 后端开发六维能力树

关联 Issue #5、#64。Alpha 开放岗位 `backend`，关注数据库、服务端程序与可靠接口。题库 0.1.6 在首批 42 题的基础上追加 506 题，能力树共有 130 个知识点。

## 六维与题量

维度 ID、名称和说明沿用当前 [API 契约](api.md)。

| ID | 名称 | 说明 | easy | medium | hard | 单选 | 多选 | 合计 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| programming | 程序设计 | 程序语义、数据结构基础与代码理解 | 116 | 38 | 35 | 185 | 4 | 189 |
| algorithms | 算法基础 | 复杂度、搜索排序与算法策略 | 29 | 11 | 10 | 46 | 4 | 50 |
| database | 数据库 | 关系建模、SQL、事务与索引 | 45 | 15 | 11 | 67 | 4 | 71 |
| network | 计算机网络 | 协议、HTTP、可靠传输与网络基础 | 26 | 6 | 4 | 32 | 4 | 36 |
| os | 操作系统 | 进程、并发、内存与文件管理 | 49 | 16 | 18 | 79 | 4 | 83 |
| software | 软件工程 | 需求、测试、版本控制与工程实践 | 81 | 22 | 16 | 115 | 4 | 119 |
| 总计 | | | 346 | 108 | 94 | 524 | 24 | 548 |

## 稳定知识点

每个知识点的完整标识采用 `维度ID.知识点后缀`。显示名可修订，标识应保持稳定。完整定义见 [ability-tree.json](../../backend/app/content/ability-tree.json)，每道题通过 `topicId` 引用对应节点。下表记录首批题使用的知识点。

| 维度 | 知识点 ID 后缀与说明 |
|---|---|
| programming | `queue`：先进先出；`input-validation`：服务端类型/范围与容量边界；`aliasing`：可变对象共享引用；`resource-cleanup`：异常传播与资源释放；`money-representation`：整数分和十进制金额；`hash-key`：哈希与相等语义稳定；`copy-isolation`：嵌套数据复制隔离 |
| algorithms | `binary-search`：有序输入与二分；`complexity`：线性、平方与对数增长；`deduplication`：哈希集合去重成本；`bfs`：无权图最短路径；`merge`：有序序列线性合并；`top-k`：固定容量最小堆；`directed-cycle`：DFS 路径标记与拓扑判环 |
| database | `sql-filter`：SELECT/WHERE；`constraints`：主键与外键；`transaction-atomicity`：同库事务原子性；`left-join`：ON 与 WHERE 的语义；`index-tradeoff`：索引维护和计划成本；`optimistic-concurrency`：条件更新与版本冲突；`transactional-outbox`：事务事件记录与消费幂等 |
| network | `http-content-type`：表示的媒体类型；`tcp-stream`：TCP 字节流与应用分帧；`http-created`：创建资源状态；`conditional-cache`：ETag 与条件请求；`safe-retry`：未知结果与安全重试；`proxy-trust`：代理链与转发头信任；`session-request-security`：CSRF 与对象授权 |
| os | `process-isolation`：进程地址空间；`thread-resources`：线程共享与私有状态；`mutual-exclusion`：完整临界区；`blocking-io`：阻塞操作与调度；`deadlock-prevention`：锁顺序和释放重试；`condition-variable`：唤醒后谓词重检；`bounded-buffer`：信号量、互斥锁和容量控制 |
| software | `unit-testing`：替身与稳定单测；`safe-logging`：关联日志与敏感字段；`idempotency-test`：返回值和业务副作用验证；`merge-review`：冲突的语义处理；`ci-delivery`：锁定依赖和部署门禁；`schema-migration`：兼容迁移；`message-idempotency`：至少一次投递的消费验证 |

部分知识点可跨维度，例如消费幂等同时涉及数据库与工程实践。每题在当前测评中只归入一个主维度，按主要考察目标标注，避免把同一题重复计分。此划分不是行业标准岗位模型。

## 资料与原创说明

- 本地接口依据：[API 契约](api.md)。
- 原创、改编批次及审核状态见 [manifest.json](../../backend/app/content/manifest.json)。首批 42 道题的人工复核见 [原始题库复核记录](../testing/question-bank-review.md)。
- 新增 500 道单选改编自 freeCodeCamp，随附 [版权与许可声明](../../backend/app/content/FREECODECAMP_LICENSE_NOTICE.txt)。另外 6 道为新编多选。各题 `sources` 提供知识参考资料。

## 与测评衔接的边界

蓝图 `alpha-18-easy12-medium6-v1` 每维抽 2 道 easy、1 道 medium，共 18 题。`0.1.6` 的内容分布满足配额。

本轮不增加岗位权重；如未来引入权重，必须注明为初始产品假设。难度标签同样未经样本试测校准。题目用于知识自查和联调，不支持就业预测、岗位胜任概率或学习效果因果结论。

题库字段、公开投影、版本及后续外部题库适配约定见 [question-bank-contract.md](question-bank-contract.md)。
