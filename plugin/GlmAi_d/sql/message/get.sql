SELECT role, text FROM messages
WHERE open_id = :open_id
ORDER BY time ASC;