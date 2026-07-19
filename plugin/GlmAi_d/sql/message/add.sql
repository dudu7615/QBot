-- add a new message
INSERT INTO messages (open_id, role, content)
VALUES (:open_id, :role, :content);

-- update user's updated_at timestamp
UPDATE users
SET updated_at = (DATETIME('now', 'localtime'))
WHERE open_id = :open_id;
