-- CreateTable
CREATE TABLE "vacation_types" (
    "id" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "vacation_types_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "vacation_types_code_key" ON "vacation_types"("code");

-- CreateIndex
CREATE UNIQUE INDEX "vacation_types_name_key" ON "vacation_types"("name");

-- Seed catalog
INSERT INTO "vacation_types" ("id", "code", "name", "description", "updated_at")
VALUES
    (
        '1d45d6d2-b25d-4bb0-a2bb-01f26ab7f101',
        'VACACIONES_DISFRUTADAS',
        'Vacaciones Disfrutadas',
        'Vacaciones tomadas por el colaborador en tiempo.',
        CURRENT_TIMESTAMP
    ),
    (
        '1d45d6d2-b25d-4bb0-a2bb-01f26ab7f102',
        'VACACIONES_EN_DINERO',
        'Vacaciones en Dinero',
        'Vacaciones compensadas o pagadas en dinero.',
        CURRENT_TIMESTAMP
    );

-- AlterTable
ALTER TABLE "vacation_requests" ADD COLUMN "vacation_type_id" TEXT;

-- Backfill existing data
UPDATE "vacation_requests"
SET "vacation_type_id" = (
    SELECT "id"
    FROM "vacation_types"
    WHERE "code" = 'VACACIONES_DISFRUTADAS'
    LIMIT 1
)
WHERE "vacation_type_id" IS NULL;

-- Make relation required
ALTER TABLE "vacation_requests"
ALTER COLUMN "vacation_type_id" SET NOT NULL;

-- CreateIndex
CREATE INDEX "vacation_requests_vacation_type_id_idx" ON "vacation_requests"("vacation_type_id");

-- AddForeignKey
ALTER TABLE "vacation_requests"
ADD CONSTRAINT "vacation_requests_vacation_type_id_fkey"
FOREIGN KEY ("vacation_type_id") REFERENCES "vacation_types"("id")
ON DELETE RESTRICT ON UPDATE CASCADE;
