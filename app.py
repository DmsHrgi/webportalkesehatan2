from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from dotenv import load_dotenv

# Load env
load_dotenv()

app = Flask(__name__)

# =====================
# CONFIG
# =====================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///healthcare_portal.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# ⛔ VERCEL FILESYSTEM IS READ-ONLY
# Upload DIMATIKAN khusus di Vercel
if os.getenv("VERCEL"):
    app.config['UPLOAD_FOLDER'] = None
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# =====================
# INIT EXTENSIONS
# =====================
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# =====================
# MODELS
# =====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    age_group = db.Column(db.Enum('18-34', '35-49', '50-64', '65-74', '≥75'), nullable=False)
    birth_sex = db.Column(db.Enum('Male', 'Female'), nullable=False)
    numeracy_score = db.Column(db.Enum('Very easy', 'Easy', 'Hard'), nullable=False)
    health_literacy_level = db.Column(db.Enum('High', 'Medium', 'Low'), nullable=False)
    preferred_access_mode = db.Column(db.Enum('Website only', 'App only', 'Both'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    provider_name = db.Column(db.String(200), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('Scheduled', 'Confirmed', 'Completed', 'Cancelled'), default='Scheduled')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)

# =====================
# LOGIN
# =====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =====================
# ROUTES
# =====================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Email atau password salah')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email sudah terdaftar')
            return redirect(url_for('register'))

        user = User(
            email=request.form.get('email'),
            age_group=request.form.get('age_group'),
            birth_sex=request.form.get('birth_sex'),
            numeracy_score=request.form.get('numeracy_score'),
            health_literacy_level=request.form.get('health_literacy_level'),
            preferred_access_mode=request.form.get('preferred_access_mode')
        )
        user.set_password(request.form.get('password'))

        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/dashboard')
@login_required
def dashboard():
    appointments = Appointment.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', appointments=appointments)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    # ⛔ Upload dimatikan di Vercel
    if app.config['UPLOAD_FOLDER'] is None:
        flash('Fitur upload tidak tersedia di server ini')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('File tidak valid')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        doc = Document(
            user_id=current_user.id,
            filename=filename,
            original_filename=file.filename,
            file_type=file.content_type,
            file_size=os.path.getsize(path),
            description=request.form.get('description')
        )
        db.session.add(doc)
        db.session.commit()

        flash('File berhasil diupload')
        return redirect(url_for('dashboard'))

    return render_template('upload.html')

# =====================
# ENTRY POINT
# =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
