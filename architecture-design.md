# 竹林司马后端系统架构设计

## 项目概述

**竹林司马**是一个需要重构的后端系统，目标是构建一个具有高扩展性和稳定性的现代化架构。

## 1. 架构目标

### 核心目标
- **可扩展性**: 支持水平扩展，适应业务快速增长
- **高可用性**: 99.9%+ 的系统可用性
- **安全性**: 多层安全防护，符合行业安全标准
- **性能**: API响应时间 < 200ms (95%百分位)
- **可维护性**: 清晰的代码结构和完整的文档

### 业务需求推测
基于"竹林司马"项目名称，可能涉及以下业务场景：
- 内容管理系统
- 用户社区/社交功能
- 数据分析和报表
- 多媒体内容处理
- 电商或交易功能

## 2. 技术栈选型

### 2.1 核心编程语言
**Python 3.11+** - 选择理由：
- 生态系统成熟，库支持完善
- 开发效率高，维护成本低
- 强大的异步支持 (FastAPI)
- AI/ML集成能力强

### 2.2 Web框架
**FastAPI** - 选择理由：
- 高性能，基于Starlette和Pydantic
- 自动API文档生成 (OpenAPI/Swagger)
- 异步支持优秀
- 类型提示完善

### 2.3 数据库层
**PostgreSQL 15+** - 主数据库
- ACID兼容，事务支持完善
- JSONB支持NoSQL功能
- 地理空间数据支持 (PostGIS)
- 强大的全文搜索

**Redis 7+** - 缓存层
- 内存缓存，高速读写
- 会话存储
- 分布式锁实现
- 消息队列功能

### 2.4 消息队列
**RabbitMQ** 或 **Apache Kafka** - 选择：
- RabbitMQ: 成熟稳定，易于部署
- Kafka: 高吞吐量，适合大数据场景

### 2.5 对象存储
**MinIO** (自托管) 或 **AWS S3** (云服务)
- 文件、图片、视频存储
- CDN集成
- 生命周期管理

### 2.6 监控与日志
- **Prometheus + Grafana**: 系统监控和告警
- **ELK Stack**: 日志收集和分析
- **Sentry**: 错误追踪和应用性能监控

## 3. 架构模式

### 3.1 微服务架构设计

```mermaid
graph TB
    subgraph "API Gateway层"
        GW[API Gateway<br/>Nginx/Kong]
    end
    
    subgraph "核心微服务层"
        AUTH[认证服务<br/>JWT/OAuth2]
        USER[用户服务]
        CONTENT[内容服务]
        MEDIA[媒体服务]
        NOTIFY[通知服务]
    end
    
    subgraph "数据服务层"
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        MQ[RabbitMQ]
        STORE[对象存储]
    end
    
    subgraph "支持服务层"
        MONITOR[监控系统]
        LOG[日志系统]
        CACHE[CDN]
    end
    
    GW --> AUTH
    GW --> USER
    GW --> CONTENT
    GW --> MEDIA
    GW --> NOTIFY
    
    AUTH --> PG
    USER --> PG
    CONTENT --> PG
    MEDIA --> STORE
    NOTIFY --> MQ
    
    AUTH --> REDIS
    USER --> REDIS
    CONTENT --> REDIS
    
    MONITOR -.-> 核心微服务层
    LOG -.-> 核心微服务层
    CACHE -.-> MEDIA
```

### 3.2 服务分解原则
1. **业务边界清晰**: 每个服务负责一个业务领域
2. **独立数据库**: 每个服务拥有自己的数据库模式
3. **异步通信**: 服务间通过消息队列通信
4. **API契约**: 明确的API版本控制和文档

## 4. 数据库架构设计

### 4.1 PostgreSQL数据库模式设计

```sql
-- 核心用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- bcrypt哈希
    full_name VARCHAR(100),
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL -- 软删除
);

-- 用户角色和权限
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- 内容管理表
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    excerpt TEXT,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    content_type VARCHAR(50) DEFAULT 'article' CHECK (content_type IN ('article', 'video', 'audio', 'image')),
    metadata JSONB DEFAULT '{}',
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

-- 评论表
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT true,
    like_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

-- 媒体资源表
CREATE TABLE media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT NOT NULL,
    storage_bucket VARCHAR(100) DEFAULT 'default',
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    width INTEGER,
    height INTEGER,
    duration_seconds INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 操作日志表
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    request_path TEXT,
    request_method VARCHAR(10),
    request_body JSONB,
    response_status INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 4.2 关键索引设计
```sql
-- 性能优化索引
CREATE INDEX idx_users_email_active ON users(email) WHERE deleted_at IS NULL AND is_active = true;
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_username_active ON users(username) WHERE deleted_at IS NULL AND is_active = true;

CREATE INDEX idx_content_status_published ON content(status, published_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_author ON content(author_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_slug ON content(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_created_at ON content(created_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_comments_content ON comments(content_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_user ON comments(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_parent ON comments(parent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_created_at ON comments(created_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_audit_logs_user_action ON audit_logs(user_id, action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
```

### 4.3 Redis缓存策略
```yaml
缓存策略:
  - 用户会话: 24小时过期
  - 频繁访问内容: 1小时过期
  - API速率限制: 滑动窗口计数
  - 分布式锁: 5秒自动释放
  
缓存键设计:
  - 用户信息: user:{user_id}
  - 内容缓存: content:{content_id}
  - API速率限制: rate_limit:{user_id}:{endpoint}
  - 会话: session:{session_id}
```

## 5. API架构设计

### 5.1 REST API设计原则
1. **资源导向**: 所有端点对应资源
2. **版本控制**: `/api/v1/` 前缀
3. **统一响应格式**: JSON标准格式
4. **错误处理**: 标准HTTP状态码和错误消息
5. **分页和过滤**: 统一查询参数

### 5.2 API端点设计
```
/api/v1/
├── auth/                  # 认证相关
│   ├── login/            POST    用户登录
│   ├── register/         POST    用户注册
│   ├── refresh/          POST    Token刷新
│   └── logout/           POST    用户登出
├── users/                # 用户管理
│   ├── {id}/            GET     获取用户信息
│   ├── {id}/profile/    GET/PUT 用户资料
│   └── {id}/settings/   GET/PUT 用户设置
├── content/             # 内容管理
│   ├──                  GET     内容列表
│   ├── {id}/           GET     获取内容
│   ├── {id}/comments/  GET     获取评论
│   └── {id}/like/      POST    点赞/取消
├── media/               # 媒体管理
│   ├── upload/         POST    上传文件
│   └── {id}/           GET     获取媒体信息
└── admin/               # 管理接口
    ├── users/          GET     用户列表
    ├── content/        GET     内容管理
    └── audit-logs/     GET     操作日志
```

### 5.3 API安全规范
```python
# 示例：带安全保护的FastAPI端点
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta

app = FastAPI(title="竹林司马API", version="1.0.0")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

class User(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证"
            )
        # 从数据库或缓存获取用户
        user = await get_user_from_db(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        return user
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token验证失败"
        )

@app.get("/api/v1/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    }
```

## 6. 部署架构

### 6.1 Docker容器化部署
```dockerfile
# Dockerfile示例
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 运行应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 Docker Compose配置
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: zhulin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: zhulinsma
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zhulin"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: zhulin
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    ports:
      - "5672:5672"   # AMQP协议端口
      - "15672:15672" # 管理界面端口
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

  api:
    build: .
    environment:
      DATABASE_URL: postgresql://zhulin:${DB_PASSWORD}@postgres:5432/zhulinsma
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      RABBITMQ_URL: amqp://zhulin:${RABBITMQ_PASSWORD}@rabbitmq:5672
      SECRET_KEY: ${API_SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_started
    volumes:
      - ./logs:/app/logs
      - ./uploads:/app/uploads

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
```

## 7. 监控与告警

### 7.1 关键监控指标
1. **应用性能**:
   - API响应时间 (P95, P99)
   - 请求成功率
   - 错误率
   - 活跃连接数

2. **数据库性能**:
   - 查询执行时间
   - 连接池使用率
   - 缓存命中率
   - 死锁数量

3. **系统资源**:
   - CPU使用率
   - 内存使用率
   - 磁盘I/O
   - 网络流量

### 7.2 告警策略
```yaml
告警规则:
  - 关键错误: 立即通知(电话/短信)
  - 性能降级: 15分钟内通知(邮件/即时通讯)
  - 资源告警: 30分钟内通知(邮件)
  
告警阈值:
  - API响应时间 > 500ms (持续5分钟)
  - 错误率 > 1% (持续10分钟)
  - CPU使用率 > 80% (持续5分钟)
  - 内存使用率 > 85% (持续5分钟)
```

## 8. 安全架构

### 8.1 安全策略层级
1. **网络层安全**:
   - 防火墙规则
   - DDoS防护
   - WAF(Web应用防火墙)

2. **应用层安全**:
   - 输入验证和清理
   - SQL注入防护
   - XSS防护
   - CSRF防护

3. **数据层安全**:
   - 传输加密 (TLS 1.3)
   - 静态数据加密
   - 密钥管理
   - 数据脱敏

4. **访问控制**:
   - RBAC (基于角色的访问控制)
   - 最小权限原则
   - API密钥管理
   - 多因素认证

### 8.2 安全审计
- 所有敏感操作记录审计日志
- 定期安全扫描
- 渗透测试
- 代码安全审查

## 9. 扩展性设计

### 9.1 水平扩展策略
1. **无状态服务**: API服务无状态，可水平扩展
2. **数据库分片**: 基于用户ID或业务分区
3. **读写分离**: 主从数据库架构
4. **CDN加速**: 静态资源缓存

### 9.2 弹性设计
1. **断路器模式**: 防止级联故障
2. **重试策略**: 指数退避重试
3. **降级方案**: 核心功能优先保障
4. **限流保护**: 防止资源耗尽

## 10. 实施路线图

### 阶段1: 基础架构 (1-2周)
1. 项目结构搭建
2. 数据库设计和部署
3. 核心API框架实现
4. 基本认证系统

### 阶段2: 核心功能 (2-3周)
1. 用户管理模块
2. 内容管理模块
3. 媒体处理模块
4. 缓存系统集成

### 阶段3: 高级功能 (2-3周)
1. 通知系统
2. 搜索功能
3. 数据分析
4. 第三方集成

### 阶段4: 运维优化 (1-2周)
1. 监控系统部署
2. 自动化部署流程
3. 性能优化
4. 安全加固

## 11. 成功指标

### 技术指标
- API响应时间 P95 < 200ms
- 系统可用性 > 99.9%
- 错误率 < 0.1%
- 数据库查询性能 < 100ms

### 业务指标
- 用户注册成功率 > 95%
- 内容加载时间 < 3秒
- 媒体上传成功率 > 99%
- 系统并发支持 > 1000用户

---

**架构师**: 后端架构师Agent  
**设计时间**: 2026年4月9日  
**版本**: 1.0.0  
**状态**: 设计草案