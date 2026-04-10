# 竹林司马后端API使用指南

## 📖 目录
1. [快速开始](#快速开始)
2. [API基础信息](#api基础信息)
3. [认证与授权](#认证与授权)
4. [用户管理API](#用户管理api)
5. [内容管理API](#内容管理api)
6. [媒体管理API](#媒体管理api)
7. [管理后台API](#管理后台api)
8. [错误处理](#错误处理)
9. [最佳实践](#最佳实践)

## 🚀 快速开始

### 环境要求
- Python 3.9+
- PostgreSQL 14+ / SQLite (开发环境)
- Redis (可选，用于缓存)

### 安装步骤
```bash
# 1. 克隆项目
git clone https://github.com/yourusername/zhulin-sima-backend.git
cd zhulin-sima-backend

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑.env文件，设置数据库连接等信息

# 5. 初始化数据库
python scripts/database_init.py

# 6. 运行服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker启动
```bash
# 使用Docker Compose一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 🌐 API基础信息

### 基础URL
```
开发环境: http://localhost:8000
生产环境: https://api.yourdomain.com
```

### API版本前缀
所有API都使用以下前缀：
```
/api/v1
```

### 响应格式
所有API响应都遵循以下格式：

**成功响应:**
```json
{
  "code": 200,
  "message": "操作成功",
  "data": {...}
}
```

**错误响应:**
```json
{
  "code": 400,
  "message": "错误的请求参数",
  "detail": "详细的错误信息"
}
```

### HTTP状态码
| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 422 | Unprocessable Entity | 验证错误 |
| 500 | Internal Server Error | 服务器内部错误 |

## 🔐 认证与授权

### JWT认证
系统使用JWT（JSON Web Tokens）进行认证。

### 获取访问令牌
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**响应:**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### 使用令牌
在请求头中添加Authorization头：
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 刷新令牌
```http
POST /api/v1/auth/refresh
Authorization: Bearer {refresh_token}
```

## 👥 用户管理API

### 用户注册
```http
POST /api/v1/users/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "StrongPassword123!",
  "full_name": "New User",
  "phone": "+861234567890"
}
```

### 获取用户信息
```http
GET /api/v1/users/me
Authorization: Bearer {access_token}
```

### 更新用户信息
```http
PUT /api/v1/users/me
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "full_name": "Updated Name",
  "phone": "+861234567891",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

### 修改密码
```http
POST /api/v1/users/change-password
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

### 管理员获取用户列表
```http
GET /api/v1/users/
Authorization: Bearer {access_token}
Query参数:
  - page: 页码 (默认: 1)
  - per_page: 每页数量 (默认: 20)
  - search: 搜索关键词
  - is_active: 是否激活
  - role: 角色
```

### 管理员更新用户
```http
PUT /api/v1/users/{user_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "is_active": true,
  "role": "editor"
}
```

## 📝 内容管理API

### 创建内容
```http
POST /api/v1/content/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "文章标题",
  "content": "文章内容...",
  "content_type": "article",
  "status": "draft",
  "tags": ["技术", "教程"],
  "category": "编程",
  "cover_image": "https://example.com/cover.jpg",
  "summary": "文章摘要"
}
```

### 获取内容列表
```http
GET /api/v1/content/
Query参数:
  - page: 页码
  - per_page: 每页数量
  - content_type: 内容类型
  - status: 状态
  - category: 分类
  - tag: 标签
  - author_id: 作者ID
  - sort_by: 排序字段
  - order: 排序方向 (asc/desc)
```

### 获取单篇内容
```http
GET /api/v1/content/{content_id}
```

### 更新内容
```http
PUT /api/v1/content/{content_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "更新后的标题",
  "content": "更新后的内容...",
  "status": "published"
}
```

### 删除内容
```http
DELETE /api/v1/content/{content_id}
Authorization: Bearer {access_token}
```

### 创建评论
```http
POST /api/v1/content/{content_id}/comments
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "content": "评论内容",
  "parent_id": null  # 父评论ID，用于回复
}
```

### 获取评论列表
```http
GET /api/v1/content/{content_id}/comments
Query参数:
  - page: 页码
  - per_page: 每页数量
  - parent_id: 父评论ID
```

## 📁 媒体管理API

### 上传文件
```http
POST /api/v1/media/upload
Authorization: Bearer {access_token}
Content-Type: multipart/form-data

表单字段:
  - file: 文件 (必填)
  - description: 文件描述 (可选)
  - tags: 标签，逗号分隔 (可选)
```

**响应:**
```json
{
  "code": 200,
  "message": "文件上传成功",
  "data": {
    "id": 1,
    "filename": "example.jpg",
    "file_url": "/media/files/example.jpg",
    "file_size": 1024000,
    "mime_type": "image/jpeg",
    "uploaded_at": "2026-04-10T10:30:00Z"
  }
}
```

### 获取文件列表
```http
GET /api/v1/media/files
Authorization: Bearer {access_token}
Query参数:
  - page: 页码
  - per_page: 每页数量
  - mime_type: 文件类型
  - uploader_id: 上传者ID
  - start_date: 开始日期
  - end_date: 结束日期
```

### 获取文件信息
```http
GET /api/v1/media/files/{file_id}
```

### 下载文件
```http
GET /api/v1/media/files/{file_id}/download
```

### 删除文件
```http
DELETE /api/v1/media/files/{file_id}
Authorization: Bearer {access_token}
```

### 创建处理任务
```http
POST /api/v1/media/process-tasks
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "media_id": 1,
  "task_type": "compress",
  "parameters": {
    "quality": 80,
    "max_width": 1920
  }
}
```

### 获取处理任务状态
```http
GET /api/v1/media/process-tasks/{task_id}
Authorization: Bearer {access_token}
```

## 🛠️ 管理后台API

### 获取系统状态
```http
GET /api/v1/admin/dashboard
Authorization: Bearer {access_token}
需要管理员权限
```

### 获取用户统计
```http
GET /api/v1/admin/users/stats
Authorization: Bearer {access_token}
需要管理员权限
```

### 获取内容统计
```http
GET /api/v1/admin/content/stats
Authorization: Bearer {access_token}
需要管理员权限
```

### 获取系统日志
```http
GET /api/v1/admin/system/logs
Authorization: Bearer {access_token}
需要管理员权限
Query参数:
  - level: 日志级别
  - start_date: 开始时间
  - end_date: 结束时间
  - page: 页码
  - per_page: 每页数量
```

### 内容审核
```http
POST /api/v1/admin/content/{content_id}/review
Authorization: Bearer {access_token}
需要审核员权限
Content-Type: application/json

{
  "action": "approve",  # approve/reject
  "review_notes": "内容符合规范"
}
```

### 用户权限管理
```http
POST /api/v1/admin/users/{user_id}/roles
Authorization: Bearer {access_token}
需要超级管理员权限
Content-Type: application/json

{
  "role": "editor",
  "permissions": ["content:create", "content:edit"]
}
```

## ⚠️ 错误处理

### 常见错误码
| 错误码 | 含义 | 解决方法 |
|--------|------|----------|
| 1001 | 认证失败 | 检查令牌是否有效 |
| 1002 | 权限不足 | 检查用户角色和权限 |
| 1003 | 令牌过期 | 重新登录获取新令牌 |
| 2001 | 资源不存在 | 检查资源ID是否正确 |
| 2002 | 资源冲突 | 检查是否有重复数据 |
| 3001 | 参数验证失败 | 检查请求参数格式 |
| 3002 | 文件类型不支持 | 检查上传文件格式 |
| 3003 | 文件大小超限 | 压缩文件或分片上传 |
| 4001 | 数据库错误 | 联系管理员 |
| 5001 | 服务器内部错误 | 联系管理员 |

### 错误响应示例
```json
{
  "code": 4001,
  "message": "数据库操作失败",
  "detail": "无法连接到数据库服务器",
  "timestamp": "2026-04-10T10:30:00Z",
  "request_id": "req_1234567890"
}
```

## 🏆 最佳实践

### 1. 使用HTTPS
生产环境务必使用HTTPS，保护数据传输安全。

### 2. 令牌管理
- 将令牌存储在安全的地方
- 不要将令牌提交到版本控制系统
- 定期刷新令牌

### 3. 错误处理
- 始终检查HTTP状态码
- 处理网络错误和超时
- 实现重试机制

### 4. 性能优化
- 使用分页获取列表数据
- 合理使用缓存
- 压缩大文件上传

### 5. 安全性
- 验证所有输入参数
- 限制API调用频率
- 记录重要的操作日志

### 6. 开发建议
- 使用API客户端工具（如Postman、Insomnia）
- 编写自动化测试
- 监控API使用情况

## 📱 客户端示例

### Python客户端
```python
import requests
from typing import Optional

class ZhulinSimaClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.token: Optional[str] = None
        
    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        response = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()['data']
            self.token = data['access_token']
            return True
        return False
    
    def get_user_info(self):
        """获取当前用户信息"""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(
            f"{self.base_url}/api/v1/users/me",
            headers=headers
        )
        return response.json()
    
    def create_content(self, title: str, content: str):
        """创建内容"""
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "title": title,
            "content": content,
            "content_type": "article",
            "status": "draft"
        }
        response = requests.post(
            f"{self.base_url}/api/v1/content/",
            json=data,
            headers=headers
        )
        return response.json()

# 使用示例
client = ZhulinSimaClient()
if client.login("username", "password"):
    user_info = client.get_user_info()
    print(f"欢迎，{user_info['data']['username']}!")
```

### JavaScript/TypeScript客户端
```typescript
class ZhulinSimaClient {
    private baseUrl: string;
    private token: string | null = null;

    constructor(baseUrl = "http://localhost:8000") {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    async login(username: string, password: string): Promise<boolean> {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            const data = await response.json();
            this.token = data.data.access_token;
            return true;
        }
        return false;
    }

    async getUserInfo() {
        const response = await fetch(`${this.baseUrl}/api/v1/users/me`, {
            headers: { 'Authorization': `Bearer ${this.token}` }
        });
        return response.json();
    }
}
```

## 🔗 相关资源

- **Swagger文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **GitHub仓库**: https://github.com/yourusername/zhulin-sima-backend
- **问题反馈**: https://github.com/yourusername/zhulin-sima-backend/issues

## 📄 更新日志

### v1.0.0 (2026-04-10)
- 初始版本发布
- 用户管理系统
- 内容管理系统
- 媒体管理系统
- 管理后台

---
**文档版本**: v1.0.0  
**最后更新**: 2026-04-10  
**维护者**: 竹林司马开发团队