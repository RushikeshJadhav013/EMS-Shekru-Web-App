# Netlify Deployment Guide

## Prerequisites
- Backend API deployed and accessible
- Netlify account

## Step 1: Configure Environment Variables
1. Create a `.env.production` file in the root:
```
VITE_API_BASE_URL=https://your-backend-api-url.com
```

## Step 2: Build for Production
```bash
npm run build
```

## Step 3: Deploy to Netlify
### Option A: Drag and Drop
1. Run `npm run build`
2. Drag the `dist` folder to Netlify
3. Set environment variables in Netlify dashboard

### Option B: Git Integration
1. Push code to GitHub
2. Connect repository to Netlify
3. Set build command: `npm run build`
4. Set publish directory: `dist`
5. Add environment variable: `VITE_API_BASE_URL`

## Step 4: Configure Netlify
The following files are automatically included:
- `netlify.toml` - Netlify configuration
- `public/_redirects` - SPA routing fallback

## Common Issues and Solutions

### 1. MIME Type Errors
- Fixed by `netlify.toml` headers configuration
- Ensures correct Content-Type for JS/CSS files

### 2. Blank Page
- Fixed by `_redirects` file for SPA routing
- All routes redirect to `index.html`

### 3. API Connection Issues
- Update `VITE_API_BASE_URL` in Netlify environment variables
- Must match your deployed backend URL

### 4. Manifest.json 404 Error
- File exists in `public/manifest.json`
- Should be automatically served by Netlify

## Environment Variables
Required:
- `VITE_API_BASE_URL` - Your backend API URL

## Build Optimization
- Code splitting for better performance
- Proper MIME types for all assets
- SPA routing support
- Security headers configured

## Testing After Deployment
1. Check if the site loads
2. Test login functionality
3. Verify API calls work
4. Test navigation between pages
5. Check mobile responsiveness
