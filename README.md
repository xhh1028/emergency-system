# 城市轨道交通数字化应急系统

项目是一个城市轨道交通数字化应急系统，包含 Vue 前端、Spring Boot 后端和独立的知识图谱/RAG 工具目录。

```text
.
├─ frontend/              Vue 3 + Vite 前端
├─ backend/               Java 17 + Spring Boot 后端
├─ KG_RAG/                知识图谱与 RAG 脚本、数据
├─ tools/maven-runtime/   项目本地 Maven 运行时
├─ _archive/              构建产物、旧目录和临时文件归档
└─ README.md
```

## 启动后端

数据库连接配置保存在不会提交到版本库的 `backend/.env.local`。在一个终端中运行：

```powershell
cd backend
./start_backend.bat
```

后端默认地址为 `http://localhost:8081`。

## 启动前端

在另一个终端中运行：

```powershell
cd frontend
npm.cmd run dev
```

前端默认地址为 `http://localhost:5173`，开发代理会把 `/api` 和 `/uploads` 请求转发到后端 `8081` 端口。

## 构建与测试

```powershell
cd frontend
npm.cmd run build

cd ..\backend
mvn.cmd test
```

如果系统没有全局 Maven，可直接使用项目内的 `tools/maven-runtime/apache-maven-3.9.12/bin/mvn.cmd`。

后端接口、数据库初始化和本地账号配置详见 [backend/README.md](backend/README.md)。

## 目录说明

- `frontend/src/`：页面、路由、状态和 API 调用。
- `backend/src/`：Spring Boot 应用代码；`backend/database/` 保存数据库导入脚本。
- `KG_RAG/online/` 与 `KG_RAG/offline/`：RAG 在线服务和离线数据处理脚本。运行前请按脚本说明准备 Python 环境及外部服务。
- `_archive/`：本次整理保留的构建产物、旧目录和临时文件，不参与正常构建。

<!-- TODO: 补充已验证的 RAG 启动命令、外部服务地址和生产部署说明。 -->
