-- Notifications feed (useNotifications.js) subscribes to postgres_changes on
-- delivery_jobs; realtime only fires for tables in the supabase_realtime
-- publication. consultations is already published (dashboard realtime works);
-- this adds delivery_jobs. Safe to re-run.
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE delivery_jobs;
EXCEPTION
  WHEN duplicate_object THEN NULL;  -- already published
END $$;
