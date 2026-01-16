#!/bin/bash
set -e

DEPLOYMENT_ID=$(node -p "require('./deployment-config.json').deploymentId")
REGION="us-east-1"
BUCKET_NAME="citizens-advice-frontend-${DEPLOYMENT_ID}"

echo "Building web UI..."
cd web-ui
npm run build
cd ..

echo "Uploading files to S3..."
aws s3 sync web-ui/dist s3://${BUCKET_NAME} --delete

echo ""
echo "✅ Frontend deployed successfully!"
echo ""
echo "Your application is in S3 bucket: ${BUCKET_NAME}"
echo ""
echo "To access it, you need to:"
echo "1. Set up CloudFront distribution pointing to this bucket, OR"
echo "2. Use AWS Amplify Console to host the app (recommended)"
echo ""
echo "For now, run locally with: npm run dev"
echo ""


