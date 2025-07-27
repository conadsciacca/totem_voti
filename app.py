from flask import Flask, render_template, request, redirect, url_for, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from io import StringIO
import os, csv

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.secret_key = "TotemAdminPhabio@2025"

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

UPLOAD_FOLDER = os.path.join('static', 'foto')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ---------------- MODELS ----------------
class Utente(Base):
    __tablename__ = "utenti"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    store = Column(String)

class Dipendente(Base):
    __tablename__ = "dipendenti"
    id = Column(Integer, primary_key=True)
    nome = Column(String)
    foto = Column(String)
    store_id = Column(String)
    voti = relationship("Voto", back_populates="dipendente")

class Voto(Base):
    __tablename__ = "voti"
    id = Column(Integer, primary_key=True)
    fidelity = Column(String)
    dipendente_id = Column(Integer, ForeignKey("dipendenti.id"))
    voto = Column(Integer)
    dipendente = relationship("Dipendente", back_populates="voti")
    __table_args__ = (UniqueConstraint('fidelity', 'dipendente_id', name='_fidelity_dip_uc'),)

# ---------------- DB INIT ----------------
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # utenti da creare
    auto_users = [
        {
            "username": "admin_sancipirello",
            "password_env": "PWD_ADMIN_SANCIPIRELLO",
            "role": "admin",
            "store": "pdv_sancipirello"
        },
        {
            "username": "admin_sciacca",
            "password_env": "PWD_ADMIN_SCIACCA",
            "role": "admin",
            "store": "pdv_sciacca"
        },
        {
            "username": "user_sancipirello",
            "password_env": "PWD_USER_SANCIPIRELLO",
            "role": "store",
            "store": "pdv_sancipirello"
        },
        {
            "username": "user_sciacca",
            "password_env": "PWD_USER_SCIACCA",
            "role": "store",
            "store": "pdv_sciacca"
        }
    ]

    for u in auto_users:
        pwd = os.getenv(u["password_env"])
        if pwd:
            exists = db.query(Utente).filter_by(username=u["username"]).first()
            if not exists:
                hashed = generate_password_hash(pwd)
                db.add(Utente(
                    username=u["username"],
                    password=hashed,
                    role=u["role"],
                    store=u["store"]
                ))
                print(f"Creato utente {u['username']} da {u['password_env']}")
        else:
            print(f"ATTENZIONE: variabile {u['password_env']} non trovata!")
    db.commit()
    db.close()

# ---------------- UTILS ----------------
def get_dipendenti(store_id):
    db = SessionLocal()
    dip = db.query(Dipendente).filter(Dipendente.store_id == store_id).all()
    db.close()
    return dip

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- DECORATOR ----------------
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

# ---------------- LOGIN ROUTES ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        db = SessionLocal()
        u = db.query(Utente).filter(Utente.username==user).first()
        db.close()
        if u and check_password_hash(u.password, pwd):
            session['user'] = u.username
            session['role'] = u.role
            session['store'] = u.store
            return redirect(url_for('admin' if u.role=='admin' else 'index'))
        return "Credenziali errate", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- STORE ROUTES ----------------
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
    db = SessionLocal()
    votati = [v.dipendente_id for v in db.query(Voto).filter(Voto.fidelity==fidelity).all()]
    db.close()
    return render_template('dipendenti.html', dipendenti=dip, votati=votati, fidelity=fidelity)

@app.route('/vota/<fidelity>/<int:dipendente_id>', methods=['GET','POST'])
@login_required(role='store')
def vota(fidelity, dipendente_id):
    db = SessionLocal()
    if request.method == 'POST':
        voto = int(request.form['voto'])
        try:
            db.add(Voto(fidelity=fidelity, dipendente_id=dipendente_id, voto=voto))
            db.commit()
        except:
            db.rollback()
        db.close()
        return redirect(url_for('dipendenti_list', fidelity=fidelity))

    dip = db.query(Dipendente).filter(Dipendente.id==dipendente_id).first()
    db.close()
    return render_template('voto.html', fidelity=fidelity, dipendente_id=dipendente_id,
                           nome=dip.nome, foto=dip.foto)

# ---------------- ADMIN ROUTES ----------------
@app.route('/admin', methods=['GET', 'POST'])
@login_required(role='admin')
def admin():
    store_id = session.get('store')
    db = SessionLocal()

    if request.method == 'POST':
        nome = request.form['nome']
        file = request.files['foto']
        if nome and file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            db.add(Dipendente(nome=nome, foto=filename, store_id=store_id))
            db.commit()
            db.close()
            return redirect(url_for('admin'))

    dip = db.query(Dipendente).filter(Dipendente.store_id==store_id).all()
    db.close()
    return render_template('admin.html', dipendenti=dip)

@app.route('/delete/<int:dipendente_id>', methods=['POST'])
@login_required(role='admin')
def delete_dipendente(dipendente_id):
    store_id = session.get('store')
    db = SessionLocal()
    dip = db.query(Dipendente).filter(Dipendente.id==dipendente_id, Dipendente.store_id==store_id).first()
    if dip:
        foto_path = os.path.join(UPLOAD_FOLDER, dip.foto)
        if os.path.exists(foto_path):
            os.remove(foto_path)
        db.query(Voto).filter(Voto.dipendente_id==dipendente_id).delete()
        db.delete(dip)
        db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/edit/<int:dipendente_id>', methods=['POST'])
@login_required(role='admin')
def edit_dipendente(dipendente_id):
    nuovo_nome = request.form['nome']
    file = request.files.get('foto')
    store_id = session.get('store')
    db = SessionLocal()
    dip = db.query(Dipendente).filter(Dipendente.id==dipendente_id, Dipendente.store_id==store_id).first()
    if dip:
        dip.nome = nuovo_nome
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            dip.foto = filename
        db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/stats')
@login_required(role='admin')
def stats():
    store_id = session.get('store')
    db = SessionLocal()
    results = db.query(
        Dipendente.nome,
        func.count(Voto.voto),
        func.round(func.avg(Voto.voto),2)
    ).outerjoin(Voto).filter(Dipendente.store_id==store_id).group_by(Dipendente.id).all()
    db.close()
    return render_template('stats.html', stats=results)

@app.route('/export_csv')
@login_required(role='admin')
def export_csv():
    store_id = session.get('store')
    db = SessionLocal()
    rows = db.query(Voto.fidelity, Dipendente.nome, Voto.voto).join(Dipendente).filter(Dipendente.store_id==store_id).all()
    db.close()

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
init_db()
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port)
