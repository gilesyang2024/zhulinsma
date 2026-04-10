"""OpenAPI/Swagger配置增强"""
from typing import Dict, Any
from src.core.config import get_settings

settings = get_settings()


def get_openapi_config() -> Dict[str, Any]:
    """生成OpenAPI配置"""
    return {
        "title": f"{settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "description": f"""
# {settings.PROJECT_NAME} 后端API文档

## 项目简介
{settings.PROJECT_NAME}是一个完整的后端服务平台，提供用户管理、内容管理、媒体管理和系统管理等功能。

## 主要功能
- 👤 **用户管理**: 注册、登录、权限控制
- 📝 **内容管理**: 文章、评论、标签、分类
- 📁 **媒体管理**: 文件上传、下载、处理
- 🛠️ **管理后台**: 系统监控、内容审核、用户管理

## 认证方式
系统使用JWT（JSON Web Tokens）进行认证。

### 获取令牌
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{{"username": "admin", "password": "password"}}'
```

### 使用令牌
```
Authorization: Bearer {your_jwt_token}
```

## API状态码
| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 资源创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 422 | 验证错误 |
| 500 | 服务器错误 |

## 快速开始
1. 注册用户 `/api/v1/users/register`
2. 登录获取令牌 `/api/v1/auth/login`
3. 使用令牌访问受保护API

## 环境
- **开发环境**: http://localhost:8000
- **生产环境**: {settings.SERVER_HOST}

## 技术支持
- GitHub: https://github.com/yourusername/zhulin-sima-backend
- 问题反馈: https://github.com/yourusername/zhulin-sima-backend/issues
        """,
        "terms_of_service": "https://example.com/terms/",
        "contact": {
            "name": "竹林司马开发团队",
            "url": "https://github.com/yourusername/zhulin-sima-backend",
            "email": "support@example.com",
        },
        "license_info": {
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        "servers": [
            {
                "url": "http://localhost:8000",
                "description": "开发服务器"
            },
            {
                "url": settings.SERVER_HOST,
                "description": "生产服务器"
            }
        ],
        "externalDocs": {
            "description": "完整使用指南",
            "url": f"{settings.SERVER_HOST}/docs/api-guide"
        },
        "tags": [
            {
                "name": "认证",
                "description": "用户登录、注册、令牌管理"
            },
            {
                "name": "用户",
                "description": "用户管理、个人信息、权限控制"
            },
            {
                "name": "内容",
                "description": "内容管理、评论、标签、分类"
            },
            {
                "name": "媒体",
                "description": "文件上传、下载、媒体处理"
            },
            {
                "name": "管理后台",
                "description": "系统监控、审核、管理功能"
            }
        ],
        "security": [
            {
                "BearerAuth": []
            }
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "输入你的JWT令牌，格式: Bearer <token>"
                }
            },
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "integer",
                            "example": 400
                        },
                        "message": {
                            "type": "string",
                            "example": "请求参数错误"
                        },
                        "detail": {
                            "type": "string",
                            "example": "详细的错误信息"
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time",
                            "example": "2026-04-10T10:30:00Z"
                        },
                        "request_id": {
                            "type": "string",
                            "example": "req_1234567890"
                        }
                    }
                },
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "integer",
                            "example": 200
                        },
                        "message": {
                            "type": "string",
                            "example": "操作成功"
                        },
                        "data": {
                            "type": "object",
                            "description": "响应数据"
                        }
                    }
                }
            },
            "responses": {
                "SuccessResponse": {
                    "description": "成功响应",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/SuccessResponse"
                            }
                        }
                    }
                },
                "ErrorResponse": {
                    "description": "错误响应",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ErrorResponse"
                            }
                        }
                    }
                },
                "UnauthorizedError": {
                    "description": "未认证或令牌无效",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ErrorResponse"
                            },
                            "example": {
                                "code": 401,
                                "message": "认证失败",
                                "detail": "无效的JWT令牌或令牌已过期"
                            }
                        }
                    }
                },
                "ForbiddenError": {
                    "description": "权限不足",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ErrorResponse"
                            },
                            "example": {
                                "code": 403,
                                "message": "权限不足",
                                "detail": "当前用户没有执行此操作的权限"
                            }
                        }
                    }
                },
                "NotFoundError": {
                    "description": "资源不存在",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ErrorResponse"
                            },
                            "example": {
                                "code": 404,
                                "message": "资源不存在",
                                "detail": "请求的资源ID不存在"
                            }
                        }
                    }
                },
                "ValidationError": {
                    "description": "请求参数验证失败",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ErrorResponse"
                            },
                            "example": {
                                "code": 422,
                                "message": "验证错误",
                                "detail": "请求参数不符合要求"
                            }
                        }
                    }
                }
            }
        }
    }


def get_redoc_config() -> Dict[str, Any]:
    """生成ReDoc配置"""
    return {
        "title": f"{settings.PROJECT_NAME} API - ReDoc",
        "theme": {
            "typography": {
                "fontFamily": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                "fontSize": "14px",
                "lineHeight": "1.5",
                "code": {
                    "fontFamily": "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                    "fontSize": "12px",
                    "backgroundColor": "#f5f5f5",
                    "color": "#d14"
                }
            },
            "sidebar": {
                "backgroundColor": "#f8f9fa",
                "width": "260px"
            },
            "rightPanel": {
                "backgroundColor": "#fafbfc",
                "width": "40%"
            },
            "colors": {
                "primary": {
                    "main": "#1890ff"
                },
                "success": {
                    "main": "#52c41a"
                },
                "warning": {
                    "main": "#faad14"
                },
                "error": {
                    "main": "#f5222d"
                },
                "text": {
                    "primary": "#262626",
                    "secondary": "#595959"
                },
                "border": {
                    "light": "#f0f0f0",
                    "dark": "#d9d9d9"
                },
                "http": {
                    "get": "#52c41a",
                    "post": "#1890ff",
                    "put": "#faad14",
                    "delete": "#f5222d",
                    "patch": "#722ed1"
                }
            },
            "schema": {
                "linesColor": "#8c8c8c",
                "defaultDetailsWidth": "70%",
                "typeNameColor": "#595959",
                "typeTitleColor": "#262626",
                "requireLabelColor": "#f5222d",
                "labelsTextSize": "12px",
                " nestingSpacing": "16px"
            },
            "codeBlock": {
                "backgroundColor": "#f5f5f5"
            }
        },
        "hideDownloadButton": False,
        "hideHostname": False,
        "expandResponses": "200,201",
        "requiredPropsFirst": True,
        "sortPropsAlphabetically": False,
        "showExtensions": True,
        "noAutoAuth": False,
        "pathInMiddlePanel": True,
        "nativeScrollbars": False,
        "disableSearch": False,
        "onlyRequiredInSamples": False,
        "hideLoading": False
    }


def customize_openapi_schema(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """自定义OpenAPI schema"""
    
    # 添加认证信息到每个需要认证的路径
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            # 如果路径包含auth，跳过
            if "auth" in path:
                continue
                
            # 为需要认证的路径添加安全要求
            if path not in ["/api/v1/auth/login", "/api/v1/users/register"]:
                if "post" in method or "put" in method or "delete" in method:
                    operation["security"] = [{"BearerAuth": []}]
                elif method == "get":
                    # GET请求可能也需要认证（如获取个人信息）
                    if any(keyword in path for keyword in ["/me", "/admin", "/media/upload"]):
                        operation["security"] = [{"BearerAuth": []}]
    
    # 添加通用响应
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            responses = operation.get("responses", {})
            
            # 为所有操作添加错误响应
            if "401" not in responses:
                responses["401"] = {"$ref": "#/components/responses/UnauthorizedError"}
            if "403" not in responses:
                responses["403"] = {"$ref": "#/components/responses/ForbiddenError"}
            if "422" not in responses:
                responses["422"] = {"$ref": "#/components/responses/ValidationError"}
            if "500" not in responses:
                responses["500"] = {"$ref": "#/components/responses/ErrorResponse"}
                
            operation["responses"] = responses
    
    return openapi_schema


def get_api_tags() -> list:
    """获取API标签配置"""
    return [
        {
            "name": "认证",
            "description": "用户登录、注册、令牌管理",
            "externalDocs": {
                "description": "详细认证文档",
                "url": f"{settings.SERVER_HOST}/docs/auth-guide"
            }
        },
        {
            "name": "用户",
            "description": "用户管理、个人信息、权限控制",
            "externalDocs": {
                "description": "用户管理指南",
                "url": f"{settings.SERVER_HOST}/docs/user-guide"
            }
        },
        {
            "name": "内容",
            "description": "内容管理、评论、标签、分类",
            "externalDocs": {
                "description": "内容管理指南",
                "url": f"{settings.SERVER_HOST}/docs/content-guide"
            }
        },
        {
            "name": "媒体",
            "description": "文件上传、下载、媒体处理",
            "externalDocs": {
                "description": "媒体管理指南",
                "url": f"{settings.SERVER_HOST}/docs/media-guide"
            }
        },
        {
            "name": "管理后台",
            "description": "系统监控、审核、管理功能",
            "externalDocs": {
                "description": "管理后台指南",
                "url": f"{settings.SERVER_HOST}/docs/admin-guide"
            }
        }
    ]