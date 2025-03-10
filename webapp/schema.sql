DROP TABLE IF EXISTS users;

CREATE TABLE users
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    has_node_red_permission BIT DEFAULT 0,     
    first_name TEXT DEFAULT 'Not provided',
    last_name TEXT DEFAULT 'Not provided'
);

INSERT INTO users (username, password)
VALUES ('admin', 'admin5'), ('admin2', 'admin5');