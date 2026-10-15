# 城市轨道交通数字化应急系统

项目已按前后端分离结构组织：

```text
emergency-system/
├─ frontend/   Vue 3 + Vite 前端
├─ backend/    Java 17 + Spring Boot 后端
├─ .tools/     项目本地开发工具
└─ README.md
```

## 启动后端

数据库连接配置保存在 `backend/.env`。在一个终端中运行：

```powershell
cd backend
mvn.cmd spring-boot:run
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

后端接口和数据库配置详见 [backend/README.md](backend/README.md)。
