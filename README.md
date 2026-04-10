# 竹林司马后端系统

一个现代化、可扩展、高性能的内容管理系统后端，基于Python FastAPI构建。

## 📋 项目概述

竹林司马是一个完整的后端系统架构设计，适用于内容管理、用户社区、多媒体处理等场景。系统采用微服务架构思想，具备高可用性、高扩展性和安全性。

### 核心特性

- 🚀 **高性能**: 基于FastAPI和异步编程，支持高并发
- 🏗️ **可扩展**: 微服务架构，支持水平扩展
- 🔒 **安全**: 多层安全防护，符合行业标准
- 📊 **监控**: 完整的监控和日志系统
- 🐳 **容器化**: 完整的Docker和Kubernetes支持
- 📈 **可观测**: Prometheus + Grafana监控体系

## 🏗️ 系统架构

### 技术栈

| 组件 | 技术选择 | 说明 |
|------|----------|------|
| **编程语言** | Python 3.11+ | 高性能，生态系统完善 |
| **Web框架** | FastAPI | 异步，自动API文档 |
| **数据库** | PostgreSQL 15+ | 主数据库，ACID兼容 |
| **缓存** | Redis 7+ | 分布式缓存和会话 |
| **消息队列** | RabbitMQ | 异步任务处理 |
| **对象存储** | MinIO | 自托管的S3兼容存储 |
| **监控** | Prometheus + Grafana | 系统监控和可视化 |
| **容器** | Docker + Docker Compose | 容器化部署 |

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                     客户端层                              │
├─────────────────────────────────────────────────────────┤
│                 API网关层 (Nginx/Kong)                   │
├─────────────────────────────────────────────────────────┤
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│   │ 认证服务 │  │ 用户服务 │  │内容服务 │  │媒体服务 │   │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
├─────────────────────────────────────────────────────────┤
│   ┌─────────────────────────────────────────────────┐   │
│   │               数据层 (PostgreSQL)                │   │
│   └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│   │ Redis缓存│  │RabbitMQ │  │ MinIO   │  │ 监控    │   │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Docker 20.10+ 和 Docker Compose
- PostgreSQL 15+
- Redis 7+

### 开发环境设置

1. **克隆项目**
   ```bash
   git clone https://github.com/zhulinsma/zhulinsma-backend.git
   cd zhulinsma-backend
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # 或
   venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # 开发依赖
   ```

4. **环境配置**
   ```bash
   cp .env.example .env
   # 编辑.env文件，配置数据库连接等信息
   ```

5. **运行开发服务器**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker部署

1. **使用Docker Compose启动所有服务**
   ```bash
   cd docker
   docker-compose up -d
   ```

2. **访问服务**
   - API: http://localhost:8000
   - API文档: http://localhost:8000/api/docs
   - MinIO控制台: http://localhost:9001
   - RabbitMQ管理: http://localhost:15672
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090

3. **停止服务**
   ```bash
   docker-compose down
   ```

## 📁 项目结构

```
zhulinsma-backend/
├── src/                          # 源代码目录
│   ├── core/                     # 核心模块
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── cache.py             # 缓存管理
│   │   ├── security.py          # 安全模块
│   │   └── exceptions.py        # 异常处理
│   ├── api/                     # API路由层
│   │   ├── v1/                  # API v1版本
│   │   │   ├── auth.py          # 认证API
│   │   │   ├── users.py         # 用户API
│   │   │   ├── content.py       # 内容API
│   │   │   ├── comments.py      # 评论API
│   │   │   ├── media.py         # 媒体API
│   │   │   └── notifications.py # 通知API
│   │   └── middleware/          # 中间件
│   │       ├── auth.py          # 认证中间件
│   │       ├── logging.py       # 日志中间件
│   │       └── rate_limit.py    # 限流中间件
│   ├── models/                  # 数据模型
│   ├── schemas/                 # Pydantic模式
│   ├── services/                # 业务逻辑层
│   ├── repositories/            # 数据访问层
│   ├── tasks/                   # 后台任务
│   └── utils/                   # 工具函数
├── tests/                       # 测试目录
├── migrations/                  # 数据库迁移
├── docker/                      # Docker配置
├── docs/                        # 文档
└── scripts/                     # 部署脚本
```

## 🔧 配置说明

### 环境变量

主要环境变量配置（详见 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_ENV` | 应用环境 | `development` |
| `DATABASE_URL` | 数据库连接URL | `postgresql://zhulin:password@localhost:5432/zhulinsma` |
| `REDIS_URL` | Redis连接URL | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | JWT密钥 | `change-this-in-production` |
| `FILE_STORAGE_PROVIDER` | 文件存储提供商 | `local` |

### 数据库配置

系统使用PostgreSQL作为主数据库，主要表包括：
- `users` - 用户表
- `content` - 内容表
- `comments` - 评论表
- `media` - 媒体文件表
- `notifications` - 通知表

详细数据库设计见 [database-api-design.md](database-api-design.md)。

## 🔐 安全特性

### 认证和授权
- JWT令牌认证
- OAuth2支持
- 基于角色的访问控制 (RBAC)
- 密码强度验证

### 安全防护
- SQL注入防护
- XSS防护
- CSRF防护
- 速率限制
- 输入验证和清理

### 审计和日志
- 操作审计日志
- 安全事件记录
- 请求日志
- 错误追踪

## 📊 监控和运维

### 健康检查
```bash
curl http://localhost:8000/health
```

### 监控指标
- API响应时间
- 错误率
- 数据库连接池状态
- Redis缓存命中率
- 系统资源使用情况

### 日志管理
- 结构化日志 (JSON格式)
- 日志分级 (DEBUG, INFO, WARNING, ERROR)
- 日志轮转和归档
- 集中式日志收集 (ELK Stack)

## 🧪 测试

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_auth.py

# 生成测试覆盖率报告
pytest --cov=src --cov-report=html
```

### 测试类型
- **单元测试**: 测试单个函数或类
- **集成测试**: 测试多个组件集成
- **端到端测试**: 测试完整API流程
- **性能测试**: 测试系统性能和负载能力

## 📈 性能优化

### 数据库优化
- 连接池管理
- 查询优化和索引
- 读写分离
- 数据库分片

### 缓存策略
- 多级缓存 (内存 + Redis)
- 缓存预热
- 缓存失效策略
- 分布式锁

### 异步处理
- 后台任务 (Celery)
- 消息队列 (RabbitMQ)
- 异步数据库操作
- 异步文件处理

## 🚢 部署

### 生产环境部署

1. **使用Docker Compose**
   ```bash
   # 生产环境配置
   APP_ENV=production docker-compose -f docker-compose.prod.yml up -d
   ```

2. **使用Kubernetes**
   ```bash
   # 应用Kubernetes配置
   kubectl apply -f k8s/
   ```

3. **使用云平台**
   - AWS ECS/EKS
   - Google Cloud Run/GKE
   - Azure Container Instances/AKS

### 持续集成/持续部署 (CI/CD)

GitHub Actions配置：
- 代码质量检查
- 自动化测试
- 镜像构建和推送
- 自动部署

## 📚 API文档

### 在线文档
启动应用后访问：
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### API端点
主要API端点：
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/users/me` - 获取当前用户
- `GET /api/v1/content` - 获取内容列表
- `POST /api/v1/content` - 创建内容
- `POST /api/v1/media/upload` - 上传文件

详细API规范见 [database-api-design.md](database-api-design.md)。

## 🔄 数据库迁移

### 使用Alembic
```bash
# 创建迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 迁移策略
- 零停机迁移
- 向后兼容
- 数据验证和回滚计划

## 🤝 贡献指南

### 开发流程
1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

### 代码规范
- 使用Black进行代码格式化
- 使用isort进行导入排序
- 使用flake8进行代码检查
- 使用mypy进行类型检查

### 提交消息格式
使用约定式提交：
```
类型(范围): 描述

正文...

脚注...
```

类型包括：`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

- 问题跟踪: [GitHub Issues](https://github.com/zhulinsma/zhulinsma-backend/issues)
- 文档: [项目Wiki](https://github.com/zhulinsma/zhulinsma-backend/wiki)
- 邮件: team@zhulinsma.com

## 🏆 性能指标

| 指标 | 目标值 | 当前状态 |
|------|--------|----------|
| API响应时间 (P95) | < 200ms | - |
| 系统可用性 | > 99.9% | - |
| 数据库查询性能 | < 100ms | - |
| 并发用户数 | > 1000 | - |
| 错误率 | < 0.1% | - |

---

**架构师**: 后端架构师Agent  
**版本**: 1.0.0  
**最后更新**: 2026年4月9日