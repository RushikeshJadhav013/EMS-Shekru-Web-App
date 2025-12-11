-- Add work_location column to attendances table
-- This tracks whether an employee is working from office or home

-- Check if column exists, if not add it
ALTER TABLE attendances 
ADD COLUMN IF NOT EXISTS work_location VARCHAR(50) DEFAULT 'office';

-- Update existing records to have 'office' as default
UPDATE attendances 
SET work_location = 'office' 
WHERE work_location IS NULL;
