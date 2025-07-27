import sqlite3

DB = "database.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

# Aggiungi colonna store_id se non esiste
cols = [row[1] for row in c.execute("PRAGMA table_info(dipendenti)")]
if "store_id" not in cols:
    print("Aggiungo colonna store_id a dipendenti...")
    c.execute("ALTER TABLE dipendenti ADD COLUMN store_id TEXT")
    conn.commit()

# Aggiorna tutti i dipendenti senza store_id
print("Aggiorno dipendenti senza store_id, assegnandoli a pdv_sciacca...")
c.execute("UPDATE dipendenti SET store_id='pdv_sciacca' WHERE store_id IS NULL OR store_id=''")
conn.commit()

# Aggiorna gli utenti esistenti (se non sono già aggiornati)
print("Controllo utenti nella tabella utenti...")
c.execute("SELECT username, store FROM utenti")
utenti = c.fetchall()
for u in utenti:
    print(" -", u)

# Fine
print("Migrazione completata con successo.")
conn.close()
