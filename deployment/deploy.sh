#!/bin/bash

# 竹林司马应用部署脚本
# 支持开发、测试和生产环境部署

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
竹林司马应用部署脚本

使用方法: ./deploy.sh [选项] [环境]

选项:
  -h, --help          显示帮助信息
  -e, --env ENV       部署环境 (dev/staging/prod)
  -b, --branch BRANCH 要部署的分支
  -t, --tag TAG       要部署的标签版本
  --skip-tests        跳过测试
  --skip-lint         跳过代码检查
  --build-only        只构建不部署
  --deploy-only       只部署不构建
  --rollback          回滚到上一个版本

示例:
  ./deploy.sh -e dev              # 部署开发环境
  ./deploy.sh -e staging          # 部署测试环境
  ./deploy.sh -e prod             # 部署生产环境
  ./deploy.sh -e prod --tag v1.2.3 # 部署特定版本
  ./deploy.sh --rollback          # 回滚到上一个版本
EOF
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    required_commands=("docker" "docker-compose" "git" "python3" "curl")
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "缺少依赖: $cmd"
            exit 1
        fi
    done
    
    log_success "所有依赖已安装"
}

# 检查Docker服务
check_docker() {
    log_info "检查Docker服务状态..."
    
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行"
        exit 1
    fi
    
    log_success "Docker服务正常运行"
}

# 检查Git状态
check_git() {
    log_info "检查Git状态..."
    
    if ! git status &> /dev/null; then
        log_error "不是有效的Git仓库"
        exit 1
    fi
    
    local current_branch
    current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")
    log_info "当前分支: $current_branch"
    
    log_success "Git状态正常"
}

# 环境变量验证
validate_environment() {
    local env="$1"
    
    log_info "验证环境变量..."
    
    case "$env" in
        dev)
            if [[ -z "$DEV_DATABASE_URL" ]]; then
                log_warning "DEV_DATABASE_URL未设置，使用默认值"
                export DATABASE_URL="postgresql://postgres:password@localhost:5432/zhulinsma_dev"
            fi
            ;;
        staging)
            if [[ -z "$STAGING_DATABASE_URL" ]]; then
                log_error "STAGING_DATABASE_URL必须设置"
                exit 1
            fi
            ;;
        prod)
            if [[ -z "$PROD_DATABASE_URL" ]]; then
                log_error "PROD_DATABASE_URL必须设置"
                exit 1
            fi
            ;;
    esac
    
    # 加载环境文件
    if [[ -f ".env.$env" ]]; then
        source ".env.$env"
        log_info "已加载环境文件: .env.$env"
    elif [[ -f ".env" ]]; then
        source ".env"
        log_info "已加载环境文件: .env"
    else
        log_warning "未找到环境文件，使用默认配置"
    fi
    
    log_success "环境变量验证完成"
}

# 代码检查
run_lint() {
    if [[ "$SKIP_LINT" == "true" ]]; then
        log_info "跳过代码检查"
        return 0
    fi
    
    log_info "运行代码检查..."
    
    # 检查Python代码质量
    if ! flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics; then
        log_error "代码检查失败：发现严重错误"
        exit 1
    fi
    
    if ! black --check src/; then
        log_warning "代码格式化检查失败，请运行 black src/ 格式化代码"
    fi
    
    if ! isort --check-only --profile black src/; then
        log_warning "导入排序检查失败，请运行 isort src/ 排序导入"
    fi
    
    log_success "代码检查完成"
}

# 运行测试
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_info "跳过测试"
        return 0
    fi
    
    log_info "运行测试..."
    
    # 启动测试数据库
    if [[ "$DEPLOY_ENV" != "prod" ]]; then
        log_info "启动测试数据库服务..."
        docker-compose -f docker-compose.test.yml up -d
        
        # 等待数据库就绪
        sleep 10
    fi
    
    # 运行单元测试
    if ! python -m pytest tests/ -v --cov=src --cov-report=xml --cov-report=html; then
        log_error "测试失败"
        
        # 清理测试服务
        if [[ "$DEPLOY_ENV" != "prod" ]]; then
            docker-compose -f docker-compose.test.yml down
        fi
        
        exit 1
    fi
    
    # 清理测试服务
    if [[ "$DEPLOY_ENV" != "prod" ]]; then
        docker-compose -f docker-compose.test.yml down
    fi
    
    log_success "所有测试通过"
}

# 构建Docker镜像
build_docker() {
    if [[ "$DEPLOY_ONLY" == "true" ]]; then
        log_info "跳过构建，直接部署"
        return 0
    fi
    
    log_info "构建Docker镜像..."
    
    local build_args=""
    local build_target="runtime"
    
    case "$DEPLOY_ENV" in
        prod)
            build_args="--build-arg APP_ENV=production"
            build_target="runtime"
            ;;
        staging)
            build_args="--build-arg APP_ENV=staging"
            build_target="runtime"
            ;;
        dev)
            build_target="builder"
            ;;
    esac
    
    # 如果有指定标签，使用标签构建
    if [[ -n "$DEPLOY_TAG" ]]; then
        IMAGE_TAG="$DEPLOY_TAG"
    elif [[ -n "$DEPLOY_BRANCH" ]]; then
        IMAGE_TAG="$DEPLOY_BRANCH-$(git rev-parse --short HEAD)"
    else
        IMAGE_TAG="latest"
    fi
    
    # 构建镜像
    if ! docker build \
        -f deployment/Dockerfile \
        $build_args \
        --target "$build_target" \
        -t "zhulinsma:$IMAGE_TAG" \
        -t "zhulinsma:latest" \
        .; then
        log_error "Docker构建失败"
        exit 1
    fi
    
    log_success "Docker镜像构建完成: zhulinsma:$IMAGE_TAG"
}

# 部署应用
deploy_app() {
    if [[ "$BUILD_ONLY" == "true" ]]; then
        log_info "只构建不部署"
        return 0
    fi
    
    log_info "开始部署应用..."
    
    # 选择Docker Compose文件
    local compose_file="docker-compose.yml"
    
    case "$DEPLOY_ENV" in
        prod)
            compose_file="deployment/docker-compose.prod.yml"
            ;;
        staging)
            compose_file="deployment/docker-compose.yml"
            export APP_ENV=staging
            ;;
        dev)
            compose_file="deployment/docker-compose.dev.yml"
            export APP_ENV=development
            ;;
    esac
    
    # 停止现有服务
    log_info "停止现有服务..."
    docker-compose -f "$compose_file" down || true
    
    # 启动服务
    log_info "启动服务..."
    if ! docker-compose -f "$compose_file" up -d --build; then
        log_error "服务启动失败"
        exit 1
    fi
    
    # 等待服务就绪
    log_info "等待服务就绪..."
    sleep 30
    
    # 检查服务健康状态
    if ! curl -f http://localhost:8000/health; then
        log_error "服务健康检查失败"
        docker-compose -f "$compose_file" logs app
        exit 1
    fi
    
    log_success "应用部署成功！"
    
    # 显示部署信息
    show_deployment_info
}

# 回滚部署
rollback() {
    log_info "开始回滚部署..."
    
    # 检查是否有备份镜像
    if ! docker images | grep -q "zhulinsma:previous"; then
        log_error "没有找到可回滚的镜像"
        exit 1
    fi
    
    # 停止当前服务
    docker-compose down || true
    
    # 回滚到上一个版本
    docker tag zhulinsma:previous zhulinsma:latest
    docker-compose up -d
    
    log_success "已回滚到上一个版本"
    
    # 健康检查
    sleep 10
    if curl -f http://localhost:8000/health; then
        log_success "回滚完成，服务正常运行"
    else
        log_error "回滚后服务健康检查失败"
        exit 1
    fi
}

# 备份当前版本
backup_current() {
    log_info "备份当前版本..."
    
    if docker images | grep -q "zhulinsma:latest"; then
        docker tag zhulinsma:latest zhulinsma:previous
        log_success "当前版本已备份为 zhulinsma:previous"
    fi
}

# 清理旧镜像
cleanup_images() {
    log_info "清理旧的Docker镜像..."
    
    # 保留最近5个镜像
    docker images "zhulinsma:*" --format "{{.ID}} {{.Tag}}" | \
        grep -v "latest" | grep -v "previous" | \
        sort -k2 -r | tail -n +6 | awk '{print $1}' | \
        xargs -r docker rmi -f 2>/dev/null || true
    
    # 清理悬挂镜像
    docker image prune -f
    
    log_success "镜像清理完成"
}

# 显示部署信息
show_deployment_info() {
    local ip_address
    ip_address=$(hostname -I | awk '{print $1}')
    
    cat << EOF

${GREEN}=== 部署完成 ===${NC}

应用名称: 竹林司马
部署环境: $DEPLOY_ENV
版本标签: ${IMAGE_TAG:-latest}
部署时间: $(date)

${BLUE}访问信息:${NC}
API地址: http://$ip_address:8000
API文档: http://$ip_address:8000/docs
健康检查: http://$ip_address:8000/health
监控面板: http://$ip_address:3000 (如果启用)

${YELLOW}常用命令:${NC}
查看日志: docker-compose -f $compose_file logs -f
停止服务: docker-compose -f $compose_file down
重启服务: docker-compose -f $compose_file restart
进入容器: docker exec -it zhulinsma-app bash

${GREEN}部署成功！${NC}
EOF
}

# 主函数
main() {
    # 默认值
    DEPLOY_ENV="dev"
    DEPLOY_BRANCH=""
    DEPLOY_TAG=""
    SKIP_TESTS="false"
    SKIP_LINT="false"
    BUILD_ONLY="false"
    DEPLOY_ONLY="false"
    ROLLBACK="false"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -e|--env)
                DEPLOY_ENV="$2"
                shift 2
                ;;
            -b|--branch)
                DEPLOY_BRANCH="$2"
                shift 2
                ;;
            -t|--tag)
                DEPLOY_TAG="$2"
                shift 2
                ;;
            --skip-tests)
                SKIP_TESTS="true"
                shift
                ;;
            --skip-lint)
                SKIP_LINT="true"
                shift
                ;;
            --build-only)
                BUILD_ONLY="true"
                shift
                ;;
            --deploy-only)
                DEPLOY_ONLY="true"
                shift
                ;;
            --rollback)
                ROLLBACK="true"
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 如果是回滚操作
    if [[ "$ROLLBACK" == "true" ]]; then
        rollback
        exit 0
    fi
    
    # 验证环境
    if [[ ! "$DEPLOY_ENV" =~ ^(dev|staging|prod)$ ]]; then
        log_error "无效的环境: $DEPLOY_ENV，必须是 dev、staging 或 prod"
        exit 1
    fi
    
    # 检查目录
    cd "$(dirname "$0")/.." || exit 1
    
    log_info "开始竹林司马应用部署"
    log_info "部署环境: $DEPLOY_ENV"
    log_info "部署分支: ${DEPLOY_BRANCH:-当前分支}"
    log_info "部署标签: ${DEPLOY_TAG:-最新}"
    
    # 执行部署步骤
    check_dependencies
    check_docker
    check_git
    validate_environment "$DEPLOY_ENV"
    run_lint
    run_tests
    backup_current
    build_docker
    deploy_app
    cleanup_images
    
    log_success "部署流程完成！"
}

# 运行主函数
main "$@"