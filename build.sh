#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🚀 Starting Nestova deployment build process..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

# Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

# Update Django site to production domain
echo "🌐 Updating site configuration..."
python manage.py update_site

# Setup Google OAuth for social login
echo "🔐 Setting up Google OAuth..."
python manage.py setup_google_oauth || echo "⚠️  Warning: Google OAuth setup failed (check environment variables)"

echo "✅ Build process completed successfully!"
echo "🎉 Nestova is ready for deployment!"
