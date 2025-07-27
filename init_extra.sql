-- Crea tabella utenti (se non esiste)
CREATE TABLE IF NOT EXISTS utenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    ruolo TEXT,        -- 'admin' o 'voter'
    supermercato TEXT  -- nome del punto vendita
);

-- Inserisci utenti admin
INSERT OR IGNORE INTO utenti (username, password, ruolo, supermercato)
VALUES
    ('admin1', 'adminpass1', 'admin', 'supermercato1'),
    ('admin2', 'adminpass2', 'admin', 'supermercato2');

-- Inserisci utenti voter (cassieri)
INSERT OR IGNORE INTO utenti (username, password, ruolo, supermercato)
VALUES
    ('voter1', 'voterpass1', 'voter', 'supermercato1'),
    ('voter2', 'voterpass2', 'voter', 'supermercato2');
