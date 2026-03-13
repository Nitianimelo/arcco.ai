-- Migration: Expand ChatConfigs to support unlimited admin-created models
-- Description: Removes the old 1-5 slot limit so the admin can create as many chat models as needed
-- Created: 2026-03-10

ALTER TABLE "ChatConfigs"
  DROP CONSTRAINT IF EXISTS "ChatConfigs_slot_number_check";

ALTER TABLE "ChatConfigs"
  ADD CONSTRAINT "ChatConfigs_slot_number_check"
  CHECK (slot_number > 0);

COMMENT ON COLUMN "ChatConfigs".slot_number IS 'Display order for chat models created in the admin panel';
