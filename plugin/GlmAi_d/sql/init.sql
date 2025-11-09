BEGIN TRANSACTION;
CREATE TABLE users (
    open_id TEXT PRIMARY KEY,  -- 用户唯一标识
    name TEXT NOT NULL,  -- 用户名
    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
    updated_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime'))
);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT NOT NULL,  -- 关联用户表的open_id
    role TEXT NOT NULL CHECK(role IN ('assistant', 'user')),  -- 角色只能是'assistant'或'user'
    text TEXT NOT NULL,  -- 消息内容
    time TIMESTAMP NOT NULL DEFAULT (DATETIME('now', 'localtime')),  -- 消息时间
    FOREIGN KEY (open_id) REFERENCES users(open_id) ON DELETE CASCADE,
    UNIQUE(open_id, time)  -- 确保每个用户在同一时间只有一条消息
);
COMMIT;
