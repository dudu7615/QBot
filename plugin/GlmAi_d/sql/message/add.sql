-- add a new message
INSERT INTO messages (open_id, role, text)
VALUES (:open_id, :role, :text);

-- update user's updated_at timestamp
UPDATE users
SET updated_at = (DATETIME('now', 'localtime'))
WHERE open_id = :open_id;
