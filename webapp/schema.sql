DROP TABLE IF EXISTS users;

CREATE TABLE users
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,     
    first_name TEXT DEFAULT 'Not provided',
    last_name TEXT DEFAULT 'Not provided'
);

INSERT INTO users (username, password)
VALUES ('default', 'default');