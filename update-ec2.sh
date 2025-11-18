#!/bin/bash

# Antelligence EC2 Update Script
# Run this script on your EC2 instance to pull the latest image from ECR and restart

set -e

echo "🚀 Starting Antelligence EC2 update..."

# ECR Repository details
ECR_REPO="983240697534.dkr.ecr.us-east-1.amazonaws.com/antelligence"
REGION="us-east-1"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO

if [ $? -ne 0 ]; then
    echo "❌ Failed to login to ECR. Please check your AWS credentials."
    exit 1
fi

# Stop existing container if running
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose-ecr.yml down 2>/dev/null || true
docker stop antelligence 2>/dev/null || true
docker rm antelligence 2>/dev/null || true

# Clean up Docker to free space
echo "🧹 Cleaning up Docker to free space..."
docker system prune -f
docker image prune -f
echo "💾 Current disk space:"
df -h / | tail -1

# Pull latest image from ECR
echo "📥 Pulling latest image from ECR..."
docker pull $ECR_REPO:latest

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull image from ECR!"
    exit 1
fi

# Start with docker-compose (if docker-compose-ecr.yml exists)
if [ -f "docker-compose-ecr.yml" ]; then
    echo "🚀 Starting application with docker-compose..."
    docker-compose -f docker-compose-ecr.yml up -d
else
    # Fallback: run with docker directly
    echo "🚀 Starting application with docker..."
    docker run -d \
        --name antelligence \
        --restart unless-stopped \
        -p 8001:8001 \
        --env-file .env \
        $ECR_REPO:latest
fi

# Wait for the application to be ready
echo "⏳ Waiting for application to be ready..."
sleep 10

# Check if the application is running
if curl -f http://localhost:8001/health &> /dev/null; then
    echo "✅ Application updated and running successfully!"
    echo "🌐 Access the application at: http://localhost:8001"
else
    echo "⚠️  Application started but health check failed. Check logs:"
    docker-compose -f docker-compose-ecr.yml logs || docker logs antelligence
fi

echo "🎉 EC2 update completed successfully!"

