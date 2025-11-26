# API Integration Guide - Authentication Flow

## Overview
The frontend authentication system has been configured to work with your new backend API endpoints.

## API Endpoints

### 1. Send OTP
**Endpoint:** `POST http://172.105.56.142/auth/send-otp?email={email}`

**Query Parameters:**
- `email` (string, required): User's email address

**Example:**
```
POST http://172.105.56.142/auth/send-otp?email=user@example.com
```

**Success Response (200/201):**
```json
{
  "message": "OTP sent successfully"
}
```

**Error Response:**
```json
{
  "detail": "Error message here"
}
```

### 2. Verify OTP
**Endpoint:** `POST http://172.105.56.142/auth/verify-otp?email={email}&otp={otp}`

**Query Parameters:**
- `email` (string, required): User's email address
- `otp` (integer, required): 6-digit OTP code

**Example:**
```
POST http://172.105.56.142/auth/verify-otp?email=user@example.com&otp=123456
```

**Success Response (200/201):**
```json
{
  "user_id": "unique_user_id",
  "email": "user@example.com",
  "name": "User Name",
  "role": "employee",
  "department": "Engineering",
  "designation": "Developer",
  "joining_date": "2024-01-01",
  "access_token": "jwt_token_here",
  "token_type": "bearer"
}
```

**Error Response:**
```json
{
  "detail": "Invalid or expired OTP"
}
```

## Frontend Implementation

### Files Modified:
1. **`/Frontend/src/pages/Login.tsx`**
   - Handles the OTP login flow
   - Sends OTP request
   - Verifies OTP
   - Manages loading states and error handling

2. **`/Frontend/src/contexts/AuthContext.tsx`**
   - Manages user authentication state
   - Stores user data and token in localStorage
   - Handles role-based navigation

### Authentication Flow:

```
1. User enters email → Click "Send OTP"
   ↓
2. Frontend calls: POST /auth/send-otp
   ↓
3. Backend sends OTP to email
   ↓
4. User receives OTP and enters it
   ↓
5. Frontend calls: POST /auth/verify-otp
   ↓
6. Backend verifies OTP and returns user data + token
   ↓
7. Frontend stores token and user data
   ↓
8. User is redirected to role-based dashboard
```

### Role-Based Navigation:
- **admin** → `/admin`
- **hr** → `/hr`
- **manager** → `/manager`
- **team_lead** → `/team_lead`
- **employee** → `/employee`

## Error Handling

The system handles the following error scenarios:

1. **Invalid Email:** Validation on frontend
2. **OTP Send Failure:** Shows error message from backend
3. **Invalid OTP:** Shows "Invalid or expired OTP" message
4. **Network Error:** Shows "Unable to connect to the server"
5. **Server Error:** Shows detailed error message from backend

## Token Storage

- **Access Token:** Stored in `localStorage` as `token`
- **User Data:** Stored in `localStorage` as `user`

## Testing the Integration

### 1. Start the Backend Server
```bash
cd Backend
uvicorn app.main:app --reload
```

### 2. Start the Frontend Server
```bash
cd Frontend
npm run dev
```

### 3. Test the Login Flow
1. Navigate to `http://localhost:5173/login`
2. Enter a valid email address
3. Click "Send OTP"
4. Check your email for the OTP
5. Enter the OTP
6. Click "Verify OTP"
7. You should be redirected to your role-based dashboard

## API Configuration

The API endpoints are configured in:
```typescript
// src/pages/Login.tsx
const API_ENDPOINTS = {
  sendOtp: 'http://172.105.56.142/auth/send-otp',
  verifyOtp: 'http://172.105.56.142/auth/verify-otp'
};
```

## Next Steps

1. ✅ Send OTP API - **CONFIGURED**
2. ✅ Verify OTP API - **CONFIGURED**
3. ⏳ Attendance APIs - **PENDING**
4. ⏳ Leave Management APIs - **PENDING**
5. ⏳ Task Management APIs - **PENDING**
6. ⏳ User Profile APIs - **PENDING**

## Troubleshooting

### Issue: "Unable to connect to the server"
**Solution:** Make sure the backend server is running on `http://172.105.56.142`

### Issue: "Invalid or expired OTP"
**Solution:** 
- Check if the OTP is correct
- OTP might have expired (check backend OTP expiry time)
- Try requesting a new OTP

### Issue: CORS Error
**Solution:** Make sure your backend has CORS enabled for `http://localhost:5173`

### Issue: Token not persisting
**Solution:** Check browser localStorage to ensure token is being saved

## Security Notes

1. **Token Storage:** Currently using localStorage. Consider using httpOnly cookies for production.
2. **OTP Expiry:** Implement OTP expiry on backend (recommended: 5-10 minutes)
3. **Rate Limiting:** Implement rate limiting on OTP send endpoint
4. **HTTPS:** Use HTTPS in production for secure token transmission

## Support

For issues or questions, contact the development team or refer to the backend API documentation at:
`http://172.105.56.142/docs`
