/*
  Changes:

  - Converts `roles.id` and `permissions.id` from TEXT UUIDs to INTEGER autoincrement.
  - Preserves existing relations from `users`, `role_permissions`, and `user_permissions`.
*/
BEGIN;

-- Drop foreign keys that depend on the old TEXT ids.
ALTER TABLE "users" DROP CONSTRAINT "users_role_id_fkey";
ALTER TABLE "user_permissions" DROP CONSTRAINT "user_permissions_permission_id_fkey";
ALTER TABLE "role_permissions" DROP CONSTRAINT "role_permissions_role_id_fkey";
ALTER TABLE "role_permissions" DROP CONSTRAINT "role_permissions_permission_id_fkey";

-- Add replacement integer ids for roles.
ALTER TABLE "roles" ADD COLUMN "new_id" INTEGER;
CREATE SEQUENCE "roles_new_id_seq";
ALTER TABLE "roles" ALTER COLUMN "new_id" SET DEFAULT nextval('roles_new_id_seq');
UPDATE "roles" SET "new_id" = nextval('roles_new_id_seq') WHERE "new_id" IS NULL;
ALTER SEQUENCE "roles_new_id_seq" OWNED BY "roles"."new_id";

DO $$
DECLARE max_id INTEGER;
BEGIN
  SELECT MAX("new_id") INTO max_id FROM "roles";

  IF max_id IS NULL THEN
    PERFORM setval('roles_new_id_seq', 1, false);
  ELSE
    PERFORM setval('roles_new_id_seq', max_id, true);
  END IF;
END $$;

-- Add replacement integer ids for permissions.
ALTER TABLE "permissions" ADD COLUMN "new_id" INTEGER;
CREATE SEQUENCE "permissions_new_id_seq";
ALTER TABLE "permissions" ALTER COLUMN "new_id" SET DEFAULT nextval('permissions_new_id_seq');
UPDATE "permissions" SET "new_id" = nextval('permissions_new_id_seq') WHERE "new_id" IS NULL;
ALTER SEQUENCE "permissions_new_id_seq" OWNED BY "permissions"."new_id";

DO $$
DECLARE max_id INTEGER;
BEGIN
  SELECT MAX("new_id") INTO max_id FROM "permissions";

  IF max_id IS NULL THEN
    PERFORM setval('permissions_new_id_seq', 1, false);
  ELSE
    PERFORM setval('permissions_new_id_seq', max_id, true);
  END IF;
END $$;

-- Add temporary foreign key columns with integer ids.
ALTER TABLE "users" ADD COLUMN "new_role_id" INTEGER;
ALTER TABLE "user_permissions" ADD COLUMN "new_permission_id" INTEGER;
ALTER TABLE "role_permissions" ADD COLUMN "new_role_id" INTEGER;
ALTER TABLE "role_permissions" ADD COLUMN "new_permission_id" INTEGER;

-- Backfill the new foreign key columns from the old UUID/text ids.
UPDATE "users" AS u
SET "new_role_id" = r."new_id"
FROM "roles" AS r
WHERE u."role_id" = r."id";

UPDATE "user_permissions" AS up
SET "new_permission_id" = p."new_id"
FROM "permissions" AS p
WHERE up."permission_id" = p."id";

UPDATE "role_permissions" AS rp
SET "new_role_id" = r."new_id"
FROM "roles" AS r
WHERE rp."role_id" = r."id";

UPDATE "role_permissions" AS rp
SET "new_permission_id" = p."new_id"
FROM "permissions" AS p
WHERE rp."permission_id" = p."id";

-- Replace the old primary keys and relation columns.
ALTER TABLE "user_permissions" DROP CONSTRAINT "user_permissions_pkey";
ALTER TABLE "role_permissions" DROP CONSTRAINT "role_permissions_pkey";
ALTER TABLE "roles" DROP CONSTRAINT "roles_pkey";
ALTER TABLE "permissions" DROP CONSTRAINT "permissions_pkey";

ALTER TABLE "users" DROP COLUMN "role_id";
ALTER TABLE "user_permissions" DROP COLUMN "permission_id";
ALTER TABLE "role_permissions" DROP COLUMN "role_id";
ALTER TABLE "role_permissions" DROP COLUMN "permission_id";

ALTER TABLE "users" RENAME COLUMN "new_role_id" TO "role_id";
ALTER TABLE "user_permissions" RENAME COLUMN "new_permission_id" TO "permission_id";
ALTER TABLE "role_permissions" RENAME COLUMN "new_role_id" TO "role_id";
ALTER TABLE "role_permissions" RENAME COLUMN "new_permission_id" TO "permission_id";

ALTER TABLE "users" ALTER COLUMN "role_id" SET NOT NULL;
ALTER TABLE "user_permissions" ALTER COLUMN "permission_id" SET NOT NULL;
ALTER TABLE "role_permissions" ALTER COLUMN "role_id" SET NOT NULL;
ALTER TABLE "role_permissions" ALTER COLUMN "permission_id" SET NOT NULL;

ALTER TABLE "roles" DROP COLUMN "id";
ALTER TABLE "permissions" DROP COLUMN "id";

ALTER TABLE "roles" RENAME COLUMN "new_id" TO "id";
ALTER TABLE "permissions" RENAME COLUMN "new_id" TO "id";

ALTER TABLE "roles" ALTER COLUMN "id" SET NOT NULL;
ALTER TABLE "permissions" ALTER COLUMN "id" SET NOT NULL;

ALTER TABLE "roles" ADD CONSTRAINT "roles_pkey" PRIMARY KEY ("id");
ALTER TABLE "permissions" ADD CONSTRAINT "permissions_pkey" PRIMARY KEY ("id");
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_pkey" PRIMARY KEY ("user_id", "permission_id");
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_pkey" PRIMARY KEY ("role_id", "permission_id");

ALTER TABLE "users"
  ADD CONSTRAINT "users_role_id_fkey"
  FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "user_permissions"
  ADD CONSTRAINT "user_permissions_permission_id_fkey"
  FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "role_permissions"
  ADD CONSTRAINT "role_permissions_role_id_fkey"
  FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "role_permissions"
  ADD CONSTRAINT "role_permissions_permission_id_fkey"
  FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

COMMIT;
