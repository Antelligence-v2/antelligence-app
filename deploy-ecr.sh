#!/bin/bash

# Antelligence AWS ECR Deployment Script
echo "🚀 Starting Antelligence ECR deployment..."

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

# Build the Docker image
# Use --no-cache flag if frontend needs to be rebuilt: ./deploy-ecr.sh --no-cache
BUILD_TIMESTAMP=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
BUILD_VERSION=$(date +%s)

if [ "$1" == "--no-cache" ]; then
    echo "🔨 Building Docker image (no cache - fresh frontend build)..."
    docker build --no-cache \
        --build-arg BUILD_TIMESTAMP="$BUILD_TIMESTAMP" \
        --build-arg BUILD_VERSION="$BUILD_VERSION" \
        -t antelligence .
else
    echo "🔨 Building Docker image..."
    docker build \
        --build-arg BUILD_TIMESTAMP="$BUILD_TIMESTAMP" \
        --build-arg BUILD_VERSION="$BUILD_VERSION" \
        -t antelligence .
fi

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
else
    echo "❌ Docker build failed!"
    exit 1
fi

# Tag the image for ECR
echo "🏷️ Tagging image for ECR..."
docker tag antelligence:latest $ECR_REPO:latest

# Push to ECR
echo "📤 Pushing to ECR..."
docker push $ECR_REPO:latest

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to ECR!"
    echo ""
    echo "🌐 Your image is now available at: $ECR_REPO:latest"
    echo ""
    echo "📋 To deploy on EC2:"
    echo "1. SSH to your EC2 instance"
    echo "2. Run: docker pull $ECR_REPO:latest"
    echo "3. Run: docker run -p 8001:8001 $ECR_REPO:latest"
    echo ""
    echo "🔧 Or use docker-compose with ECR image:"
    echo "   Update docker-compose.yml to use: $ECR_REPO:latest"
else
    echo "❌ Failed to push to ECR!"
    exit 1
fi

echo "🎉 ECR deployment completed successfully!" 