#!/usr/bin/env python3
"""
后端服务启动脚本
用于启动和验证竹林司马后端程序
"""

import subprocess
import sys
import os
import time
import signal
import requests
import json
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """简单的健康检查HTTP处理器"""
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "service": "zhulin-sima-backend",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


def start_health_check_server(port=9999):
    """启动健康检查服务器"""
    server = HTTPServer(('localhost', port), HealthCheckHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def check_server_health(base_url="http://localhost:8000", timeout=30):
    """检查服务器健康状态"""
    print(f"检查服务器健康状态: {base_url}")
    
    endpoints = [
        ("/", "根路径"),
        ("/health", "健康检查"),
        ("/info", "系统信息"),
        ("/api/v1/auth/login", "认证API"),
        ("/api/docs", "Swagger文档"),
        ("/api/redoc", "ReDoc文档"),
    ]
    
    results = []
    
    for endpoint, description in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            start_time = time.time()
            response = requests.get(url, timeout=5, allow_redirects=True)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                status = "✅ 正常"
            elif response.status_code in [401, 403]:
                status = "⚠️ 需要认证"
            else:
                status = f"❌ 异常 (HTTP {response.status_code})"
            
            results.append({
                "endpoint": endpoint,
                "description": description,
                "status": status,
                "response_time": f"{elapsed:.2f}s",
                "status_code": response.status_code
            })
            
            print(f"  {endpoint:25} {description:20} {status:20} {elapsed:.2f}s")
            
        except requests.exceptions.RequestException as e:
            results.append({
                "endpoint": endpoint,
                "description": description,
                "status": f"❌ 无法连接: {str(e)[:50]}",
                "response_time": "N/A",
                "status_code": None
            })
            print(f"  {endpoint:25} {description:20} ❌ 无法连接")
    
    return results


def test_api_endpoints(base_url="http://localhost:8000"):
    """测试API端点"""
    print("\n" + "="*60)
    print("测试API端点")
    print("="*60)
    
    tests = []
    
    # 测试1: 根路径
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tests.append(("根路径", "✅", f"应用: {data.get('app', 'N/A')}"))
        else:
            tests.append(("根路径", "❌", f"HTTP {response.status_code}"))
    except Exception as e:
        tests.append(("根路径", "❌", f"错误: {str(e)[:50]}"))
    
    # 测试2: 健康检查
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code in [200, 503]:  # 503表示有组件不正常但API正常
            data = response.json()
            tests.append(("健康检查", "✅", f"状态: {data.get('status', 'N/A')}"))
        else:
            tests.append(("健康检查", "❌", f"HTTP {response.status_code}"))
    except Exception as e:
        tests.append(("健康检查", "❌", f"错误: {str(e)[:50]}"))
    
    # 测试3: 系统信息
    try:
        response = requests.get(f"{base_url}/info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tests.append(("系统信息", "✅", f"版本: {data.get('app', {}).get('version', 'N/A')}"))
        else:
            tests.append(("系统信息", "❌", f"HTTP {response.status_code}"))
    except Exception as e:
        tests.append(("系统信息", "❌", f"错误: {str(e)[:50]}"))
    
    # 测试4: API文档
    try:
        response = requests.get(f"{base_url}/api/docs", timeout=5, allow_redirects=True)
        if response.status_code == 200:
            tests.append(("Swagger文档", "✅", "文档可访问"))
        else:
            tests.append(("Swagger文档", "⚠️", f"HTTP {response.status_code}"))
    except Exception as e:
        tests.append(("Swagger文档", "❌", f"错误: {str(e)[:50]}"))
    
    # 测试5: OpenAPI JSON
    try:
        response = requests.get(f"{base_url}/api/openapi.json", timeout=5)
        if response.status_code == 200:
            data = response.json()
            api_count = len(data.get('paths', {}))
            tests.append(("OpenAPI定义", "✅", f"{api_count}个API端点"))
        else:
            tests.append(("OpenAPI定义", "⚠️", f"HTTP {response.status_code}"))
    except Exception as e:
        tests.append(("OpenAPI定义", "❌", f"错误: {str(e)[:50]}"))
    
    # 输出结果
    for test_name, status, message in tests:
        print(f"{test_name:20} {status:5} {message}")
    
    return all(status == "✅" for _, status, _ in tests)


def start_server():
    """启动后端服务器"""
    print("="*60)
    print("启动竹林司马后端服务器")
    print("="*60)
    
    # 检查Python环境
    python_exe = sys.executable
    print(f"使用Python: {python_exe}")
    
    # 检查依赖
    try:
        import uvicorn
        import fastapi
        import sqlalchemy
        print("✅ 核心依赖检查通过")
    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    # 启动服务器进程
    cmd = [
        python_exe, "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    print(f"启动命令: {' '.join(cmd)}")
    print(f"服务器将在 http://localhost:8000 启动")
    print(f"API文档: http://localhost:8000/api/docs")
    print("按 Ctrl+C 停止服务器")
    print("-" * 60)
    
    try:
        # 启动服务器
        process = subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 等待服务器启动
        print("等待服务器启动...")
        time.sleep(3)
        
        # 检查服务器是否运行
        try:
            response = requests.get("http://localhost:8000/", timeout=2)
            if response.status_code == 200:
                print("✅ 服务器启动成功")
                
                # 测试API端点
                api_ok = test_api_endpoints()
                
                if api_ok:
                    print("\n🎉 后端程序验证成功！")
                    print("所有核心功能正常工作。")
                else:
                    print("\n⚠️  部分API端点存在问题，但服务器已启动。")
                
                print("\n服务器日志:")
                print("-" * 60)
                
                # 输出服务器日志
                try:
                    for line in iter(process.stdout.readline, ''):
                        print(line.rstrip())
                except KeyboardInterrupt:
                    print("\n正在停止服务器...")
                    process.terminate()
                    process.wait()
                    print("服务器已停止")
                    
            else:
                print(f"❌ 服务器响应异常: HTTP {response.status_code}")
                process.terminate()
                return False
                
        except requests.exceptions.RequestException:
            print("❌ 无法连接到服务器")
            process.terminate()
            return False
            
    except Exception as e:
        print(f"❌ 启动服务器失败: {e}")
        return False
    
    return True


def quick_test():
    """快速测试"""
    print("="*60)
    print("快速验证后端程序")
    print("="*60)
    
    # 测试1: 导入检查
    print("1. 导入检查...")
    try:
        from src.core.config import settings
        from src.core.database import Database
        print(f"   ✅ 配置加载: {settings.PROJECT_NAME}")
        print(f"   ✅ 数据库模块: OK")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False
    
    # 测试2: 配置文件检查
    print("2. 配置文件检查...")
    try:
        print(f"   项目名称: {settings.PROJECT_NAME}")
        print(f"   版本: {settings.VERSION}")
        print(f"   环境: {'开发' if settings.DEBUG else '生产'}")
        print(f"   数据库URL: {'已配置' if settings.DATABASE_URL else '未配置'}")
        print(f"   API前缀: {settings.API_V1_PREFIX}")
        print("   ✅ 配置检查通过")
    except Exception as e:
        print(f"   ❌ 配置检查失败: {e}")
        return False
    
    # 测试3: 代码语法检查
    print("3. 代码语法检查...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "main.py"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("   ✅ 主程序语法检查通过")
        else:
            print(f"   ❌ 语法错误: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ 语法检查失败: {e}")
        return False
    
    print("\n✅ 所有快速检查通过！")
    print("可以启动后端服务器进行完整验证。")
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="竹林司马后端程序验证工具")
    parser.add_argument("--quick", action="store_true", help="仅运行快速检查")
    parser.add_argument("--start", action="store_true", help="启动服务器并验证")
    parser.add_argument("--test", action="store_true", help="测试已运行的服务器")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    
    args = parser.parse_args()
    
    # 如果没有指定任何参数，默认运行快速检查
    if not any([args.quick, args.start, args.test]):
        args.quick = True
    
    if args.quick:
        success = quick_test()
        if success:
            print("\n建议运行 --start 启动服务器进行完整验证。")
        return 0 if success else 1
    
    if args.test:
        print(f"测试运行在端口 {args.port} 的服务器...")
        base_url = f"http://localhost:{args.port}"
        try:
            response = requests.get(f"{base_url}/", timeout=2)
            if response.status_code == 200:
                print("✅ 服务器正在运行")
                test_api_endpoints(base_url)
            else:
                print(f"❌ 服务器响应异常: HTTP {response.status_code}")
                return 1
        except requests.exceptions.RequestException:
            print("❌ 无法连接到服务器")
            print("请确保服务器正在运行，或使用 --start 启动服务器。")
            return 1
    
    if args.start:
        return 0 if start_server() else 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())