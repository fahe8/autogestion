/*
  Warnings:

  - A unique constraint covering the columns `[number_identity]` on the table `users` will be added. If there are existing duplicate values, this will fail.
  - Changed the type of `number_identity` on the `users` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.

*/
-- AlterTable
ALTER TABLE "users" DROP COLUMN "number_identity",
ADD COLUMN     "number_identity" INTEGER NOT NULL;

-- CreateIndex
CREATE UNIQUE INDEX "users_number_identity_key" ON "users"("number_identity");
