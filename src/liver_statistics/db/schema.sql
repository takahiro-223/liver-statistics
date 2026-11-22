CREATE TABLE IF NOT EXISTS tribes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tribe_id    INTEGER NOT NULL REFERENCES tribes(id),
    name        TEXT    NOT NULL,
    name_key    TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (tribe_id, name_key)
);

CREATE TABLE IF NOT EXISTS member_aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    alias_key   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (member_id, alias_key)
);

CREATE TABLE IF NOT EXISTS source_images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tribe_id     INTEGER NOT NULL REFERENCES tribes(id),
    file_name    TEXT    NOT NULL,
    file_path    TEXT    NOT NULL,
    sha256       TEXT    NOT NULL,
    captured_at  TEXT    NOT NULL,
    imported_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (tribe_id, sha256)
);

CREATE TABLE IF NOT EXISTS member_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id        INTEGER NOT NULL REFERENCES members(id),
    record_date      TEXT    NOT NULL,
    level            INTEGER,
    honor            INTEGER,
    needs_review     INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
    review_reason    TEXT,
    source_image_id  INTEGER NOT NULL REFERENCES source_images(id),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (member_id, record_date)
);

CREATE INDEX IF NOT EXISTS idx_member_records_date ON member_records(record_date);
