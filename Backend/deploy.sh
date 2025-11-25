#!/bin/bash

# Environment-based deployment script
# Usage: ./deploy.sh [environment]
# Environments: development, testing, production

set -e

ENVIRONMENT=${1:-development}
PROJECT_NAME="Employee Management System"

echo "🚀 Deploying $PROJECT_NAME to $ENVIRONMENT environment"
echo "=" * 60

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|testing|production)$ ]]; then
    echo "❌ Invalid environment: $ENVIRONMENT"
    echo "Valid options: development, testing, production"
    exit 1
fi

# Set environment file
ENV_FILE=".env.$ENVIRONMENT"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Environment file not found: $ENV_FILE"
    exit 1
fi

echo "📋 Using environment file: $ENV_FILE"

# Copy environment file
cp "$ENV_FILE" .env

# Load environment variables
source .env

echo "🔧 Environment Configuration:"
echo "  - Environment: $ENVIRONMENT"
echo "  - Database: ${DATABASE_URL:0:20}..."
echo "  - OTP Method: $([ "$ENVIRONMENT" = "production" ] && echo "Email" || echo "Console (Fixed: $TESTING_OTP)")"
echo "  - Email Enabled: $ENABLE_EMAIL_OTP"

# Environment-specific setup
case $ENVIRONMENT in
    "development")
        echo "🛠️  Development Setup:"
        echo "  - Fixed OTP: $TESTING_OTP"
        echo "  - Console output enabled"
        echo "  - Debug endpoints available"
        ;;
    "testing")
        echo "🧪 Testing Setup:"
        echo "  - Fixed OTP: $TESTING_OTP"
        echo "  - Console output enabled"
        echo "  - Debug endpoints available"
        echo "  - Test database: ${DATABASE_URL:0:20}..."
        ;;
    "production")
        echo "🏭 Production Setup:"
        echo "  - Random OTP generation"
        echo "  - Email delivery enabled"
        echo "  - Debug endpoints disabled"
        echo "  - Security settings enabled"
        
        # Verify production requirements
        if [[ -z "$SMTP_HOST" || -z "$SMTP_USERNAME" || -z "$SMTP_PASSWORD" ]]; then
            echo "❌ Production requires SMTP configuration"
            echo "Please set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD"
            exit 1
        fi
        
        if [[ "$JWT_SECRET" == "supersecretjwtkey" || "$JWT_SECRET" == "dev-secret-key-change-in-production" ]]; then
            echo "⚠️  Warning: Using default JWT secret"
            echo "Please change JWT_SECRET for production"
        fi
        ;;
esac

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Database migrations (if needed)
echo ""
echo "🗄️  Database setup..."
# Add migration commands here if needed
# alembic upgrade head

# Run tests
if [[ "$ENVIRONMENT" != "production" ]]; then
    echo ""
    echo "🧪 Running tests..."
    python test_otp_environments.py
fi

# Start server
echo ""
echo "🌐 Starting server..."
echo "Environment: $ENVIRONMENT"
echo "Server will start on: http://localhost:8000"
echo ""
echo "🔍 Test endpoints:"
if [[ "$ENVIRONMENT" != "production" ]]; then
    echo "  - Environment info: http://localhost:8000/auth/debug/environment"
    echo "  - OTP info: http://localhost:8000/auth/debug/otp/test@example.com"
    echo "  - Test email: http://localhost:8000/auth/debug/test-email"
fi
echo "  - Send OTP: POST http://localhost:8000/auth/send-otp?email=test@example.com"
echo "  - Verify OTP: POST http://localhost:8000/auth/verify-otp"
echo ""

# Start the server
if [[ "$ENVIRONMENT" == "development" ]]; then
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
elif [[ "$ENVIRONMENT" == "testing" ]]; then
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
fi
