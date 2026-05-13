-- CreateTable
CREATE TABLE "roles" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,

    CONSTRAINT "roles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "permissions" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,

    CONSTRAINT "permissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_permissions" (
    "user_id" TEXT NOT NULL,
    "permission_id" INTEGER NOT NULL,

    CONSTRAINT "user_permissions_pkey" PRIMARY KEY ("user_id", "permission_id")
);

-- CreateTable
CREATE TABLE "role_permissions" (
    "role_id" INTEGER NOT NULL,
    "permission_id" INTEGER NOT NULL,

    CONSTRAINT "role_permissions_pkey" PRIMARY KEY ("role_id", "permission_id")
);

-- CreateTable
CREATE TABLE "vacation_types" (
    "id" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "vacation_types_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "roles_name_key" ON "roles"("name");

-- CreateIndex
CREATE UNIQUE INDEX "permissions_name_key" ON "permissions"("name");

-- CreateIndex
CREATE UNIQUE INDEX "vacation_types_code_key" ON "vacation_types"("code");

-- CreateIndex
CREATE UNIQUE INDEX "vacation_types_name_key" ON "vacation_types"("name");

-- Seed roles needed by the current Prisma schema.
INSERT INTO "roles" ("name", "description")
VALUES
    ('EMPLOYEE', 'Rol migrado desde el esquema inicial.'),
    ('HR', 'Rol migrado desde el esquema inicial.')
ON CONFLICT ("name") DO NOTHING;

-- Seed a default vacation type so existing requests can be backfilled safely.
INSERT INTO "vacation_types" ("id", "code", "name", "created_at", "updated_at")
VALUES
    ('00000000-0000-0000-0000-000000000001', 'VACATIONS', 'Vacaciones', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT ("code") DO NOTHING;

-- AlterTable
ALTER TABLE "users" ADD COLUMN "role_id" INTEGER;

-- Map legacy enum values to the new roles table.
UPDATE "users" AS u
SET "role_id" = r."id"
FROM "roles" AS r
WHERE r."name" = u."role"::TEXT;

-- Ensure new relation field is present for all users.
UPDATE "users"
SET "role_id" = (SELECT "id" FROM "roles" WHERE "name" = 'EMPLOYEE')
WHERE "role_id" IS NULL;

-- AlterTable
ALTER TABLE "users" ALTER COLUMN "role_id" SET NOT NULL;

-- AlterTable
ALTER TABLE "vacation_requests" ADD COLUMN "vacation_type_id" TEXT;

-- Backfill existing requests with the seeded vacation type.
UPDATE "vacation_requests"
SET "vacation_type_id" = '00000000-0000-0000-0000-000000000001'
WHERE "vacation_type_id" IS NULL;

-- AlterTable
ALTER TABLE "vacation_requests" ALTER COLUMN "vacation_type_id" SET NOT NULL;

-- CreateIndex
CREATE INDEX "vacation_requests_vacation_type_id_idx" ON "vacation_requests"("vacation_type_id");

-- AddForeignKey
ALTER TABLE "users" ADD CONSTRAINT "users_role_id_fkey"
FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_permissions" ADD CONSTRAINT "user_permissions_permission_id_fkey"
FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_role_id_fkey"
FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_permission_id_fkey"
FOREIGN KEY ("permission_id") REFERENCES "permissions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "vacation_requests" ADD CONSTRAINT "vacation_requests_vacation_type_id_fkey"
FOREIGN KEY ("vacation_type_id") REFERENCES "vacation_types"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Drop the legacy enum-based role column now that role_id is in place.
ALTER TABLE "users" DROP COLUMN "role";

-- DropEnum
DROP TYPE "Role";
