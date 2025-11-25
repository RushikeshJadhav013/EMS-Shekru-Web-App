-- Verify Office Timing Configuration
-- Run this to check if office timing is properly configured

-- 1. Check current office timings
SELECT 
    id,
    department,
    start_time,
    end_time,
    check_in_grace_minutes,
    check_out_grace_minutes,
    is_active,
    created_at
FROM office_timings
WHERE is_active = TRUE
ORDER BY department NULLS FIRST;

-- 2. If no office timing exists, insert the default one
-- Office: 10:00 AM - 7:00 PM
-- Check-in buffer: 15 minutes (late after 10:15 AM)
-- Check-out buffer: 10 minutes (early before 6:50 PM)

INSERT INTO office_timings (
    department,
    start_time,
    end_time,
    check_in_grace_minutes,
    check_out_grace_minutes,
    is_active,
    created_at,
    updated_at
)
SELECT 
    NULL,
    '10:00:00'::time,
    '19:00:00'::time,
    15,
    10,
    TRUE,
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM office_timings 
    WHERE department IS NULL 
    AND is_active = TRUE
);

-- 3. Update existing global timing if needed
UPDATE office_timings
SET 
    start_time = '10:00:00'::time,
    end_time = '19:00:00'::time,
    check_in_grace_minutes = 15,
    check_out_grace_minutes = 10,
    updated_at = NOW()
WHERE department IS NULL 
AND is_active = TRUE;

-- 4. Verify the update
SELECT 
    id,
    department,
    start_time,
    end_time,
    check_in_grace_minutes,
    check_out_grace_minutes,
    is_active
FROM office_timings
WHERE is_active = TRUE
ORDER BY department NULLS FIRST;

-- 5. Check recent attendance with status
SELECT 
    a.attendance_id,
    u.name,
    u.department,
    a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' as check_in_ist,
    a.check_out AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' as check_out_ist,
    EXTRACT(HOUR FROM (a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) as check_in_hour,
    EXTRACT(MINUTE FROM (a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) as check_in_minute,
    CASE 
        WHEN EXTRACT(HOUR FROM (a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) * 60 + 
             EXTRACT(MINUTE FROM (a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) > 
             (10 * 60 + 15)  -- 10:15 AM in minutes
        THEN 'LATE'
        ELSE 'ON TIME'
    END as calculated_status
FROM attendance a
JOIN users u ON a.user_id = u.user_id
WHERE DATE(a.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
ORDER BY a.check_in DESC
LIMIT 10;
