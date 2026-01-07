#!/bin/bash

echo "=========================================="
echo "🚀 Arboris Novel 一键部署脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否在deploy目录
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ 错误：请在 deploy 目录下运行此脚本${NC}"
    echo "请执行：cd /Users/shu/Documents/fix_nocel/arboris-novel/deploy"
    exit 1
fi

echo -e "${YELLOW}📦 步骤 1/5：停止现有容器...${NC}"
docker-compose down
echo ""

echo -e "${YELLOW}🗑️  步骤 2/5：删除旧镜像...${NC}"
docker rmi ghcr.io/samuncleorange/arboris-novel:latest 2>/dev/null || echo "旧镜像不存在，跳过"
echo ""

echo -e "${YELLOW}⬇️  步骤 3/5：拉取最新镜像（v1.1.1）...${NC}"
docker-compose pull
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 拉取镜像失败！请检查网络连接或GitHub Actions构建状态${NC}"
    echo "构建状态查看：https://github.com/samuncleorange/arboris-novel/actions"
    exit 1
fi
echo ""

echo -e "${YELLOW}🚀 步骤 4/5：启动服务...${NC}"
docker-compose up -d
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 启动服务失败！${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}📋 步骤 5/5：检查服务状态...${NC}"
sleep 3
docker-compose ps
echo ""

echo -e "${GREEN}=========================================="
echo "✅ 部署完成！"
echo "==========================================${NC}"
echo ""
echo -e "${YELLOW}📝 重要提示：${NC}"
echo "1. 🔍 查看日志：docker-compose logs -f arboris-app"
echo "2. 🌐 访问地址：http://localhost:28788"
echo "3. ⚠️  ${RED}必须删除旧章节并重新生成才能看到修复效果！${NC}"
echo "4. 📖 详细测试步骤请查看：./DEPLOY_AND_TEST.md"
echo ""
echo -e "${YELLOW}🧪 测试检查清单：${NC}"
echo "   ✓ 删除一个旧章节"
echo "   ✓ 重新生成该章节"
echo "   ✓ 确认章节内容只显示纯文本（不含JSON结构）"
echo "   ✓ 确认字数统计正确（约4500字）"
echo ""
echo -e "${GREEN}🐱 修复完成后，小猫咪安全了！${NC}"
echo ""
