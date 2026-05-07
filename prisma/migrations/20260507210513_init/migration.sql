-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ended_at" TIMESTAMP(3),
    "status" TEXT NOT NULL DEFAULT 'active',
    "voice" TEXT NOT NULL DEFAULT 'Kore',
    "language" TEXT NOT NULL DEFAULT 'ru-RU',
    "source" TEXT NOT NULL DEFAULT 'web',
    "turn_count" INTEGER NOT NULL DEFAULT 0,
    "summary" TEXT,
    "audio_storage_path" TEXT,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "turns" (
    "id" SERIAL NOT NULL,
    "session_id" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "role" TEXT NOT NULL,
    "text" TEXT,
    "audio_file_path" TEXT,
    "audio_duration_ms" INTEGER,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "turns_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "diary_entries" (
    "id" SERIAL NOT NULL,
    "user_id" TEXT NOT NULL,
    "entry_date" DATE NOT NULL,
    "mood" INTEGER,
    "summary" TEXT,
    "key_events" JSONB NOT NULL DEFAULT '[]',
    "insights" JSONB NOT NULL DEFAULT '[]',
    "action_items" JSONB NOT NULL DEFAULT '[]',
    "source_session_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "diary_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "expenses" (
    "id" SERIAL NOT NULL,
    "user_id" TEXT NOT NULL,
    "expense_date" DATE NOT NULL,
    "amount" DOUBLE PRECISION NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'RUB',
    "category" TEXT NOT NULL,
    "description" TEXT,
    "source_session_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "expenses_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "turns_session_id_idx" ON "turns"("session_id");

-- CreateIndex
CREATE INDEX "turns_created_at_idx" ON "turns"("created_at");

-- CreateIndex
CREATE INDEX "diary_entries_user_id_entry_date_idx" ON "diary_entries"("user_id", "entry_date");

-- CreateIndex
CREATE INDEX "expenses_user_id_expense_date_idx" ON "expenses"("user_id", "expense_date");

-- CreateIndex
CREATE INDEX "expenses_user_id_category_idx" ON "expenses"("user_id", "category");

-- AddForeignKey
ALTER TABLE "turns" ADD CONSTRAINT "turns_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "diary_entries" ADD CONSTRAINT "diary_entries_source_session_id_fkey" FOREIGN KEY ("source_session_id") REFERENCES "sessions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "expenses" ADD CONSTRAINT "expenses_source_session_id_fkey" FOREIGN KEY ("source_session_id") REFERENCES "sessions"("id") ON DELETE SET NULL ON UPDATE CASCADE;
