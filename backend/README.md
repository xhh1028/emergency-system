# 城市轨道交通应急系统后端

当前后端使用 Spring Boot 3.3、Java 17、Maven 和阿里云 RDS MySQL。用户、角色、岗位与车站信息直接读取现有的 `sys_user`、`sys_role`、`station_post`、`station`；事件历史读取 `event`、`task`、`feedback`。程序不会新建或删除业务表；启动时仅为既有 `event`、`task` 表补充本系统所需且缺失的兼容字段。

## 启动

后端默认端口为 `8081`，避免与本机占用 `8080` 的 NI 服务冲突。

```powershell
cd backend
mvn.cmd spring-boot:run
```

数据库连接信息可写在不会提交到版本库的 `backend/.env` 中，格式参考 `.env.example`：

```properties
DB_HOST=数据库地址
DB_PORT=3306
DB_NAME=subway_system
DB_USERNAME=team01
DB_PASSWORD=数据库密码
```

进入项目的 `frontend` 目录运行 `npm.cmd run dev` 后，Vite 会把 `/api` 和 `/uploads` 转发到 `http://localhost:8081`。

## 通用响应

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

除获取登录角色外，其余业务接口均需要请求头：

```text
Authorization: Bearer <登录接口返回的 token>
```

## 认证接口

### `GET /api/auth/roles`

返回登录页可选择的身份列表。

### `POST /api/auth/login`

`Content-Type: application/json`

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | String | 是 | `sys_user.phone`，即员工手机号 |
| password | String | 是 | 员工登录密码 |

```json
{
  "username": "13800000000",
  "password": "员工密码"
}
```

登录成功返回 `token` 和 `userInfo`。角色由 `sys_role.role_en_name` 映射，不能由前端自行指定。

### `POST /api/auth/logout`

撤销当前令牌。

### `POST /api/auth/change-password`

`Content-Type: application/json`

```json
{
  "oldPassword": "原密码",
  "newPassword": "新密码"
}
```

修改成功后当前令牌失效，需要使用新密码重新登录。历史明文密码保持兼容；修改后的密码使用 PBKDF2-HMAC-SHA256 加盐保存。

### `GET /api/auth/profile`

查询当前登录账号的真实个人资料，数据来自 `sys_user`、`sys_role`、`station_post` 和 `station`，包括姓名、登录手机号、人员类别、具体岗位、所属线路、所属车站和在岗状态。一线执行与后勤安保共用该接口和个人中心页面。

后勤安保按文档要求统一简化为“险情上报、我的待办、历史记录、个人中心”四个模块，不再根据子角色展示没有真实后端的安保值守、物资管理或维修进度模拟页面。

## 事件与历史接口

### `POST /api/events/report`

一线人员和后勤人员上报险情。`Content-Type: multipart/form-data`。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| eventTitle | String | 是 | 事件标题，最多 200 个字符 |
| eventType | String | 是 | `DEVICE_FAILURE`、`FIRE`、`PASSENGER`、`TRACK_OPERATION`、`CROWD_SECURITY`、`DISASTER_ENVIRONMENT`、`OTHER` |
| preLevel | String | 是 | `GENERAL`、`SERIOUS`、`EXTREMELY_SERIOUS` |
| faultyDevice | String | 设备故障时是 | 故障设备名称或编号，最多 200 个字符 |
| description | String | 是 | 现场事件描述 |
| images | File[] | 否 | 最多 5 张，JPG/PNG/WEBP，单张不超过 5MB |

成功时在现有 `event` 表中写入一条 `PENDING_ASSIGN` 状态记录：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 8,
    "eventNo": "EV-20260813120000-A1B2",
    "status": "PENDING_ASSIGN"
  }
}
```

### `GET /api/events/my-reports`

查询当前登录人员上报的事件。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| keyword | String | 否 | 匹配事件编号、类型或描述 |
| start | ISO 日期时间 | 否 | 起始上报时间 |
| end | ISO 日期时间 | 否 | 截止上报时间 |
| page | Integer | 否 | 默认 1 |
| size | Integer | 否 | 默认 10，最大 100 |

### `GET /api/events/my-completed-tasks`

查询当前登录人员作为执行人的已完成任务。参数与上一个接口一致，时间范围按反馈完成时间过滤。

## 车站事件复核与任务分派接口

以下接口仅允许角色为 `STATION` 且已绑定车站的管理员访问，数据自动限定为管理员所属车站。

### `GET /api/station/events`

查询当前车站的事件待办和处理记录。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| status | String | 否 | `ALL`、`PENDING_ASSIGN`、`STATION_HANDLE`、`REPORTED_TO_DISPATCH`、`FINISHED` |
| keyword | String | 否 | 匹配事件编号、类型、描述或上报人 |
| page | Integer | 否 | 默认 1 |
| size | Integer | 否 | 默认 10，最大 100 |

响应示例：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "list": [
      {
        "id": 15,
        "eventNo": "EV-20260813130000-A1B2",
        "eventType": "FIRE",
        "reporterLevel": "SERIOUS",
        "aiLevel": "EXTREMELY_SERIOUS",
        "status": "PENDING_ASSIGN",
        "reporterName": "员工姓名",
        "stationName": "西直门站",
        "createTime": "2026-08-13T13:00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10
  }
}
```

事件在一线人员提交时自动生成 `aiLevel`、`aiReason`、`aiSource` 和 `aiPlan`。配置 OpenAI 兼容接口后优先调用大模型生成研判与分步骤处置预案；未配置、超时或响应异常时，自动采用可解释的本地安全规则和标准处置步骤，确保上报主流程不中断。

可选的大模型环境变量：

```properties
AI_ENDPOINT=https://你的服务地址/v1/chat/completions
AI_API_KEY=你的密钥
AI_MODEL=模型名称
```

### `GET /api/station/events/{id}`

查询本站指定事件的完整信息，同时按照 `event_type` 和 AI 等级返回最多 5 条现有 `pre_plan` 预案。

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 15,
    "eventNo": "EV-20260813130000-A1B2",
    "description": "站台出现浓烟，正在组织疏散",
    "aiLevel": "EXTREMELY_SERIOUS",
    "plans": [
      {
        "id": 9,
        "name": "车站及轨道火警处置预案",
        "level": "一级",
        "content": "预案内容"
      }
    ]
  }
}
```

### `POST /api/station/events/{id}/decision`

确认 AI 判定或人工修改等级与处置路径。

```json
{
  "level": "GENERAL",
  "route": "TASK_ASSIGN"
}
```

| 参数 | 可选值 | 说明 |
| --- | --- | --- |
| level | `GENERAL`、`SERIOUS`、`EXTREMELY_SERIOUS` | 车站人工复核后的等级 |
| route | `TASK_ASSIGN`、`DISPATCH` | 站内任务分配或上报调度 |

`TASK_ASSIGN` 将事件更新为 `STATION_HANDLE`；`DISPATCH` 将事件更新为 `REPORTED_TO_DISPATCH` 并设置 `is_up_report=1`。两种路径的事件都保存在同一张 `event` 表，调度端均可读取。

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "status": "STATION_HANDLE",
    "nextPath": "/station/assign?eventId=15"
  }
}
```

### `GET /api/station/personnel/options`

返回本站角色为 `FRONT` 或 `SECURITY` 的人员，包含姓名、岗位和在岗状态，供任务分派选择。

### `POST /api/station/events/{id}/tasks`

为指定事件批量创建站内子任务。每条任务对应现有 `task` 表的一条记录和一名执行人；执行人必须是本站在岗的一线或后勤人员。

```json
{
  "tasks": [
    {
      "content": "封锁事发区域并疏散乘客",
      "executorId": 101,
      "deadline": "2026-08-13T14:30:00"
    },
    {
      "content": "检查设备并反馈故障原因",
      "executorId": 102,
      "deadline": null
    }
  ]
}
```

成功响应：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "created": 2
  }
}
```

## 调度指令接收与进度监控接口

以下接口仅允许已绑定车站的 `STATION` 角色访问，所有查询都由后端限定为当前用户所属车站。

### `GET /api/station/commands`

查询调度中心下发给本车站的指令。支持 `status=ALL|UNREAD|READ`、`keyword`、`page` 和 `size` 参数；关键字匹配指令内容、关联事件编号和下发人员姓名。

### `GET /api/station/commands/{id}`

查询一条本车站指令的详情及其关联事件信息。

### `POST /api/station/commands/{id}/sign`

由当前登录的车站管理员确认签收。接口会将现有 `dispatch_command.read_status` 更新为 `1`，并记录 `receive_user_id`；重复签收按幂等方式返回当前记录。

签收后可进入任务分配。调度指令产生的任务请求需要携带来源和指令编号：

```json
{
  "source": "DISPATCH",
  "commandId": 12,
  "tasks": [
    {
      "content": "封锁事发区域并引导乘客疏散",
      "executorId": 101,
      "deadline": "2026-08-13T23:30:00"
    }
  ]
}
```

后端会校验该指令属于本车站、已经签收且关联同一事件。普通站内安排可省略 `source` 和 `commandId`，默认来源为 `STATION`。

### `GET /api/station/tasks/progress`

查询本车站的真实任务进度。支持 `status=ALL|PENDING|IN_PROGRESS|COMPLETED|OVERDUE`、`keyword`、`page` 和 `size` 参数。逾期状态由未完成任务的 `deadline` 与当前时间动态判断，不修改数据库表结构。

### `GET /api/station/tasks/{id}`

查询任务详情及其全部 `feedback` 现场反馈记录。完成任务可在前端点击“查看报告”，查看反馈人员、文字、时间以及 `feedback_img` 中保存的现场图片。

## 车站人员管理接口

人员管理只使用现有 `sys_user`、`sys_role` 和 `station_post`，不新建表或增加字段。登录账号为 `sys_user.phone`；人员类别仅允许 `FRONT`（一线执行）和 `SECURITY`（后勤安保）。所有读写均由后端限定为当前车站管理员所属车站。

### `GET /api/station/personnel/options`

查询本车站一线执行和后勤安保人员，返回姓名、登录手机号、类别、岗位和在岗状态。

### `GET /api/station/personnel/posts`

查询 `station_post` 中可用岗位及其对应角色，供新增和编辑表单使用。

### `POST /api/station/personnel`

新增本站工作人员，同时创建可登录账号。手机号在 `sys_user` 中必须唯一，初始密码长度为6至32位，并以 PBKDF2-HMAC-SHA256 加盐结果保存。

```json
{
  "realName": "测试人员",
  "phone": "13800009991",
  "role": "FRONT",
  "postId": 1,
  "status": "ON_DUTY",
  "initialPassword": "123456"
}
```

### `PUT /api/station/personnel/{id}`

编辑本站工作人员的姓名、手机号、类别、岗位和在岗状态。禁止编辑其他车站人员，且岗位必须与人员类别匹配。

### `POST /api/station/personnel/{id}/reset-password`

管理员为忘记密码的本站工作人员设置新密码，禁止操作其他车站账号。

```json
{
  "newPassword": "654321"
}
```

## 调度事件流转与全线进度接口

以下接口仅允许 `DISPATCH` 角色访问。调度端不再维护前端模拟事件、指令或进度数据，全部读取现有 `event`、`dispatch_command`、`task` 和 `feedback`。

### `GET /api/dispatch/events`

查询已进入调度范围的事件，包括车站自主处置中的 `STATION_HANDLE`、上报调度的 `REPORTED_TO_DISPATCH` 和已归档的 `FINISHED`。支持 `status`、`keyword`、`page`、`size`。

### `GET /api/dispatch/events/{id}`

查询事件原始上报信息、AI研判、匹配预案、任务闭环数量及历史调度指令。

### `POST /api/dispatch/events/{id}/confirm`

对 `REPORTED_TO_DISPATCH` 事件确认已阅。系统使用 `event.dispatch_confirm` 和
`dispatch_confirm_time` 独立保存确认状态与时间，不再占用法定事件等级字段。启动时会自动为旧数据库补充字段，
并兼容迁移早期使用 `final_event_level=DISPATCH_CONFIRMED` 保存的记录。确认操作不会自动生成指令。

### `POST /api/dispatch/events/{id}/commands`

只有完成调度确认的严重事件才能下发指令。指令保存至 `dispatch_command`，接收车站取自事件所属车站，同时将过渡状态替换为正式法定等级。

```json
{
  "finalLevel": "II_SERIOUS",
  "content": "立即启动应急预案，组织人员疏散并持续反馈现场进度。"
}
```

法定等级支持 `IV_GENERAL`、`III_MAJOR`、`II_SERIOUS`、`I_EXTREMELY_SERIOUS`。

### `POST /api/dispatch/events/{id}/close`

只有已经生成任务且全部任务状态为 `COMPLETED` 的事件才能关闭。关闭后事件状态变为 `FINISHED`。

### `GET /api/dispatch/progress`

查询全网所有车站产生的真实 `task` 工单，支持 `stationId`、`status=ALL|PENDING|IN_PROGRESS|COMPLETED|OVERDUE`、`keyword`、`page` 和 `size`。

### `GET /api/dispatch/stations`

查询车站字典，供全线进度按车站筛选。

### `GET /api/dispatch/overview`

查询调度总览大屏的真实数据，返回事件总数、未闭环事件数、已闭环事件数、告警车站数，以及按线路排序的全部车站态势和最新10条未闭环事件。车站态势包含活跃事件数量、最高等级、事件摘要和可跳转的主事件编号。

调度总览首次进入时读取该接口，之后由 `/api/notifications/stream` 的 SSE 消息触发刷新。
新险情写入 `event` 后，即使仍处于 `PENDING_ASSIGN`（车站待复核），对应车站圆点也会立即进入告警状态；
点击圆点会打开该事件的调度详情。浏览器断线后由 EventSource 自动重连。

### `GET /api/dispatch/archive`

分页查询 `event_status=FINISHED` 的真实归档事件，支持 `keyword`、正式法定等级 `level`、归档年份 `year`、`page` 和 `size`。列表同时返回任务闭环数量、历史指令数量和最后现场反馈时间。

### `GET /api/dispatch/archive/years`

查询数据库中已有归档事件的年份，用于归档页面筛选。归档详情复用事件详情接口，并包含处置预案、调度指令、全部任务和每项任务的现场反馈。现有 `event` 表没有独立结案时间字段，因此页面将最后现场反馈时间作为闭环时间参考；没有反馈时回退到事件发生时间。

## 一线执行与后勤安保任务接口

以下接口由一线执行（`FRONT`）和后勤安保（`SECURITY`）共用。后端始终使用登录令牌中的用户编号匹配 `task.executor_id`，调用方不能通过参数查看或操作他人的任务。

### `GET /api/tasks`

查询当前人员的任务，支持 `status=ALL|PENDING|IN_PROGRESS|COMPLETED|OVERDUE`、`keyword`、`page` 和 `size`。关键词匹配任务内容、事件编号和车站名称。

### `GET /api/tasks/{id}`

查询当前人员的任务详情，包括关联事件、任务进度以及该任务的全部现场反馈；访问未分配给当前人员的任务会被拒绝。

### `POST /api/tasks/{id}/start`

将本人待执行任务从 `PENDING` 更新为 `IN_PROGRESS`。已经开始的任务重复调用时按幂等方式返回当前数据。

### `POST /api/tasks/{id}/complete`

使用 `multipart/form-data` 提交完成反馈：

- `feedbackText`：必填，最长2000个字符；
- `images`：可选，最多5张，单张不超过5MB，仅支持 JPG、PNG、WEBP。

接口只允许 `IN_PROGRESS` 任务完成，并在同一数据库事务内把任务更新为 `COMPLETED`、向 `feedback` 写入文字和图片地址。车站进度监控和调度全线进度会直接读取这一状态变化。

## 测试

```powershell
cd backend
mvn.cmd test
```

自动化测试使用模拟仓库，不会连接或写入阿里云 RDS。
