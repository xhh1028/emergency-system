# 工作流实现记录

## 0. 背景与目标

- 工作流目标：建立用于确认应急系统回答是否准确的双轨工作流：
  - **刚性业务流**：由固定状态机、已批准规程、硬性安全规则和授权人工确认共同决定是否可以执行，保证安全。
  - **AI 辅助流**：由 AI 完成事实抽取、知识检索和候选答案生成，但必须经过证据、规则、完整性和人工复核后才能进入刚性业务流。
- 输入：事件上报信息（事件类型、标题、地点、时间、人员及影响范围、描述、附件等）、已有事件状态、规程/预案知识库、AI 候选答案、人工复核意见。
- 输出：可执行或不可执行的结构化答案；处置步骤、责任岗位、依据条款、校验结果、人工最终结论、任务执行记录和完整审计记录。
- 关键节点：事件接收、事实结构化、AI 候选生成、知识证据绑定、硬规则校验、完整性/顺序校验、人工复核、调度确认、指令下发、任务执行、关闭归档。
- 技术栈/运行方式：现有 Java 17 + Spring Boot 后端、Vue 3 + Vite 前端、MySQL 数据库、`KG_RAG/` Python 知识图谱/RAG 工具；后端和前端运行方式以仓库 `README.md` 与 `backend/README.md` 为准。
- 现有相关模块：
  - 后端：`EventService`、`AiAssessmentService`、`StationWorkflowService`、`DispatchWorkflowService`、`event`、`event_log`、`task`、`pre_plan`。
  - 前端：车站事件复核、调度事件详情/指令、任务执行和事件归档页面。
  - RAG：`KG_RAG/online/main.py`、`KG_RAG/online/plan_generator.py` 及其规程索引和验证逻辑。
- 约束与偏好（当前按已有上下文记录，待确认）：保持现有架构；不擅自引入新依赖；不删除已有日志；每次只推进一个实施步骤；AI 不得绕过规则和人工授权直接触发执行；不在代码或记录中写入密钥、令牌和密码。
- 验收标准：
  1. 刚性业务流有明确状态、角色、前置条件和状态转移，非法转移被阻断。
  2. AI 输出必须为可校验的结构化候选答案，并绑定真实知识依据、版本和引用位置。
  3. 未通过证据、规则、完整性、顺序或权限校验的答案不能下发为执行指令。
  4. 高风险事件必须经过授权人员确认；人工接受、修改、驳回均有原因和前后快照。
  5. AI 不可用、超时或知识库不可用时，刚性业务流仍可按安全规则运行。
  6. 事件、答案、校验、审批、指令、任务和关闭操作均可按事件编号完整追溯。
  7. 关键异常和回放场景有自动化验证，且不虚构未执行的验证结果。

## 1. 实施步骤清单

| 编号 | 步骤名称 | 目标 | 涉及文件/模块 | 实现要点 | 验证方式 | 依赖步骤 | 完成标准 | 状态 |
|---|---|---|---|---|---|---|---|---|
| S01 | 固化双轨状态机与答案契约 | 把刚性业务流、AI 辅助流、角色权限、状态转移和答案 JSON 契约定义成可实现的边界 | `backend/src/main/java/com/metro/emergency/service/`、`dto/`、现有 `README.md`；必要时新增设计文档 | 明确事件状态、答案状态、允许动作、阻断条件、角色和错误码；定义候选答案、证据、校验结果和人工决策的数据字段；不改业务行为 | 设计审查；用现有状态和接口逐项对照；补充契约示例并检查字段完整性 | 无 | 双轨流程图、状态转移表、结构化答案契约和待确认决策已写入记录，且与现有接口无矛盾 | 已完成 |
| S02 | 增加工作流与审计持久化模型 | 保存工作流实例、答案版本、证据、校验结果、审批快照和追加式审计链 | `SchemaCompatibilityMigration.java`、repository、数据库迁移/初始化脚本 | 采用非破坏性新增表/字段；保存知识版本、模型信息、提示词摘要、输入输出快照摘要、操作人、时间和前后哈希；禁止写入密钥 | 数据库迁移/启动检查；表结构查询；Repository 读写测试 | S01 | 新模型可创建、查询、追加审计记录；旧数据和现有事件流不受影响 | 已完成 |
| S03 | 实现刚性规则与状态转移校验 | 让系统在执行前检查必填事实、等级映射、规程存在性、动作顺序、角色权限和状态前置条件 | 新增或扩展后端校验 service；`EventService`、`StationWorkflowService`、`DispatchWorkflowService` | 规则服务必须可解释；任何失败返回明确原因；严重事件和高风险动作必须人工确认；校验失败不得产生执行指令 | 单元测试覆盖合法/非法状态转移、缺失信息、顺序冲突、权限错误和等级冲突 | S01、S02 | 所有刚性闸门在服务层生效，绕过前端调用也无法放行 | 已完成 |
| S04 | 接入 AI 候选答案与证据绑定 | 将 AI 输出从自由文本升级为候选答案，并绑定 RAG 文档、章节、条款、片段和版本 | `AiAssessmentService`、`KG_RAG/online/main.py`、`plan_generator.py`、AI 结果 repository/dto | 保留 AI 来源、模型、版本、生成时间和候选版本；没有真实依据时标记为待核验/不可执行；支持 AI 故障降级到规则方案 | 使用固定事件样例检查结构化输出、证据存在性、AI 超时降级和异常响应处理 | S01、S02、S03 | AI 只生成候选结果；每个关键结论可定位依据；异常时不阻断刚性流 | 已完成 |
| S05 | 实现答案独立校验与人工复核 | 提供证据、规则、完整性、顺序、知识新鲜度和权限校验，并让授权人员接受/修改/驳回 | 新增 `AnswerValidationService`/审批 service；车站复核 API 与页面；`StationWorkflowService` | 校验结果逐项落库；人工界面展示 AI 原答、依据、失败项、缺失事实和差异；修改必须填写理由并保存前后快照 | 后端接口测试；前端人工操作检查；覆盖接受、修改、驳回和重复提交 | S03、S04 | 未通过关键校验的答案不能被接受为可执行；人工决策可追溯 | 已完成 |
| S06 | 将执行指令接入安全闸门 | 确保调度指令只能引用已校验、已批准的答案版本 | `DispatchWorkflowService`、`DispatchWorkflowController`、调度指令页面和 repository | 指令提交必须携带答案版本/校验结果；检查调度确认、最终等级、权限、事件状态和任务前置条件；记录指令与答案的关联 | API 级绕过前端测试；合法下发、未确认、过期答案、等级冲突和重复下发测试 | S03、S05 | 所有执行指令都能回溯到批准答案和依据；非法调用被阻断 | 已完成 |
| S07 | 完善执行反馈、关闭和审计回放 | 形成从指令、任务、反馈到关闭的闭环，并支持按事件重放决策过程 | `TaskExecutionService`、`DispatchWorkflowService`、归档页面、审计查询 API/页面 | 关闭前检查任务完成和反馈完整性；审计记录追加写入；支持查看事件时间线、答案版本、校验结果、人工修改和指令快照 | 端到端回放；关闭前置条件测试；审计链连续性和查询完整性检查 | S02、S05、S06 | 一个事件可重建“输入→AI候选→校验→人工决策→指令→任务→关闭”的全过程 | 已完成 |
| S08 | 建立回归测试与验收基线 | 用固定场景确认准确性、安全性、可追溯性和降级能力 | 后端测试目录、必要的前端检查、`KG_RAG/online` 回放样例、README/记录文件 | 覆盖正常、信息不足、编造条款、过期知识、顺序错误、多事件交叉、AI 超时、人工改判、紧急跳过普通驳回等场景 | 执行仓库约定的后端测试、前端构建和 RAG 回放；记录真实命令、输出和失败项 | S04、S06、S07 | 安全规则误放行为 0；无依据答案不可执行；关键操作 100% 留痕；失败项有明确处理结论 | 已完成 |

## 2. 执行记录

### S01 固化双轨状态机与答案契约

- 状态：已完成
- 开始时间：2026-10-18（本轮执行开始）
- 结束时间：2026-10-18 16:01:46 +08:00
- 目标：明确刚性业务流与 AI 辅助流的状态、角色、答案结构和执行前置条件，为后续实现提供稳定契约。
- 本轮计划：对照现有事件、车站复核、调度和任务状态，补充状态转移表、角色边界、候选答案 JSON 契约及阻断规则；只更新 Markdown 设计记录，不修改业务代码。
- 验证方式：检查状态转移是否覆盖现有服务端流程；检查答案契约是否包含结论、步骤、责任岗位、依据、校验和人工决策字段；检查 S02-S08 的依赖关系是否明确。
- 设计结果：
  - 刚性业务流以现有服务端事件状态为兼容基础：`PENDING`（待车站处理）→ `CONFIRMED`（补全后重新提交）→ `STATION_HANDLE`（站内处置）或 `REPORTED_TO_DISPATCH`（上报调度）→ `FINISHED`（关闭归档）；普通事件允许 `PENDING → REJECTED → CONFIRMED`，紧急事件禁止进入 `REJECTED`。
  - `REPORTED_TO_DISPATCH` 必须先完成调度确认，再允许下发指令；关闭前必须存在任务且全部任务为 `COMPLETED`。最终法定等级使用 `IV_GENERAL`、`III_MAJOR`、`II_SERIOUS`、`I_EXTREMELY_SERIOUS`，与 AI 建议等级分开保存。
  - 刚性流角色边界：一线人员负责上报和补全；车站管理员负责复核等级、选择站内处置或上报调度、分派站内任务；调度员负责确认、最终定级、下发指令、监督任务和关闭；执行人员只能更新本人任务；系统负责校验和记录，不代替授权人员作最终决定。
  - AI 辅助流状态定义为 `GENERATED → VALIDATED → ACCEPTED|MODIFIED|REJECTED`。只有 `VALIDATED` 且通过关键校验，并经授权人员 `ACCEPTED` 或 `MODIFIED` 的答案，才允许关联执行指令。
  - 候选答案契约示例：

    ```json
    {
      "schemaVersion": "answer.v1",
      "eventId": 123,
      "answerId": "候选答案版本标识",
      "source": "RULE|LLM|HUMAN",
      "conclusion": {"riskLevel": "GENERAL|SERIOUS|EXTREMELY_SERIOUS", "text": ""},
      "actions": [{"order": 1, "action": "", "role": "", "mandatory": true, "evidenceIds": ["ev-1"]}],
      "missingFacts": [],
      "assumptions": [],
      "conflicts": [],
      "evidence": [{"id": "ev-1", "sourceType": "RAG|PRE_PLAN|RULE", "documentId": "", "version": "", "section": "", "quote": "", "contentHash": ""}],
      "validation": {"schema": "PENDING|PASS|FAIL", "evidence": "PENDING|PASS|FAIL", "rule": "PENDING|PASS|FAIL", "completeness": "PENDING|PASS|FAIL", "order": "PENDING|PASS|FAIL", "permission": "PENDING|PASS|FAIL", "final": "PENDING|PASS|FAIL"},
      "decision": {"status": "PENDING|ACCEPTED|MODIFIED|REJECTED", "operatorId": null, "reason": null}
    }
    ```
  - 关键阻断规则：缺少地点/影响范围/人员情况等必要事实时只能返回 `missingFacts`；证据不存在、条款版本不可确认、动作顺序冲突、答案等级与事件等级冲突、操作者无权限或答案未完成人工决策时，禁止进入可执行状态；AI 服务异常只允许切换到可解释规则方案，并记录降级原因。
  - 版本与关联规则：每次 AI 生成或人工修改产生新答案版本；校验结果绑定具体答案版本；指令绑定批准答案版本；事件审计时间线按事件编号串联，不覆盖历史版本。
- 验证结果：已对照 `EventService`、`StationWorkflowService`、`DispatchWorkflowService`、`TaskExecutionService` 及相关 repository 中的现有状态和前置条件；S01 设计覆盖当前主流程，未发现状态名称冲突。答案契约和后续 S02-S08 的依赖关系已明确。
- 变更文件：`WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：本步骤仅完成设计契约和记录，不修改 Java、Vue、SQL 或 Python 业务实现。
- 验证命令：`rg -n "PENDING|CONFIRMED|REJECTED|STATION_HANDLE|REPORTED_TO_DISPATCH|FINISHED|COMPLETED" backend/src/main/java`
- 验证结果：命令已执行；确认现有事件、任务状态及调度前置条件与本步骤设计一致。未执行构建或测试，因为本步骤没有业务代码变更。
- 问题与决策：后续实现以现有数据库状态兼容为前提；答案版本、证据、校验和审批记录进入 S02 设计的新增持久化模型；最终法定等级与 AI 建议等级继续分离。
- 下一步：等待确认后进入 S02，设计并实现工作流、答案、证据、校验、审批和追加式审计的持久化模型。

### S02 增加工作流与审计持久化模型

- 状态：已完成
- 开始时间：2026-10-18
- 结束时间：2026-10-18 16:11:06 +08:00
- 目标：以非破坏性方式增加双轨工作流所需的持久化表，并提供创建、查询、追加审计记录的最小后端能力。
- 本轮计划：扩展 `SchemaCompatibilityMigration` 创建工作流实例、答案候选、证据、校验、审批和审计表；新增 repository 负责基础写入和查询；不接入事件主流程，不改变现有表和现有接口行为。
- 验证方式：编译后端；检查新增 SQL/Java 代码引用；使用现有测试框架完成 repository 基础行为验证或在无可用数据库时记录实际阻塞原因。
- 操作摘要：在启动迁移中新增六张非破坏性表；新增 `WorkflowArtifactRepository`，提供工作流实例和答案候选的创建/查询、证据写入、校验结果写入、审批快照写入、审计追加和事件审计链查询。
- 变更文件：`backend/src/main/java/com/metro/emergency/config/SchemaCompatibilityMigration.java`；`backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`；`WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：新增表分别为 `workflow_instance`、`answer_candidate`、`answer_evidence`、`validation_result`、`approval_record`、`audit_event`；答案按事件内版本唯一约束；审计记录保存 `previous_hash` 与 `current_hash`，调用方负责脱敏和计算当前哈希；本步骤没有把候选答案接入执行指令。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -DskipTests compile`
- 验证结果：首次运行因沙箱禁止 Maven 访问中央仓库失败；在获得网络权限后同一编译命令成功，退出码为 0。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q test`
- 验证结果：现有后端测试成功，退出码为 0。测试上下文没有可用 JDBC 连接，启动日志记录了数据库迁移未完成警告，因此本轮未对真实 MySQL 建表和 repository 读写做集成验证；代码编译和现有接口测试不受影响。
- 问题与决策：不新增依赖；不使用外键以兼容现有数据库初始化顺序和历史数据；真实数据库迁移/读写验证留到具备可用数据库连接的环境或后续验收步骤执行。
- 下一步：等待确认后进入 S03，实现刚性规则与状态转移校验，并让服务层阻断未满足前置条件的操作。

### S03 实现刚性规则与状态转移校验

- 状态：已完成
- 开始时间：2026-10-18 16:20:00 +08:00
- 结束时间：2026-10-18 16:29:57 +08:00
- 目标：在后端服务层建立可解释的刚性校验，阻止非法状态转移、等级冲突、未确认调度指令和未完成任务关闭。
- 操作摘要：新增 `RigidWorkflowRuleService` 作为无副作用规则闸门；车站复核、调度确认、调度指令和事件关闭均先通过规则服务，再执行原有数据库写入和通知；归档等级筛选也复用法定等级校验。严重及以上车站等级无论请求路径如何都强制进入调度上报；指令必须处于 `REPORTED_TO_DISPATCH` 且完成调度确认；关闭必须有任务且全部任务完成。
- 变更文件：`backend/src/main/java/com/metro/emergency/service/RigidWorkflowRuleService.java`；`backend/src/main/java/com/metro/emergency/service/StationWorkflowService.java`；`backend/src/main/java/com/metro/emergency/service/DispatchWorkflowService.java`；`backend/src/test/java/com/metro/emergency/service/RigidWorkflowRuleServiceTest.java`；`WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：规则服务只读取服务层事件快照并返回结构化决策或抛出明确业务原因，不写数据库；AI 候选答案和前端流程未在本步骤接入；未新增依赖。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml -DskipTests compile`
- 验证结果：在允许 Maven 访问依赖仓库后编译成功，退出码为 0。首次受限环境尝试因无法下载 Spring Boot 父 POM 失败，未作为代码失败；随后使用相同命令完成真实编译。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`
- 验证结果：成功。`RigidWorkflowRuleServiceTest` 5/5 通过；现有 `AuthControllerTest` 24/24 通过；失败数 0、错误数 0。测试上下文仍无可用 JDBC 连接，启动时记录数据库迁移警告，因此未验证真实 MySQL 集成读写。
- 问题与决策：保留现有服务层错误消息和状态名称，避免前端兼容性变化；将规则集中化但不改变现有数据库结构；真实数据库连接验证留到具备数据库的验收环境。
- 下一步：等待确认后进入 S04，接入 AI 候选答案与真实证据绑定，并保留规则流降级路径。

（后续步骤记录继续追加，不覆盖历史记录。）

### S04 开始记录

- 状态：进行中
- 开始时间：2026-10-18 16:44:28 +08:00
- 本轮计划：读取现有 AI 研判与预案接口，新增结构化候选答案和证据绑定服务，保存候选及证据版本；AI 无法使用时保留规则降级，并补充单元测试。
- 变更范围：仅处理 AI 候选生成、证据绑定和对应持久化，不接入人工审批和执行指令。
- 验证方式：后端编译、S04 单元测试、现有后端测试。

### S04 接入 AI 候选答案与证据绑定

- 状态：已完成
- 开始时间：2026-10-18 16:44:28 +08:00
- 结束时间：2026-10-18 17:08:00 +08:00
- 目标：将现有 AI/规则研判结果保存为不可直接执行的结构化候选答案，并绑定可定位的预案证据；知识库不可用时不阻断刚性业务流。
- 操作摘要：新增 `AiCandidateAnswerService`，把 `AiAssessmentService.Assessment` 包装为 `answer.v1` JSON，生成事件内递增候选版本，创建 `AI_ASSIST` 工作流实例并保存答案摘要；从 `pre_plan` 查询匹配预案，记录文档标识、版本、章节、引用片段和 SHA-256 内容摘要；候选固定为 `GENERATED`，答案校验和人工决策保持待处理，未进入执行指令。知识库查询、候选结构化或候选持久化失败时记录告警并保留原有事件上报/规则流程。
- 变更文件：`backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`；`backend/src/main/java/com/metro/emergency/service/AiCandidateAnswerService.java`；`backend/src/main/java/com/metro/emergency/service/EventService.java`；`backend/src/test/java/com/metro/emergency/service/AiCandidateAnswerServiceTest.java`；`backend/src/test/java/com/metro/emergency/controller/AuthControllerTest.java`；`WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：答案包含结论、动作顺序、责任角色、强制标志、证据 ID、缺失事实、假设、冲突、逐项校验状态和人工决策字段；无匹配预案时证据校验为 `PENDING` 且不写入伪造证据；AI 结果来源仅归一化为 `RULE` 或 `LLM`，候选不会自动变成 `VALIDATED`、`ACCEPTED` 或执行指令。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml -DskipTests compile`
- 验证结果：成功，退出码为 0。首次受限环境尝试因 Maven 无法访问中央仓库失败；在允许依赖访问后同一编译命令成功，该受限环境失败不代表代码编译失败。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`
- 验证结果：成功，退出码为 0。`AiCandidateAnswerServiceTest` 3/3 通过（含预案证据、无证据待核验、知识库异常降级）；`RigidWorkflowRuleServiceTest` 5/5 通过；`AuthControllerTest` 24/24 通过；失败数 0、错误数 0。测试上下文仍未连接真实 MySQL，启动日志出现数据库迁移连接警告，因此本步骤未把真实数据库建表/读写作为测试结果宣称。
- 问题与决策：真实 MySQL 已确认可由本机应用环境连接，但当前 Spring 测试通过 Mock 数据源隔离数据库；真实迁移与 repository 集成验证保留到后续具备专门集成测试入口的验收步骤，不将单元测试结果当作真实数据库验证。
- 下一步：等待确认后进入 S05，实现答案独立校验与授权人工复核。

### S05 实现答案独立校验与人工复核

- 状态：已完成
- 开始时间：2026-10-18 17:09:00 +08:00
- 结束时间：2026-10-18 17:44:00 +08:00
- 目标：让候选答案在人工决策前经过独立的结构、证据、规则、完整性、动作顺序、知识版本和权限校验，并保存接受、修改或驳回的完整快照。
- 操作摘要：新增 `AnswerValidationService`，读取候选答案和持久化证据，逐项写入 `validation_result`；只有全部校验通过才将候选状态推进到 `VALIDATED`。新增答案详情、独立校验和人工复核接口；接受/修改/驳回均要求原因，修改会生成新的 `HUMAN` 答案版本，所有动作写入 `approval_record` 和追加式 `audit_event`。
- 变更文件：`backend/src/main/java/com/metro/emergency/service/AnswerValidationService.java`；`backend/src/main/java/com/metro/emergency/controller/AnswerWorkflowController.java`；`backend/src/main/java/com/metro/emergency/dto/AnswerReviewRequest.java`；`backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`；`backend/src/main/java/com/metro/emergency/config/SchemaCompatibilityMigration.java`；`backend/src/test/java/com/metro/emergency/service/AnswerValidationServiceTest.java`；`WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：新增知识版本新鲜度校验字段 `freshness_result`，并对已有 `validation_result` 表提供兼容增列；接受和修改要求候选先处于 `VALIDATED`，驳回可处理未通过或待处理候选；修改后的答案必须再次满足同一组校验，且不会直接进入执行指令。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`
- 验证结果：成功，退出码为 0。`AnswerValidationServiceTest` 5/5、`AiCandidateAnswerServiceTest` 3/3、`RigidWorkflowRuleServiceTest` 5/5、`AuthControllerTest` 24/24 通过；合计 37 项，失败数 0、错误数 0。测试上下文仍使用数据源隔离，启动日志出现数据库迁移连接警告，因此未宣称真实 MySQL 集成读写已验证。
- 问题与决策：本步骤只提供候选答案校验和人工复核接口，不把批准结果接入调度指令；答案详情接口目前按业务角色授权，事件归属和执行指令关联留到 S06 统一处理。
- 下一步：等待确认后进入 S06，将执行指令绑定到已校验且已批准的答案版本。

#### S05 前端复核入口补充记录

- 状态：已完成
- 操作摘要：在车站事件待办详情中增加最新候选答案、动作责任、证据标签和当前校验状态展示；增加独立校验、接受、修改、驳回入口，修改时提交完整结构化 JSON，接受/修改/驳回均要求填写原因。
- 变更文件：`frontend/src/api/station.js`；`frontend/src/views/station/EventTodo.vue`；`backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`；`backend/src/main/java/com/metro/emergency/controller/AnswerWorkflowController.java`
- 验证命令：`npm run build`（工作目录：`frontend`）
- 验证结果：成功，Vite 完成生产构建；仅出现既有第三方库 `/*#__PURE__*/` 注释提示，无构建失败。
- 后端补充验证：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test` 成功，37 项测试全部通过；测试上下文仍未连接真实 MySQL。


### S06 开始记录

- 状态：进行中
- 开始时间：2026-10-21（Asia/Shanghai）
- 本轮计划：将调度指令请求绑定到已通过独立校验并完成授权的答案版本；为既有 `dispatch_command` 增加兼容关联字段，补充答案状态、事件等级、调度确认、重复下发和证据关联闸门，并增加后端测试。
- 变更范围：`DispatchCommandRequest`、`DispatchWorkflowService`、`RigidWorkflowRuleService`、`DispatchWorkflowRepository`、`SchemaCompatibilityMigration` 及 S06 测试；必要时补充调度指令页面的答案版本输入/展示。不改任务执行和关闭流程。
- 验证方式：后端编译和测试；覆盖未校验、未批准、答案不存在/过期、事件等级冲突、重复下发、合法答案关联和前端构建。

#### S06 恢复执行记录

- 状态：进行中
- 恢复时间：2026-10-21 22:12 +08:00
- 本轮目标：完成上轮尚未验证的最终改动及 S06 验收；修正首次建库迁移顺序、未授权答案显示和接口错误返回；补充直接调用接口的阻断测试。
- 涉及文件：`backend/src/main/java/com/metro/emergency/config/SchemaCompatibilityMigration.java`、`backend/src/main/java/com/metro/emergency/service/DispatchWorkflowService.java`、`backend/src/main/java/com/metro/emergency/controller/AnswerWorkflowController.java`、相关 repository/test、`frontend/src/views/dispatch/CommandDispatch.vue`。
- 验证方式：后端全量测试（含真实服务参与的 MockMvc 接口测试）、前端生产构建、差异检查。真实 MySQL 集成与浏览器人工操作未执行时明确记录，不以 Mock 测试替代。
- 完成标准：最终代码测试通过、指令关联与阻断场景有证据、步骤状态和执行记录已更新。

#### S06 验证过程记录

- `tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`：失败于 Windows 文件占用（`backend/target/maven-status/.../createdFiles.lst`），未作为业务代码失败。
- 使用原 `backend/pom.xml` 生成仅将 build.directory 指向 `backend/target-s06-verification` 的临时清单 `backend/.s06-verification-pom.xml`；源码、依赖、资源与测试入口保持相同。执行 `tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/.s06-verification-pom.xml test`。
- 首轮独立目录结果：73 项，72 通过、1 失败、0 错误。失败项为 `AnswerWorkflowAccessTest.blocksCrossStationReadValidationAndReview`；Mockito 默认返回空 Map，与真实 repository 无记录时返回 null 不一致。已显式模拟 null，并增加车站复核等级冲突用例，等待重新验证。
- `npm run build`（`D:/dachuang/emergency-system/frontend`）：成功，退出码 0；只有第三方库 PURE 注释提示，未验证浏览器人工操作。

### S06 将执行指令接入安全闸门

- 状态：已完成
- 开始时间：2026-10-21（首次开始记录）；本轮恢复：2026-10-21 22:12 +08:00。
- 结束时间：2026-10-21 22:23:31 +08:00
- 目标：正式调度指令只引用当前事件最新、全部校验通过且已人工批准的答案版本，并保存指令、校验与证据关联。
- 操作摘要：完成服务端闸门、持久化关联和追加审计；修正首次迁移顺序、答案权限和前端状态显示；将下发正文绑定到批准动作，补齐最终自动化验证。
- 变更文件（相对于 `D:/dachuang/emergency-system/`）：
  - `backend/src/main/java/com/metro/emergency/dto/DispatchCommandRequest.java`
  - `backend/src/main/java/com/metro/emergency/service/DispatchWorkflowService.java`
  - `backend/src/main/java/com/metro/emergency/service/AnswerValidationService.java`
  - `backend/src/main/java/com/metro/emergency/repository/DispatchWorkflowRepository.java`
  - `backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`
  - `backend/src/main/java/com/metro/emergency/controller/AnswerWorkflowController.java`
  - `backend/src/main/java/com/metro/emergency/config/SchemaCompatibilityMigration.java`
  - `backend/src/main/java/com/metro/emergency/exception/GlobalExceptionHandler.java`
  - `backend/database/All.sql`（本地初始化脚本，现有 .gitignore 已忽略）
  - `frontend/src/views/dispatch/CommandDispatch.vue`
  - `backend/src/test/java/com/metro/emergency/service/DispatchAnswerGateTest.java`
  - `backend/src/test/java/com/metro/emergency/service/AnswerValidationServiceTest.java`
  - `backend/src/test/java/com/metro/emergency/controller/AnswerWorkflowAccessTest.java`
  - `backend/src/test/java/com/metro/emergency/config/SchemaCompatibilityMigrationTest.java`
  - `WORKFLOW_IMPLEMENTATION.md`
- 关键实现/配置说明：
  - 请求必须携带 answerId/answerVersion；服务端验证调度权限、事件未撤回、已上报且已确认；候选表和 JSON 中的事件号一致；只使用最新 ACCEPTED/MODIFIED 答案。
  - 最新校验记录的所有子项和汇总均为 PASS；实际审批的动作、角色、原因及 afterSnapshot 与答案匹配，禁止仅凭状态字段放行。
  - 下发时重新查询 pre_plan，核对版本、引用正文及 SHA-256 摘要；预案更新、删除或来源无法确认时阻断。人工修改新版本复制证据并保存独立校验结果。
  - 指令正文严格等于批准答案按原顺序生成的编号动作；页面展示批准动作并设为只读；未批准答案展示待复核状态并禁用下发。更改内容须先修改答案并复核。
  - 兼容现有三档建议等级与四档法定等级：GENERAL 对应 IV_GENERAL/III_MAJOR，SERIOUS 对应 III_MAJOR/II_SERIOUS，EXTREMELY_SERIOUS 对应 II_SERIOUS/I_EXTREMELY_SERIOUS；事件已有法定等级必须精确匹配；事件仍为车站复核三档等级时须与答案等级一致。
  - 指令保存 answer_id、answer_version、validation_id、evidence_snapshot 并追加 COMMAND_DISPATCH 审计。重复版本检查配合数据库唯一索引；竞争触发重复键时明确拒绝。旧指令关联字段允许 NULL，不伪造历史授权。
  - 答案读取/校验/复核按业务角色和车站归属授权；状态拒绝转换为统一 API code=400。首次迁移先建 validation_result 再兼容增列；不删除旧数据、记录，不引入新依赖。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/.s06-verification-pom.xml test`。
- 验证结果：退出码 0，74 项全部通过，失败 0、错误 0、跳过 0。

| 测试类 | 通过/总数 | 失败 | 错误 |
|---|---|---|---|
| SchemaCompatibilityMigrationTest | 1/1 | 0 | 0 |
| AnswerWorkflowAccessTest | 3/3 | 0 | 0 |
| AuthControllerTest | 24/24 | 0 | 0 |
| AiCandidateAnswerServiceTest | 3/3 | 0 | 0 |
| AnswerValidationServiceTest | 5/5 | 0 | 0 |
| DispatchAnswerGateTest | 33/33 | 0 | 0 |
| RigidWorkflowRuleServiceTest | 5/5 | 0 | 0 |

- API 验证范围：真实 controller/service 加 Mock 数据访问，覆盖 24 个下发阻断场景，包括未带版本、未校验、未授权、旧版本、跨事件、校验子项失败、缺少/不匹配审批、缺证据、预案更新/删除、法定/车站等级冲突、正文篡改、撤回、未确认、非调度人员、重复下发、JSON 事件号错误及不存在答案；断言拒绝后无指令写入、等级更新、下发审计与通知。另覆盖合法人工修改答案下发、数据库重复键拒绝和本站/跨站答案权限。
- 构建目录说明：标准 `mvn -q -f backend/pom.xml test` 因旧 target 的 Windows 文件占用失败；复制原 POM 到临时 `backend/.s06-verification-pom.xml`，仅在 build 中增加 `<directory>${project.basedir}/target-s06-verification</directory>`，源码、依赖、资源、测试入口不变。最终测试产物已移至 `D:/dachuang/emergency-system/.verify-backend/s06-20261021/`，报告位于其 `surefire-reports/`；临时 POM 已移除。需要复现时可按上述方式重新生成，原 POM 未修改。
- 前端验证命令：`npm run build`（`D:/dachuang/emergency-system/frontend`）。
- 前端验证结果：退出码 0，Vite 生产构建成功；第三方库 PURE 注释提示不影响构建。
- 差异检查命令：`git -c core.safecrlf=false diff --check`。
- 差异检查结果：2026-10-21 22:23 +08:00 执行成功，退出码 0，无空白错误；临时验证 POM 已移除，原 `backend/pom.xml` 未改动，独立测试产物已保存在现有忽略目录 `.verify-backend/s06-20261021/`。
- 问题与决策：当前核验知识源为实际接入的 PRE_PLAN；其他来源无实时版本核验适配时一律阻断。原目录占用已通过独立目录解决。首次独立测试的 1 项失败及修复原因保留在前面的验证过程记录中。
- 未验证范围：本轮没有连接真实 MySQL，未执行真实 DDL、读写、事务回滚及并发压力；数据库重复键由 Mock 模拟。未执行浏览器人工操作。Mock 数据源迁移警告不表示本机数据库不可用，真实集成验收保留到 S08，不用自动化 Mock 测试替代。
- Markdown 整理：将原来追加在验收清单之后的 S04-S06 执行记录原文移回 `## 2. 执行记录`；历史内容全部保留，未删除或改写历史验证结论。
- 是否存在阻塞：S06 代码与本轮自动化验证无阻塞；上述真实集成和浏览器操作明确为未验证。
- 下一步：等待用户确认 S07，完善执行反馈、关闭与审计回放；本轮未开始 S07。

### S07 完善执行反馈、关闭和审计回放

- 状态：已完成
- 开始时间：2026-10-22（Asia/Shanghai）
- 结束时间：2026-10-22 15:39:42 +08:00
- 目标：补齐任务反馈、关闭前检查和按事件重放答案、校验、人工复核、指令、任务与审计记录。
- 操作摘要：关闭校验新增逐个检查已完成任务是否存在非空文字现场反馈；任务开始与完成反馈在事务内追加 `audit_event`，事件关闭追加 `EVENT_CLOSE`；调度事件详情返回事件全部答案版本及其证据、最新独立校验和人工审批快照、指令证据快照、审计时间线与哈希链连续性标记；归档详情页面展示这些信息。
- 变更文件：`backend/src/main/java/com/metro/emergency/repository/DispatchWorkflowRepository.java`；`backend/src/main/java/com/metro/emergency/repository/WorkflowArtifactRepository.java`；`backend/src/main/java/com/metro/emergency/service/DispatchWorkflowService.java`；`backend/src/main/java/com/metro/emergency/service/TaskExecutionService.java`；`backend/src/main/java/com/metro/emergency/service/RigidWorkflowRuleService.java`；`backend/src/test/java/com/metro/emergency/service/DispatchAnswerGateTest.java`；`backend/src/test/java/com/metro/emergency/service/RigidWorkflowRuleServiceTest.java`；`backend/src/test/java/com/metro/emergency/controller/AuthControllerTest.java`；`frontend/src/views/dispatch/DispatchArchive.vue`；`WORKFLOW_IMPLEMENTATION.md`。
- 关键实现/配置说明：反馈文字为关闭必需项，图片仍为可选；只验证每项审计记录的 `previous_hash` 与前一条 `current_hash` 是否连续，并没有重算历史记录的 `current_hash` 内容。旧任务详情快照缺少事件编号时，审计写入明确失败，避免静默跳过追溯记录。未新增依赖或数据库表。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`
- 验证结果：成功，退出码 0；共 77 项测试通过，失败 0、错误 0、跳过 0。其中 `DispatchAnswerGateTest` 35/35、`RigidWorkflowRuleServiceTest` 6/6、`AuthControllerTest` 24/24。另有 S04/S05 测试均通过。
- 验证命令：`npm run build`（工作目录：`frontend`）
- 验证结果：成功，Vite 生产构建完成；出现既有 `@vueuse/core` PURE 注释提示，不影响构建。
- 验证命令：`git -c core.safecrlf=false diff --check`
- 验证结果：成功，无空白错误。
- 问题与决策：通过 SQL 对已完成但无非空现场反馈的任务进行关闭闸门核验；反馈审计保留反馈正文快照和图片数量，图片本身继续沿用现有附件存储；审计详情中的“连续”表示前后哈希指针衔接，不代表已验证所有历史哈希内容。
- 未验证范围：测试上下文没有真实 JDBC 连接，迁移日志显示未取得 JDBC Connection；因此真实 MySQL SQL 兼容、事务和数据回放仍未验证。未进行浏览器人工操作；前端验证仅为生产构建。
- 下一步：等待确认后进入 S08，建立固定回归与验收基线；本轮未开始 S08。

### S08 开始记录

- 状态：进行中
- 开始时间：2026-10-22（Asia/Shanghai）
- 本轮计划：梳理现有后端与 RAG 固定回归场景，补齐可复现的验证入口或必要测试；执行后端全量测试、前端构建及 RAG 回放自检，并逐项记录目标验收场景的覆盖证据与未验证项。
- 变更范围：后端测试、`KG_RAG/online` 的既有验证脚本（仅在需要时新增轻量场景）、`WORKFLOW_IMPLEMENTATION.md`；不改动业务规则或引入依赖。
- 验证方式：仓库测试命令、现有 RAG 自检脚本和代码差异检查；只有成功执行才记为通过。

### S08 建立回归测试与验收基线

- 状态：已完成
- 开始时间：2026-10-22（Asia/Shanghai）
- 结束时间：2026-10-22 15:51:35 +08:00
- 目标：用可复现测试确认关键安全闸门、证据/完整性校验、紧急流程和 RAG 固定场景，并建立本次验收结果基线。
- 操作摘要：补充紧急事件跳过普通驳回并写审计、紧急事件禁止走普通驳回接口的服务测试；补充答案动作顺序错误、必要事实缺失时不能通过校验的测试。修正 RAG `_test_order_n.py` 的输出解析：详细方案中还有作战简报摘要和岗位视图，旧测试把动作正文总出现次数一分为二，会将摘要误当主步骤，现改为直接验证详细方案步骤标签及主列表/岗位视图各自顺序。没有修改 RAG 业务逻辑或增加依赖。
- 变更文件：`backend/src/test/java/com/metro/emergency/service/StationEmergencyWorkflowTest.java`；`backend/src/test/java/com/metro/emergency/service/AnswerValidationServiceTest.java`；`KG_RAG/online/_test_order_n.py`；`WORKFLOW_IMPLEMENTATION.md`。
- 关键实现/配置说明：答案校验新增失败路径断言；紧急事件测试确认普通拒绝调用不产生 REJECT 审计；排序回归脚本检查固定 1..14 步骤在详细方案主列表和岗位视图均按数值顺序出现。RAG 脚本在 Windows 需使用 UTF-8 输出编码运行，否则默认 GBK 无法写出勾选符号。
- 验证命令：`tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd -q -f backend/pom.xml test`。
- 验证结果：成功，退出码 0；81 项通过，失败 0、错误 0、跳过 0。测试报告明细：SchemaCompatibilityMigrationTest 1，AnswerWorkflowAccessTest 3，AuthControllerTest 24，AiCandidateAnswerServiceTest 3，AnswerValidationServiceTest 7，DispatchAnswerGateTest 35，RigidWorkflowRuleServiceTest 6，StationEmergencyWorkflowTest 2。测试上下文未连接真实 JDBC，日志记录 `Failed to obtain JDBC Connection`；这不是 MySQL 集成通过的证据。
- 验证命令：`$env:PYTHONUTF8='1'; python _selftest.py`（工作目录：`KG_RAG/online`）。
- 验证结果：成功，退出码 0；固定渲染、引用可信性、降级、依赖排序、硬顺序、安全信息不足和危险源检查全部通过。未调用真实 LLM。
- 验证命令：`python _test_order_n.py`（工作目录：`KG_RAG/online`）。
- 验证结果：成功，退出码 0；跨 10 数值排序、合并/截断及端到端 1..14 步骤标签和岗位视图顺序均通过。修正前该脚本失败是测试解析器误把简报摘要当作重复主列表，调整断言后通过；业务排序代码未改。
- 验证命令：`$env:PYTHONUTF8='1'; python _test_v8_26_verify.py`（工作目录：`KG_RAG/online`）。
- 验证结果：成功，退出码 0；86 项定级阈值、指标缺失处理、升级守卫、事故等级映射及 prompt/schema 固定检查全部通过。未调用真实 LLM。
- 验证命令：`npm run build`（工作目录：`frontend`）。
- 验证结果：成功，退出码 0；Vite 生产构建完成，保留第三方 `@vueuse/core` PURE 注释提示。
- 验证命令：`git -c core.safecrlf=false diff --check`。
- 验证结果：成功，退出码 0，无空白错误。
- 场景覆盖结论：自动化覆盖答案有效证据校验、缺失证据阻断、动作顺序/必要事实错误、未批准/篡改/过期答案及多种权限和状态下发阻断、人工修改后新答案版本、AI/知识查询异常降级路径、紧急跳过驳回及 RAG 信息不足/伪造引用/硬顺序/固定阈值等。多事件并发交叉、真实 AI 服务超时、真实 MySQL DDL/事务/读写和浏览器人工操作未在本次环境验证；Mock 测试不作为这些集成验证的替代。
- 问题与决策：普通 Python 默认 GBK 下 `_selftest.py` 因勾选符号触发 `UnicodeEncodeError`，设置 `PYTHONUTF8=1` 后测试正常；`_test_order_n.py` 原端到端断言与当前简报摘要及岗位视图结构不兼容，按实际详细方案步骤标签修正测试判定，而非改变业务代码。真实数据库及 UI 检查仍需在有数据库连接和可操作浏览器的环境另行验收。
- 下一步：S08 回归基线完成；按既定逐步流程暂停，等待用户决定是否对真实 MySQL/浏览器未验证范围安排后续验收。
## 3. 问题与决策

- 阶段 0 已确认：当前仓库已经存在事件上报、AI 研判、车站复核、调度确认、指令下发、任务执行和事件日志骨架，后续优先增量实现，不进行大规模重构。
- 阶段 0 已确认：AI 结果必须经过独立校验和人工授权后才能成为可执行答案；AI 服务故障时保留本地规则降级路径。
- 待用户确认：是否按本文件默认约束执行，即保持现有技术栈且不引入新依赖。
- 待用户确认：第一阶段是否优先实现后端状态机/校验与审计，前端展示随后接入。
- 待用户确认：知识依据的权威来源是否以 `KG_RAG/online` 当前规程库和现有 `pre_plan` 为准，还是需要增加新的制度库。
- 风险：现有前端部分事件状态存在演示型 store；实施时必须以服务端状态和数据库记录为准，避免前后端状态不一致。
- 风险：现有 AI 研判字段主要保存等级、理由和预案文本，证据片段、版本、校验结果需要新增持久化结构。

### S06 决策补充（2026-10-21）

- 只允许最新批准答案下发，指令正文使用批准动作的原顺序编号文本；变更动作必须先修改答案并复核。
- 实时核验已接入的 pre_plan 版本与摘要；其他无法核验来源拒绝下发。人工修改新版本复制证据并保存校验记录。
- 同事件/答案/版本只允许下发一次，通过唯一索引保护重复提交；旧指令不伪造答案关联。
- 保留三档建议等级与四档法定等级的现有表达；与车站复核等级或已确认法定等级冲突时拒绝。
- 原 target 被占用，使用仅更改输出目录的临时 POM 完成验证：74 项后端测试及前端构建通过。真实 MySQL 和浏览器验收未执行，保留到 S08。

## 4. 验收清单

- [ ] 刚性业务流的状态、角色、前置条件和非法转移已定义并由服务端阻断。
- [ ] AI 辅助流输出结构化答案，包含结论、步骤、责任岗位、缺失事实、不确定性和依据引用。
- [ ] 每条关键结论都能定位到真实知识文档、版本、章节和片段。
- [ ] 证据、规则、完整性、顺序、知识新鲜度和权限校验结果已落库。
- [ ] 未通过关键校验或未完成人工授权的答案不能下发执行指令。
- [ ] 高风险事件必须由授权人员确认，人工接受/修改/驳回均保存原因和前后快照。
- [ ] AI 超时、异常或知识库不可用时，刚性业务流仍能运行并留下降级原因。
- [ ] 指令、任务、反馈和关闭操作均关联事件编号和批准答案版本。
- [ ] 可按事件重建完整时间线，审计记录具备操作人、时间、输入输出摘要和链式校验信息。
- [x] 固定回放和自动化测试覆盖正常、异常、越权、证据缺失、顺序错误和降级场景；未覆盖的集成场景见 S08 执行记录。
- [x] 前端构建、后端测试和相关 RAG 回放结果均已真实记录；真实 MySQL 与浏览器操作尚未验证。




