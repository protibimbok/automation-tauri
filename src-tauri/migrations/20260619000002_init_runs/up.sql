CREATE TABLE runs (
    id TEXT PRIMARY KEY NOT NULL,
    platform TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    params TEXT NOT NULL DEFAULT '{}',
    log TEXT NOT NULL DEFAULT '',
    pause_info TEXT,
    error TEXT,
    item_count INTEGER NOT NULL DEFAULT 0,
    first_run_at TEXT,
    last_run_at TEXT,
    re_run_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_runs_platform ON runs (platform);

CREATE INDEX idx_runs_status ON runs (status);

CREATE TABLE run_inputs (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    data TEXT NOT NULL DEFAULT '{}',
    cursor TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, ordinal),
    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE INDEX idx_run_inputs_run ON run_inputs (run_id);

CREATE TABLE run_items (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL,
    input_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, item_key),
    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
    FOREIGN KEY (input_id) REFERENCES run_inputs (id) ON DELETE CASCADE
);

CREATE INDEX idx_run_items_run ON run_items (run_id);

CREATE INDEX idx_run_items_input ON run_items (input_id);
