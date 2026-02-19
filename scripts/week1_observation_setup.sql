-- Week 1 production observation setup
-- 1) Remove demo data
DELETE FROM outreach_queue;
DELETE FROM prospects
WHERE lower(coalesce(source, '')) = 'demo'
   OR email ILIKE '%@roofingcompany%.com'
   OR contact_name ILIKE 'John Smith %';

-- 2) Enable all agents for week-1 observation
UPDATE agent_settings SET is_enabled = true;

-- 3) Revenue and operations schedule optimization
UPDATE agent_settings SET schedule_cron = '0 6 * * *' WHERE agent_name = 'Lead Scraper';
UPDATE agent_settings SET schedule_cron = '0 */2 8-18 * * 1-5' WHERE agent_name = 'Lead Enricher';
UPDATE agent_settings SET schedule_cron = '0 9,15 * * 1-5' WHERE agent_name = 'Outreach Sender';
UPDATE agent_settings SET schedule_cron = '0 */3 9-18 * * 1-5' WHERE agent_name = 'Meeting Scheduler';
UPDATE agent_settings SET schedule_cron = '*/30 * * * *' WHERE agent_name = 'Cost Monitor';
UPDATE agent_settings SET schedule_cron = '0 7 * * 1-5' WHERE agent_name = 'Daily Briefing';
UPDATE agent_settings SET schedule_cron = '0 */6 * * *' WHERE agent_name = 'GoHighLevel Sync';

-- 4) Content cadence: 3x/week for observation period
UPDATE agent_settings SET schedule_cron = '0 10 * * 1,3,5' WHERE tier = 'Content';
