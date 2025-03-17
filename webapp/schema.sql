DROP TABLE IF EXISTS users;

CREATE TABLE users
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    has_node_red_permission INTEGER DEFAULT 0,     
    country TEXT DEFAULT 'Not Provided'
);

INSERT INTO users (username, password, email)
VALUES ('admin', 'admin5', 'a@a.a');

SELECT * FROM users;