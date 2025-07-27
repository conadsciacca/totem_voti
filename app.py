from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, send_file, session
import sqlite3, os, csv
from datetime import datetime
from io import StringIO

app = Flask(__name__)
app.secret_key = "scegli_una_chiave_lunga_e_casuale"

DB = 'database.db'

# ---------- FUNZIONI DB ----------
def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS dipendenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                foto TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS voti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fidelity TEXT,
                dipendente_id INTEGER,
                voto INTEGER,
                UNIQUE(fidelity,dipendente_id)
            )
        ''')
        conn.commit()

def get_dipendenti():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM dipendenti")
        return c.fetchall()

# ---------- ROUTES ----------
@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        codice = request.form['codice']
        if len(codice) == 13:
            return redirect(url_for('dipendenti_list', fidelity=codice))
    return render_template('index.html')

@app.route('/dipendenti/<fidelity>')
def dipendenti_list(fidelity):
    dip = get_dipendenti()
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT dipendente_id FROM voti WHERE fidelity=?", (fidelity,))
        votati = [row[0] for row in c.fetchall()]
    return render_template('dipendenti.html', dipendenti=dip, votati=votati, fidelity=fidelity)

@app.route('/vota/<fidelity>/<int:dipendente_id>', methods=['GET','POST'])
def vota(fidelity, dipendente_id):
    if request.method == 'POST':
        voto = int(request.form['voto'])
        with sqlite3.connect(DB) as conn:
            try:
                conn.execute("INSERT INTO voti (fidelity,dipendente_id,voto) VALUES (?,?,?)",
                             (fidelity,dipendente_id,voto))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
        return redirect(url_for('dipendenti_list', fidelity=fidelity))

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT nome,foto FROM dipendenti WHERE id=?", (dipendente_id,))
        dip = c.fetchone()
    return render_template('voto.html', fidelity=fidelity, dipendente_id=dipendente_id, nome=dip[0], foto=dip[1])

@app.route('/stats')
def stats():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT d.nome, COUNT(v.voto), ROUND(AVG(v.voto),2)
            FROM dipendenti d
            LEFT JOIN voti v ON d.id=v.dipendente_id
            GROUP BY d.id
        ''')
        stats = c.fetchall()
    return render_template('stats.html', stats=stats)

@app.route('/export_csv')
def export_csv():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT fidelity,dipendente_id,voto FROM voti')
        rows = c.fetchall()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["fidelity","dipendente_id","voto"])
    cw.writerows(rows)
    output = si.getvalue()
    return send_file(
        StringIO(output),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"voti_{datetime.now().strftime('%Y%m%d')}.csv"
    )



# <<< QUI INCOLLA LA ROUTE ADMIN E LE FUNZIONI ALLEGATE >>>
UPLOAD_FOLDER = os.path.join('static', 'foto')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        # Cambia qui user e password a piacere
        if user == 'admin' and pwd == 'mypass123':
            session['admin'] = True
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
    return redirect(url_for('login'))
    if request.method == 'POST':
        nome = request.form['nome']
        file = request.files['foto']
        if nome and file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            with sqlite3.connect(DB) as conn:
                conn.execute(
                    "INSERT INTO dipendenti (nome,foto) VALUES (?,?)",
                    (nome, filename)
                )
                conn.commit()
            return redirect(url_for('admin'))

    dip = get_dipendenti()
    return render_template('admin.html', dipendenti=dip)


@app.route('/delete/<int:dipendente_id>', methods=['POST'])
def delete_dipendente(dipendente_id):
    # Recupero il nome del file foto per eventualmente rimuoverla
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT foto FROM dipendenti WHERE id=?", (dipendente_id,))
        row = c.fetchone()
        if row:
            foto = row[0]
            foto_path = os.path.join(UPLOAD_FOLDER, foto)
            if os.path.exists(foto_path):
                os.remove(foto_path)
        # Cancello dal DB
        conn.execute("DELETE FROM dipendenti WHERE id=?", (dipendente_id,))
        conn.execute("DELETE FROM voti WHERE dipendente_id=?", (dipendente_id,))
        conn.commit()
    return redirect(url_for('admin'))


@app.route('/edit/<int:dipendente_id>', methods=['POST'])
def edit_dipendente(dipendente_id):
    nuovo_nome = request.form['nome']
    file = request.files.get('foto')

    with sqlite3.connect(DB) as conn:
        # Se è stata caricata una nuova foto, la salvo e aggiorno il DB
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            conn.execute("UPDATE dipendenti SET nome=?, foto=? WHERE id=?",
                         (nuovo_nome, filename, dipendente_id))
        else:
            # Solo modifica del nome
            conn.execute("UPDATE dipendenti SET nome=? WHERE id=?",
                         (nuovo_nome, dipendente_id))
        conn.commit()

    return redirect(url_for('admin'))


import os

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port)


