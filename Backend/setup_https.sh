#!/bin/bash

# HTTPS Setup Script for Backend Server
# Run this on your server (172.105.56.142)

echo "🔒 Setting up HTTPS for backend server..."

# Install certbot for Let's Encrypt
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Get domain name or use IP
read -p "Enter your domain name (or press Enter to use IP): " DOMAIN
if [ -z "$DOMAIN" ]; then
    DOMAIN="172.105.56.142"
    echo "⚠️  Using IP address. Consider getting a domain name for better SSL support."
fi

# Create nginx configuration
sudo tee /etc/nginx/sites-available/backend > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/backend /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate (only works with domain names)
if [ "$DOMAIN" != "172.105.56.142" ]; then
    sudo certbot --nginx -d $DOMAIN
else
    echo "⚠️  Cannot get SSL certificate for IP address."
    echo "Consider using a domain name or self-signed certificate."
fi

echo "✅ HTTPS setup complete!"
echo "Your backend should now be accessible at: https://$DOMAIN"