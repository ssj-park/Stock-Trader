-- Create transactions table to track purchases

CREATE TABLE if NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS index_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS index_transactions_symbol ON transactions(symbol);
