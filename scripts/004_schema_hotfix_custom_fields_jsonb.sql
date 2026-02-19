-- Emergency schema hotfix: ensure prospects.custom_fields supports JSON operations.

ALTER TABLE prospects
ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'prospects'
          AND column_name = 'custom_fields'
          AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE prospects
        ALTER COLUMN custom_fields TYPE JSONB
        USING CASE
            WHEN custom_fields IS NULL THEN '{}'::jsonb
            ELSE custom_fields::jsonb
        END;
    END IF;
END $$;

UPDATE prospects
SET custom_fields = '{}'::jsonb
WHERE custom_fields IS NULL;
