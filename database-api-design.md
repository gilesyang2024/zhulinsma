# 竹林司马数据库架构与API规范

## 1. 数据库架构详细设计

### 1.1 数据库模式设计

#### 核心实体关系图
```mermaid
erDiagram
    users ||--o{ user_roles : "has"
    users ||--o{ content : "creates"
    users ||--o{ comments : "creates"
    users ||--o{ media : "uploads"
    users ||--o{ audit_logs : "generates"
    
    roles ||--o{ user_roles : "assigned"
    
    content ||--o{ comments : "has"
    content ||--o{ content_tags : "tagged"
    content ||--o{ content_categories : "categorized"
    
    tags ||--o{ content_tags : "applied"
    categories ||--o{ content_categories : "applied"
    
    comments ||--o{ comments : "replies"
```

#### 1.1.1 用户相关表
```sql
-- 用户表 (扩展)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    nickname VARCHAR(50),
    avatar_url TEXT,
    bio TEXT,
    gender VARCHAR(10) CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say')),
    birth_date DATE,
    location JSONB, -- {city: '广州', country: '中国'}
    website_url TEXT,
    social_links JSONB DEFAULT '{}', -- {github: '...', twitter: '...'}
    
    -- 状态标志
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    is_email_verified BOOLEAN DEFAULT false,
    is_phone_verified BOOLEAN DEFAULT false,
    
    -- 安全相关
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_login_ip INET,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    
    -- 约束
    CONSTRAINT chk_username_length CHECK (length(username) >= 3),
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- 用户配置表
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_notifications BOOLEAN DEFAULT true,
    push_notifications BOOLEAN DEFAULT true,
    privacy_level VARCHAR(20) DEFAULT 'public' CHECK (privacy_level IN ('private', 'friends_only', 'public')),
    language VARCHAR(10) DEFAULT 'zh-CN',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    theme VARCHAR(20) DEFAULT 'light' CHECK (theme IN ('light', 'dark', 'auto')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 用户统计表
CREATE TABLE user_statistics (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    content_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    like_count_received INTEGER DEFAULT 0,
    follower_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    total_view_count INTEGER DEFAULT 0,
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 1.1.2 内容管理系统表
```sql
-- 内容表 (支持多种类型)
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    excerpt TEXT,
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'article' CHECK (
        content_type IN ('article', 'video', 'audio', 'image', 'document', 'link')
    ),
    format VARCHAR(20) DEFAULT 'markdown' CHECK (format IN ('markdown', 'html', 'plaintext')),
    
    -- 作者和所有权
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID, -- 预留组织字段
    
    -- 状态管理
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'review', 'published', 'archived', 'deleted')
    ),
    visibility VARCHAR(20) DEFAULT 'public' CHECK (
        visibility IN ('public', 'private', 'unlisted', 'members_only')
    ),
    is_featured BOOLEAN DEFAULT false,
    is_sticky BOOLEAN DEFAULT false,
    is_commentable BOOLEAN DEFAULT true,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    tags TEXT[], -- 标签数组
    cover_image_url TEXT,
    seo_title VARCHAR(255),
    seo_description TEXT,
    seo_keywords TEXT[],
    
    -- 统计
    view_count INTEGER DEFAULT 0,
    unique_view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    
    -- 时间管理
    published_at TIMESTAMP WITH TIME ZONE,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    reading_time_minutes INTEGER,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    
    -- 约束
    CONSTRAINT chk_title_length CHECK (length(title) >= 1 AND length(title) <= 255),
    CONSTRAINT chk_slug_format CHECK (slug ~* '^[a-z0-9]+(?:-[a-z0-9]+)*$')
);

-- 内容版本历史
CREATE TABLE content_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    change_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(content_id, version_number)
);

-- 标签表
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    color VARCHAR(7), -- HEX颜色代码
    icon_url TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 内容-标签关联表
CREATE TABLE content_tags (
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (content_id, tag_id)
);

-- 分类表
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 内容-分类关联表
CREATE TABLE content_categories (
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (content_id, category_id)
);
```

#### 1.1.3 互动系统表
```sql
-- 点赞/喜欢表
CREATE TABLE likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    like_type VARCHAR(20) DEFAULT 'like' CHECK (like_type IN ('like', 'love', 'haha', 'wow', 'sad', 'angry')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, content_id)
);

-- 收藏/书签表
CREATE TABLE bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    folder VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, content_id)
);

-- 关注/粉丝关系表
CREATE TABLE follows (
    follower_id UUID REFERENCES users(id) ON DELETE CASCADE,
    following_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id),
    CONSTRAINT chk_not_self_follow CHECK (follower_id != following_id)
);

-- 评论表 (支持嵌套评论)
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    
    -- 状态管理
    status VARCHAR(20) DEFAULT 'published' CHECK (
        status IN ('pending', 'published', 'hidden', 'deleted')
    ),
    is_edited BOOLEAN DEFAULT false,
    is_pinned BOOLEAN DEFAULT false,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    
    -- 统计
    like_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    
    -- 约束
    CONSTRAINT chk_comment_content CHECK (length(content) >= 1 AND length(content) <= 5000)
);

-- 评论点赞表
CREATE TABLE comment_likes (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    comment_id UUID REFERENCES comments(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, comment_id)
);
```

#### 1.1.4 媒体管理系统表
```sql
-- 媒体文件表
CREATE TABLE media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT NOT NULL,
    storage_provider VARCHAR(50) DEFAULT 'local' CHECK (
        storage_provider IN ('local', 's3', 'minio', 'cloudinary')
    ),
    storage_bucket VARCHAR(100) DEFAULT 'default',
    
    -- 文件属性
    file_hash VARCHAR(64), -- SHA256哈希
    width INTEGER,
    height INTEGER,
    duration_seconds INTEGER, -- 视频/音频时长
    bitrate INTEGER, -- 比特率
    format VARCHAR(50),
    
    -- 元数据
    title VARCHAR(255),
    description TEXT,
    alt_text TEXT,
    caption TEXT,
    metadata JSONB DEFAULT '{}', -- EXIF, IPTC等
    tags TEXT[],
    
    -- 所有权
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    content_id UUID REFERENCES content(id) ON DELETE SET NULL,
    
    -- 状态
    is_public BOOLEAN DEFAULT true,
    is_processed BOOLEAN DEFAULT false,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    
    -- 约束
    CONSTRAINT chk_file_size CHECK (size_bytes > 0 AND size_bytes <= 10737418240) -- 最大10GB
);

-- 媒体处理任务表
CREATE TABLE media_process_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_id UUID REFERENCES media(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL CHECK (
        task_type IN ('thumbnail', 'transcode', 'optimize', 'watermark', 'extract_metadata')
    ),
    status VARCHAR(20) DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    ),
    parameters JSONB DEFAULT '{}',
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 1.1.5 通知系统表
```sql
-- 通知表
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL CHECK (
        notification_type IN (
            'content_published', 'comment_added', 'comment_replied',
            'like_received', 'follow_received', 'mention',
            'system_announcement', 'message_received'
        )
    ),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    -- 关联资源
    related_type VARCHAR(50), -- 'content', 'comment', 'user'
    related_id UUID,
    
    -- 状态
    is_read BOOLEAN DEFAULT false,
    is_archived BOOLEAN DEFAULT false,
    priority VARCHAR(20) DEFAULT 'normal' CHECK (
        priority IN ('low', 'normal', 'high', 'urgent')
    ),
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE, -- 通知过期时间
    
    -- 索引
    INDEX idx_notifications_user_unread (user_id, is_read, created_at DESC)
);

-- 消息表 (用户间私信)
CREATE TABLE messages (
    id UUID PRIMARY DEFAULT DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    sender_id UUID REFERENCES users(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    
    -- 消息类型
    message_type VARCHAR(20) DEFAULT 'text' CHECK (
        message_type IN ('text', 'image', 'file', 'audio', 'video')
    ),
    
    -- 状态
    is_delivered BOOLEAN DEFAULT false,
    is_read BOOLEAN DEFAULT false,
    is_edited BOOLEAN DEFAULT false,
    
    -- 元数据
    metadata JSONB DEFAULT '{}', -- {reactions: [], mentions: []}
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- 约束
    CONSTRAINT chk_message_content CHECK (length(content) >= 1 AND length(content) <= 10000)
);

-- 消息附件表
CREATE TABLE message_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    media_id UUID REFERENCES media(id) ON DELETE SET NULL,
    filename VARCHAR(255),
    file_size BIGINT,
    mime_type VARCHAR(100),
    storage_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 1.1.6 审计和日志表
```sql
-- 审计日志表
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    
    -- 请求信息
    ip_address INET,
    user_agent TEXT,
    request_path TEXT,
    request_method VARCHAR(10),
    request_headers JSONB,
    request_body JSONB,
    response_status INTEGER,
    response_body JSONB,
    error_message TEXT,
    error_stack TEXT,
    
    -- 性能指标
    duration_ms INTEGER,
    memory_usage_mb INTEGER,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    INDEX idx_audit_logs_user_action (user_id, action, created_at DESC),
    INDEX idx_audit_logs_resource (resource_type, resource_id, created_at DESC),
    INDEX idx_audit_logs_created_at (created_at DESC)
);

-- API请求日志表 (用于分析和监控)
CREATE TABLE api_request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    
    -- 用户信息
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    client_id VARCHAR(100), -- API客户端ID
    
    -- 请求信息
    query_params JSONB,
    request_body_size INTEGER,
    response_body_size INTEGER,
    
    -- 性能指标
    response_time_ms INTEGER NOT NULL,
    database_query_time_ms INTEGER,
    cache_hit_ratio DECIMAL(5,4),
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    INDEX idx_api_logs_endpoint_time (endpoint, created_at DESC),
    INDEX idx_api_logs_user_time (user_id, created_at DESC),
    INDEX idx_api_logs_status_time (status_code, created_at DESC)
);
```

### 1.2 索引优化策略

#### 复合索引设计
```sql
-- 用户相关索引
CREATE INDEX idx_users_email_status ON users(email, is_active, deleted_at);
CREATE INDEX idx_users_username_status ON users(username, is_active, deleted_at);
CREATE INDEX idx_users_created_at_active ON users(created_at) WHERE is_active = true AND deleted_at IS NULL;
CREATE INDEX idx_users_last_login ON users(last_login_at DESC) WHERE deleted_at IS NULL;

-- 内容相关索引
CREATE INDEX idx_content_author_status ON content(author_id, status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_status_published_at ON content(status, published_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_visibility_created ON content(visibility, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_tags_gin ON content USING gin(tags);
CREATE INDEX idx_content_slug_status ON content(slug, status) WHERE deleted_at IS NULL;

-- 全文搜索索引
CREATE INDEX idx_content_search ON content USING gin(
    to_tsvector('chinese', coalesce(title, '') || ' ' || coalesce(excerpt, '') || ' ' || coalesce(content, ''))
) WHERE deleted_at IS NULL AND status = 'published';

-- 评论相关索引
CREATE INDEX idx_comments_content_status ON comments(content_id, status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_user_created ON comments(user_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_comments_parent_created ON comments(parent_id, created_at DESC) WHERE deleted_at IS NULL AND parent_id IS NOT NULL;

-- 互动相关索引
CREATE INDEX idx_likes_content_user ON likes(content_id, user_id, created_at DESC);
CREATE INDEX idx_follows_follower ON follows(follower_id, created_at DESC);
CREATE INDEX idx_follows_following ON follows(following_id, created_at DESC);
CREATE INDEX idx_bookmarks_user_content ON bookmarks(user_id, content_id, created_at DESC);

-- 媒体相关索引
CREATE INDEX idx_media_user_created ON media(user_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_media_mimetype_size ON media(mime_type, size_bytes) WHERE deleted_at IS NULL;
CREATE INDEX idx_media_storage_path ON media(storage_path) WHERE deleted_at IS NULL;

-- 通知相关索引
CREATE INDEX idx_notifications_user_priority ON notifications(user_id, priority, created_at DESC) WHERE is_read = false;
CREATE INDEX idx_notifications_type_created ON notifications(notification_type, created_at DESC);

-- 消息相关索引
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender_recipient ON messages(sender_id, recipient_id, created_at DESC);
CREATE INDEX idx_messages_unread ON messages(recipient_id, is_read, created_at DESC) WHERE is_read = false;

-- 审计日志索引
CREATE INDEX idx_audit_logs_action_time ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_logs_user_time ON audit_logs(user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_audit_logs_ip_time ON audit_logs(ip_address, created_at DESC) WHERE ip_address IS NOT NULL;
```

### 1.3 分区策略

```sql
-- 按时间分区的大型表
-- API请求日志按月分区
CREATE TABLE api_request_logs_2026_01 PARTITION OF api_request_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE api_request_logs_2026_02 PARTITION OF api_request_logs
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- 审计日志按月分区
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- 创建分区维护函数
CREATE OR REPLACE FUNCTION create_monthly_partition(
    base_table TEXT,
    year INTEGER,
    month INTEGER
) RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_name := format('%s_%s_%s', 
        base_table, 
        year::TEXT, 
        LPAD(month::TEXT, 2, '0')
    );
    
    start_date := make_date(year, month, 1);
    end_date := start_date + INTERVAL '1 month';
    
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        partition_name, base_table, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
```

## 2. API规范设计

### 2.1 API设计原则

#### 2.1.1 RESTful API规范
```
HTTP方法规范:
- GET: 获取资源
- POST: 创建资源
- PUT: 更新完整资源
- PATCH: 部分更新资源
- DELETE: 删除资源

状态码规范:
- 200: 成功
- 201: 创建成功
- 204: 无内容
- 400: 请求错误
- 401: 未授权
- 403: 禁止访问
- 404: 资源不存在
- 422: 验证失败
- 429: 请求过多
- 500: 服务器错误
```

#### 2.1.2 API版本控制
```
路径版本控制: /api/v1/resource
Header版本控制: Accept: application/vnd.zhulinsma.v1+json
```

### 2.2 API端点详细设计

#### 2.2.1 认证API
```python
# 认证相关API
@router.post("/auth/register", status_code=201)
async def register_user(
    request: UserRegisterRequest,
    background_tasks: BackgroundTasks
):
    """用户注册"""
    pass

@router.post("/auth/login")
async def login_user(
    request: UserLoginRequest,
    response: Response
):
    """用户登录"""
    pass

@router.post("/auth/refresh")
async def refresh_token(
    request: TokenRefreshRequest
):
    """刷新访问令牌"""
    pass

@router.post("/auth/logout")
async def logout_user(
    current_user: User = Depends(get_current_user)
):
    """用户登出"""
    pass

@router.post("/auth/password/reset-request")
async def request_password_reset(
    request: PasswordResetRequest
):
    """请求密码重置"""
    pass

@router.post("/auth/password/reset")
async def reset_password(
    request: PasswordResetConfirmRequest
):
    """重置密码"""
    pass
```

#### 2.2.2 用户API
```python
# 用户管理API
@router.get("/users/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    pass

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """根据ID获取用户信息"""
    pass

@router.put("/users/me")
async def update_current_user(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """更新当前用户信息"""
    pass

@router.delete("/users/me")
async def delete_current_user(
    current_user: User = Depends(get_current_user)
):
    """删除当前用户账户"""
    pass

@router.get("/users/me/followers")
async def get_my_followers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """获取我的粉丝列表"""
    pass

@router.get("/users/me/following")
async def get_my_following(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """获取我关注的用户列表"""
    pass

@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """关注用户"""
    pass

@router.delete("/users/{user_id}/follow")
async def unfollow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """取消关注用户"""
    pass
```

#### 2.2.3 内容API
```python
# 内容管理API
@router.get("/content")
async def list_content(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    content_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    author_id: Optional[UUID] = Query(None),
    tag: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_user_optional)
):
    """获取内容列表"""
    pass

@router.post("/content", status_code=201)
async def create_content(
    request: ContentCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """创建内容"""
    pass

@router.get("/content/{content_id}")
async def get_content_by_id(
    content_id: UUID,
    current_user: User = Depends(get_current_user_optional)
):
    """根据ID获取内容"""
    pass

@router.put("/content/{content_id}")
async def update_content(
    content_id: UUID,
    request: ContentUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """更新内容"""
    pass

@router.delete("/content/{content_id}")
async def delete_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """删除内容"""
    pass

@router.post("/content/{content_id}/like")
async def like_content(
    content_id: UUID,
    like_type: str = Query("like"),
    current_user: User = Depends(get_current_user)
):
    """点赞内容"""
    pass

@router.delete("/content/{content_id}/like")
async def unlike_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """取消点赞"""
    pass

@router.post("/content/{content_id}/bookmark")
async def bookmark_content(
    content_id: UUID,
    folder: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """收藏内容"""
    pass

@router.delete("/content/{content_id}/bookmark")
async def unbookmark_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """取消收藏"""
    pass

@router.get("/content/{content_id}/comments")
async def get_content_comments(
    content_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_user_optional)
):
    """获取内容的评论列表"""
    pass
```

#### 2.2.4 评论API
```python
# 评论管理API
@router.post("/content/{content_id}/comments", status_code=201)
async def create_comment(
    content_id: UUID,
    request: CommentCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """创建评论"""
    pass

@router.get("/comments/{comment_id}")
async def get_comment_by_id(
    comment_id: UUID,
    current_user: User = Depends(get_current_user_optional)
):
    """根据ID获取评论"""
    pass

@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: UUID,
    request: CommentUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """更新评论"""
    pass

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """删除评论"""
    pass

@router.post("/comments/{comment_id}/like")
async def like_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """点赞评论"""
    pass

@router.delete("/comments/{comment_id}/like")
async def unlike_comment(
    comment_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """取消点赞评论"""
    pass

@router.get("/comments/{comment_id}/replies")
async def get_comment_replies(
    comment_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional)
):
    """获取评论的回复列表"""
    pass
```

#### 2.2.5 媒体API
```python
# 媒体管理API
@router.post("/media/upload", status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    alt_text: Optional[str] = Form(None),
    is_public: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """上传媒体文件"""
    pass

@router.get("/media/{media_id}")
async def get_media_by_id(
    media_id: UUID,
    current_user: User = Depends(get_current_user_optional)
):
    """根据ID获取媒体信息"""
    pass

@router.get("/media/{media_id}/url")
async def get_media_url(
    media_id: UUID,
    width: Optional[int] = Query(None),
    height: Optional[int] = Query(None),
    quality: Optional[int] = Query(None),
    format: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_optional)
):
    """获取媒体访问URL"""
    pass

@router.delete("/media/{media_id}")
async def delete_media(
    media_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """删除媒体文件"""
    pass

@router.get("/media")
async def list_user_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    media_type: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_user)
):
    """获取用户的媒体列表"""
    pass
```

#### 2.2.6 通知API
```python
# 通知管理API
@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """获取通知列表"""
    pass

@router.get("/notifications/unread-count")
async def get_unread_notification_count(
    current_user: User = Depends(get_current_user)
):
    """获取未读通知数量"""
    pass

@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """标记通知为已读"""
    pass

@router.put("/notifications/read-all")
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user)
):
    """标记所有通知为已读"""
    pass

@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """删除通知"""
    pass
```

#### 2.2.7 搜索API
```python
# 搜索API
@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    type: Optional[str] = Query(None),  # content, user, tag
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("relevance"),
    current_user: User = Depends(get_current_user_optional)
):
    """全局搜索"""
    pass

@router.get("/search/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=50),
    type: Optional[str] = Query(None),  # content, user, tag
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user_optional)
):
    """搜索自动补全"""
    pass
```

### 2.3 API请求/响应格式

#### 2.3.1 标准响应格式
```python
# 成功响应
{
    "success": true,
    "data": {
        // 实际数据
    },
    "meta": {
        "timestamp": "2026-04-09T21:30:00Z",
        "request_id": "req_123456789",
        "version": "1.0"
    }
}

# 分页响应
{
    "success": true,
    "data": [...],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total_items": 150,
        "total_pages": 8,
        "has_next": true,
        "has_previous": false
    },
    "meta": {
        "timestamp": "2026-04-09T21:30:00Z"
    }
}

# 错误响应
{
    "success": false,
    "error": {
        "code": "USER_NOT_FOUND",
        "message": "用户不存在",
        "details": "找不到ID为123的用户",
        "field_errors": [
            {
                "field": "email",
                "message": "邮箱格式不正确"
            }
        ]
    },
    "meta": {
        "timestamp": "2026-04-09T21:30:00Z",
        "request_id": "req_123456789"
    }
}
```

#### 2.3.2 查询参数规范
```
标准查询参数:
- page: 页码 (默认1)
- page_size: 每页数量 (默认20, 最大100)
- sort_by: 排序字段 (默认created_at)
- sort_order: 排序方向 (asc/desc, 默认desc)

过滤参数:
- status: 状态过滤
- type: 类型过滤
- author_id: 作者过滤
- created_at_after: 创建时间之后
- created_at_before: 创建时间之前

搜索参数:
- q: 搜索关键词
- search_fields: 搜索字段
```

### 2.4 API安全规范

#### 2.4.1 认证机制
```python
# JWT认证配置
JWT_CONFIG = {
    "algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "issuer": "zhulinsma.com",
    "audience": ["zhulinsma-web", "zhulinsma-mobile"]
}

# API密钥认证
API_KEY_CONFIG = {
    "header_name": "X-API-Key",
    "query_param": "api_key",
    "rate_limit_per_key": 1000  # 每分钟请求限制
}
```

#### 2.4.2 速率限制
```python
# 基于用户和端点的速率限制
RATE_LIMIT_CONFIG = {
    "default": {
        "limit": 100,  # 每分钟请求数
        "period": 60   # 秒
    },
    "auth": {
        "limit": 10,   # 登录接口更严格的限制
        "period": 60
    },
    "upload": {
        "limit": 20,   # 上传接口限制
        "period": 300  # 5分钟
    }
}
```

#### 2.4.3 输入验证
```python
# Pydantic模型验证示例
from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional

class UserRegisterRequest(BaseModel):
    username: constr(min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: constr(min_length=8, max_length=100)
    full_name: Optional[constr(max_length=100)]
    
    @validator('password')
    def validate_password_strength(cls, v):
        # 密码强度验证
        if len(v) < 8:
            raise ValueError('密码至少8个字符')
        if not any(c.isupper() for c in v):
            raise ValueError('密码必须包含大写字母')
        if not any(c.isdigit() for c in v):
            raise ValueError('密码必须包含数字')
        return v

class ContentCreateRequest(BaseModel):
    title: constr(min_length=1, max_length=255)
    content: constr(min_length=1, max_length=50000)
    content_type: constr(regex=r'^(article|video|audio|image|document|link)$')
    status: Optional[constr(regex=r'^(draft|review|published|archived)$')] = 'draft'
    visibility: Optional[constr(regex=r'^(public|private|unlisted|members_only)$')] = 'public'
    tags: Optional[list[str]] = []
    metadata: Optional[dict] = {}
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError('最多只能添加10个标签')
        return v
```

## 3. API文档规范

### 3.1 OpenAPI/Swagger文档
```python
# FastAPI自动生成API文档配置
app = FastAPI(
    title="竹林司马后端API",
    description="竹林司马内容管理系统的后端API接口",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    
    # 安全定义
    openapi_tags=[
        {
            "name": "auth",
            "description": "用户认证相关接口"
        },
        {
            "name": "users",
            "description": "用户管理接口"
        },
        {
            "name": "content",
            "description": "内容管理接口"
        },
        {
            "name": "comments",
            "description": "评论管理接口"
        },
        {
            "name": "media",
            "description": "媒体管理接口"
        },
        {
            "name": "notifications",
            "description": "通知管理接口"
        }
    ]
)

# 安全方案定义
components={
    "securitySchemes": {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
}
```

### 3.2 API端点文档示例
```python
@app.post("/api/v1/auth/login", 
    response_model=TokenResponse,
    status_code=200,
    summary="用户登录",
    description="用户使用邮箱/用户名和密码登录系统，获取访问令牌",
    tags=["auth"]
)
async def login_user(
    request: UserLoginRequest,
    response: Response
):
    """
    用户登录接口
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    
    返回:
    - **access_token**: 访问令牌
    - **refresh_token**: 刷新令牌
    - **token_type**: 令牌类型 (bearer)
    - **expires_in**: 过期时间(秒)
    """
    pass
```

## 4. 数据库迁移策略

### 4.1 Alembic迁移配置
```python
# alembic.ini 配置
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@localhost/zhulinsma
prepend_sys_path = .
version_path_separator = os

# 日志配置
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 4.2 迁移文件示例
```python
# migrations/versions/001_initial_schema.py
"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2026-04-09 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 创建users表
    op.create_table('users',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        # ... 其他字段
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_username', 'users', ['username'], unique=True)
    
    # 创建其他表...

def downgrade():
    # 删除所有表
    op.drop_table('users')
    # ... 删除其他表
```

## 5. 性能优化建议

### 5.1 数据库查询优化
```python
# 使用SELECT ... FOR UPDATE NOWAIT避免死锁
async def update_user_balance(user_id: UUID, amount: Decimal):
    async with async_session() as session:
        # 锁定用户行
        user = await session.execute(
            select(User).where(User.id == user_id).with_for_update(nowait=True)
        )
        user = user.scalar_one()
        
        # 更新余额
        user.balance += amount
        await session.commit()

# 使用CTE优化复杂查询
async def get_user_with_stats(user_id: UUID):
    query = """
    WITH user_stats AS (
        SELECT 
            u.*,
            COUNT(DISTINCT c.id) as content_count,
            COUNT(DISTINCT f.follower_id) as follower_count
        FROM users u
        LEFT JOIN content c ON c.author_id = u.id
        LEFT JOIN follows f ON f.following_id = u.id
        WHERE u.id = :user_id
        GROUP BY u.id
    )
    SELECT * FROM user_stats
    """
    
    result = await session.execute(text(query), {"user_id": user_id})
    return result.fetchone()
```

### 5.2 缓存策略优化
```python
# 多级缓存策略
class ContentCache:
    def __init__(self):
        self.local_cache = TTLCache(maxsize=1000, ttl=300)  # 5分钟本地缓存
        self.redis_cache = redis.Redis()
        
    async def get_content(self, content_id: UUID) -> Optional[Content]:
        # 1. 检查本地缓存
        cache_key = f"content:{content_id}"
        if cache_key in self.local_cache:
            return self.local_cache[cache_key]
        
        # 2. 检查Redis缓存
        cached_data = await self.redis_cache.get(cache_key)
        if cached_data:
            content = Content.parse_raw(cached_data)
            self.local_cache[cache_key] = content
            return content
        
        # 3. 从数据库获取
        content = await self.get_content_from_db(content_id)
        if content:
            # 缓存到Redis (1小时过期)
            await self.redis_cache.setex(
                cache_key, 
                3600, 
                content.json()
            )
            # 缓存到本地内存
            self.local_cache[cache_key] = content
        
        return content
```

这个数据库架构和API规范设计为竹林司马后端系统提供了**完整、可扩展、高性能**的基础设施，能够满足业务增长和技术演进的需求。