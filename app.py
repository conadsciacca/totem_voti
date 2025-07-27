from flask import Flask, render_template, request, redirect, url_for, send_file, session
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3, os, csv
from datetime import datetime
from io import StringIO

app = Flask(__name__)
app.secret_key = "TotemAdminPhabio@2025"
DB = 'database.db'

UPLOAD_FOLDER = os.path.join('static', 'foto')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ---------------- FUNZIONI DB ----------------
def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()

        # Tabella utenti
        c.execute('''
            CREATE TABLE IF NOT EXISTS utenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                store TEXT
            )
        ''')

        # Tabella dipendenti
        c.execute('''
            CREATE TABLE IF NOT EXISTS dipendenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                foto TEXT
            )
        ''')

        # Aggiunge colonna store_id se non esiste
        cols = [row[1] for row in c.execute("PRAGMA table_info(dipendenti)")]
        if "store_id" not in cols:
            c.execute("ALTER TABLE dipendenti ADD COLUMN store_id TEXT")

        # Tabella voti
        c.execute('''
            CREATE TABLE IF NOT EXISTS voti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fidelity TEXT,
                dipendente_id INTEGER,
                voto INTEGER,
                UNIQUE(fidelity,dipendente_id)
            )
        ''')

        # Inserisce utenti base solo se non ci sono
        c.execute("SELECT COUNT(*) FROM utenti")
        if c.fetchone()[0] == 0:
            # Admins
            c.execute("INSERT INTO utenti (username,password,role,store) VALUES (?,?,?,?)",
                      ("admin_sciacca","mypass1","admin","pdv_sciacca"))
            c.execute("INSERT INTO utenti (username,password,role,store) VALUES (?,?,?,?)",
                      ("admin_sancipirello","mypass2","admin","pdv_sancipirello"))
            # Utenti normali
            c.execute("INSERT INTO utenti (username,password,role,store) VALUES (?,?,?,?)",
                      ("user_sciacca","pass1","store","pdv_sciacca"))
            c.execute("INSERT INTO utenti (username,password,role,store) VALUES (?,?,?,?)",
                      ("user_sancipirello","pass2","store","pdv_sancipirello"))

        conn.commit()

def get_dipendenti(store_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Ora ritorna 4 colonne: id, nome, foto, store_id
        c.execute("SELECT id, nome, foto, store_id FROM dipendenti WHERE store_id=?", (store_id,))
        return c.fetchall()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- DECORATORI ----------------
def login_required(role=None):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# ---------------- ROUTES LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("SELECT role, store FROM utenti WHERE username=? AND password=?", (user, pwd))
            row = c.fetchone()
        if row:
            role, store = row
            session['user'] = user
            session['role'] = role
            session['store'] = store
            if role == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('index'))
        return "Credenziali errate", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- ROUTES PUNTO VENDITA ----------------
@app.route('/', methods=['GET','POST'])
@login_required(role='store')
def index():
    if request.method == 'POST':
        codice = request.form.get('codice', '')
        if codice.isdigit() and len(codice) == 13:
            return redirect(url_for('dipendenti_list', fidelity=codice))
    return render_template('index.html')

@app.route('/dipendenti/<fidelity>')
@login_required(role='store')
def dipendenti_list(fidelity):
    store = session.get('store')
    dip = get_dipendenti(store)
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT dipendente_id FROM voti WHERE fidelity=?", (fidelity,))
        votati = [row[0] for row in c.fetchall()]
    return render_template('dipendenti.html', dipendenti=dip, votati=votati, fidelity=fidelity)

@app.route('/vota/<fidelity>/<int:dipendente_id>', methods=['GET','POST'])
@login_required(role='store')
def vota(fidelity, dipendente_id):
    if request.method == 'POST':
        voto = int(request.form['voto'])
        with sqlite3.connect(DB) as conn:
            try:
                conn.execute("INSERT INTO voti (fidelity,dipendente_id,voto) VALUES (?,?,?)",
                             (fidelity, dipendente_id, voto))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
        return redirect(url_for('dipendenti_list', fidelity=fidelity))
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT nome,foto FROM dipendenti WHERE id=?", (dipendente_id,))
        dip = c.fetchone()
    return render_template('voto.html', fidelity=fidelity, dipendente_id=dipendente_id,
                           nome=dip[0], foto=dip[1])

# ---------------- ROUTES ADMIN ----------------
@app.route('/admin', methods=['GET', 'POST'])
@login_required(role='admin')
def admin():
    store_id = session.get('store')

    if request.method == 'POST':
        nome = request.form['nome']
        file = request.files['foto']
        if nome and file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            with sqlite3.connect(DB) as conn:
                conn.execute(
                    "INSERT INTO dipendenti (nome, foto, store_id) VALUES (?, ?, ?)",
                    (nome, filename, store_id)
                )
                conn.commit()
            return redirect(url_for('admin'))

    dip = get_dipendenti(store_id)
    return render_template('admin.html', dipendenti=dip)

@app.route('/delete/<int:dipendente_id>', methods=['POST'])
@login_required(role='admin')
def delete_dipendente(dipendente_id):
    store_id = session.get('store')
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT foto FROM dipendenti WHERE id=? AND store_id=?", (dipendente_id, store_id))
        row = c.fetchone()
        if row:
            foto = row[0]
            foto_path = os.path.join(UPLOAD_FOLDER, foto)
            if os.path.exists(foto_path):
                os.remove(foto_path)
        conn.execute("DELETE FROM dipendenti WHERE id=? AND store_id=?", (dipendente_id, store_id))
        conn.execute("DELETE FROM voti WHERE dipendente_id=?", (dipendente_id,))
        conn.commit()
    return redirect(url_for('admin'))

@app.route('/edit/<int:dipendente_id>', methods=['POST'])
@login_required(role='admin')
def edit_dipendente(dipendente_id):
    nuovo_nome = request.form['nome']
    file = request.files.get('foto')
    store_id = session.get('store')
    with sqlite3.connect(DB) as conn:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            conn.execute("UPDATE dipendenti SET nome=?, foto=? WHERE id=? AND store_id=?",
                         (nuovo_nome, filename, dipendente_id, store_id))
        else:
            conn.execute("UPDATE dipendenti SET nome=? WHERE id=? AND store_id=?",
                         (nuovo_nome, dipendente_id, store_id))
        conn.commit()
    return redirect(url_for('admin'))

@app.route('/stats')
@login_required(role='admin')
def stats():
    store_id = session.get('store')
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT d.nome, COUNT(v.voto), ROUND(AVG(v.voto),2)
            FROM dipendenti d
            LEFT JOIN voti v ON d.id=v.dipendente_id
            WHERE d.store_id=?
            GROUP BY d.id
        ''', (store_id,))
        stats = c.fetchall()
    return render_template('stats.html', stats=stats)

@app.route('/export_csv')
@login_required(role='admin')
def export_csv():
    store_id = session.get('store')
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT v.fidelity,d.nome,v.voto 
            FROM voti v JOIN dipendenti d ON v.dipendente_id=d.id 
            WHERE d.store_id=?
        ''', (store_id,))
        rows = c.fetchall()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["fidelity","dipendente","voto"])
    cw.writerows(rows)
    output = si.getvalue()

    return send_file(
        StringIO(output),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"voti_{datetime.now().strftime('%Y%m%d')}.csv"
    )

# ---------------- MAIN ----------------
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port)
