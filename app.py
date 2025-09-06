# Import necessary libraries
import os
import secrets
import smtplib
from email.message import EmailMessage
import json
from datetime import datetime, date, timedelta, timezone, time
from dotenv import load_dotenv, find_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, Response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
import uuid
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

load_dotenv(find_dotenv(), override=True)

# App Initialization
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-default-secret-key-for-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = "441106"
# Database connection pool configuration
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}
# SMTP Configuration
app.config['SMTP_SERVER'] = os.getenv('SMTP_SERVER')
app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', 587))
app.config['SMTP_USERNAME'] = os.getenv('SMTP_USERNAME')
app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD')
app.config['MAIL_SENDER'] = os.getenv('MAIL_SENDER', 'noreply@jitsports.com')

# --- Extensions Initialization ---
csrf = CSRFProtect(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'profiles'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String, unique=True, nullable=False)
    role = db.Column(db.String, nullable=False, default='student')
    profile_picture = db.Column(db.String)
    otp_hash = db.Column(db.String)
    otp_expiry = db.Column(TIMESTAMP(timezone=True))
    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")

class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    max_players = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    bookings = relationship("Booking", back_populates="game")

class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('profiles.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    booking_time = db.Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = db.Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="bookings")
    game = relationship("Game", back_populates="bookings")

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(uuid.UUID(user_id))
    except (ValueError, TypeError):
        return None

# --- Helper Functions ---
def send_otp_email(recipient_email, otp):
    msg = EmailMessage()
    msg.set_content(f"Your One-Time Password (OTP) is: {otp}\nThis code will expire in 5 minutes.")
    msg['Subject'] = 'Your Sports Room Login OTP'
    msg['From'] = app.config['MAIL_SENDER']
    msg['To'] = recipient_email
    try:
        server = smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT'])
        server.starttls()
        server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"--- SMTP ERROR: {e} ---")
        return False

def send_booking_confirmation_email(recipient_email, game_name, booking_dt):
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    booking_dt_ist = booking_dt.astimezone(ist_tz)
    date_str = booking_dt_ist.strftime('%A, %B %d, %Y')
    time_str = booking_dt_ist.strftime('%I:%M %p')
    msg = EmailMessage()
    msg.set_content(f"""Hi {recipient_email.split('@')[0]},
Your booking is confirmed!

Game: {game_name}
Date: {date_str}
Time: {time_str}

We look forward to seeing you.
Thanks,
The Sports Room Team""")
    msg['Subject'] = f'Booking Confirmation for {game_name}'
    msg['From'] = app.config['MAIL_SENDER']
    msg['To'] = recipient_email
    try:
        server = smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT'])
        server.starttls()
        server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"--- SMTP Booking Confirmation ERROR: {e} ---")
        return False

# --- Context Processors ---
@app.context_processor
def inject_now():
    return {'now_utc': datetime.now(timezone.utc), 'timezone': timezone, 'timedelta': timedelta}

# --- Main Routes ---
@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('landing.html')

@app.route('/home')
@login_required
def home():
    games = Game.query.order_by(Game.name).all()
    stats = {
        'total_games': Game.query.count(),
        'user_bookings': Booking.query.filter_by(user_id=current_user.id).count(),
        'today_bookings': Booking.query.filter(db.func.date(Booking.booking_time) == date.today()).count()
    }
    return render_template('home.html', games=games, stats=stats)

@app.route('/book/<int:game_id>', methods=['GET', 'POST'])
@login_required
def book_game(game_id):
    game = Game.query.get_or_404(game_id)
    if request.method == 'POST':
        booking_date_str = request.form.get('booking_date')
        booking_time_str = request.form.get('booking_time')

        if not booking_date_str or not booking_time_str:
            flash('Please select both a date and a time.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        selected_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        selected_time = datetime.strptime(booking_time_str, '%H:%M').time()
        weekday = selected_date.weekday()

        valid_slots = []
        if 0 <= weekday <= 3:
            valid_slots = [time(16, 0), time(16, 30)]
        elif weekday == 4:
            valid_slots = [time(14, 0), time(14, 30), time(15, 0), time(15, 30), time(16, 0), time(16, 30)]

        if selected_time not in valid_slots:
            flash('The selected time is not a valid slot for this day.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        ist_tz = timezone(timedelta(hours=5, minutes=30))
        naive_dt = datetime.combine(selected_date, selected_time)
        booking_dt_in_ist = naive_dt.replace(tzinfo=ist_tz)
        booking_dt = booking_dt_in_ist.astimezone(timezone.utc)
        
        if booking_dt < datetime.now(timezone.utc):
            flash('Cannot book a slot in the past.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        existing_booking = Booking.query.filter_by(game_id=game_id, booking_time=booking_dt).first()
        if existing_booking:
            flash(f'{game.name} is already booked for this time. Please choose another slot.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        new_booking = Booking(user_id=current_user.id, game_id=game_id, booking_time=booking_dt)
        db.session.add(new_booking)
        db.session.commit()
        
        send_booking_confirmation_email(current_user.username, game.name, booking_dt)
        flash(f'Successfully booked {game.name}! A confirmation has been sent to your email.', 'success')
        
        return redirect(url_for('profile'))

    today = date.today()
    next_seven_days = []
    for i in range(7):
        day = today + timedelta(days=i)
        next_seven_days.append({
            "iso_date": day.isoformat(),
            "day_name": day.strftime("%a"),
            "short_date": day.strftime("%d %b")
        })
    
    now = datetime.now(timezone.utc)
    existing_bookings_query = Booking.query.filter(Booking.game_id == game_id, Booking.booking_time >= now).all()
    booked_slots = [b.booking_time.isoformat() for b in existing_bookings_query]
    
    return render_template('book_game.html', game=game, next_seven_days=next_seven_days, booked_slots_json=json.dumps(booked_slots))

# --- Database Helper Functions ---
def db_retry_operation(operation, max_retries=3):
    """Retry database operations with exponential backoff for connection issues"""
    import time
    from sqlalchemy.exc import OperationalError
    
    for attempt in range(max_retries):
        try:
            return operation()
        except OperationalError as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Database connection error (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
            # Attempt to refresh the connection
            try:
                db.session.rollback()
                db.session.close()
            except:
                pass

# --- Auth Routes ---
@app.route('/register')
def register():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username').lower().strip()
        
        def get_or_create_user():
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, role='student', id=uuid.uuid4())
                db.session.add(user)
                flash('Welcome! Creating your account.', 'success')
            return user
        
        try:
            user = db_retry_operation(get_or_create_user)
            
            otp = secrets.token_hex(3).upper()
            user.otp_hash = generate_password_hash(otp)
            user.otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
            
            def commit_changes():
                db.session.commit()
                return True
            
            db_retry_operation(commit_changes)
            
            if send_otp_email(user.username, otp):
                session['username_for_verification'] = user.username
                flash('An OTP has been sent to your email.', 'info')
                return redirect(url_for('verify_otp'))
            else:
                flash('Failed to send OTP email. Please try again.', 'danger')
                
        except Exception as e:
            print(f"Login database error: {e}")
            flash('Database connection issue. Please try again in a moment.', 'danger')
            try:
                db.session.rollback()
            except:
                pass
                
    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    username = session.get('username_for_verification')
    if not username: return redirect(url_for('login'))
    if request.method == 'POST':
        otp = request.form.get('otp').strip()
        
        try:
            def verify_and_login():
                user = User.query.filter_by(username=username).first()
                is_valid = user and user.otp_hash and user.otp_expiry > datetime.now(timezone.utc) and check_password_hash(user.otp_hash, otp)
                if is_valid:
                    user.otp_hash = None
                    user.otp_expiry = None
                    db.session.commit()
                    login_user(user, remember=True)
                    session.pop('username_for_verification', None)
                    return True
                return False
            
            if db_retry_operation(verify_and_login):
                return redirect(url_for('home'))
            else:
                flash('Invalid or expired OTP.', 'danger')
                
        except Exception as e:
            print(f"OTP verification database error: {e}")
            flash('Database connection issue. Please try again.', 'danger')
            try:
                db.session.rollback()
            except:
                pass
                
    return render_template('verify_otp.html', email=username)

# --- Logout Routes ---
@app.route('/logout/confirm')
@login_required
def logout_confirm():
    return render_template('logout_confirm.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('landing'))

# --- Profile Route ---
@app.route('/profile')
@login_required
def profile():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.booking_time.desc()).all()
    stats = {
        'total_games': Game.query.count(),
        'user_bookings': len(bookings),
        'today_bookings': Booking.query.filter(db.func.date(Booking.booking_time) == date.today()).count()
    }
    # The context_processor handles passing timezone info, so no need to pass it explicitly here.
    return render_template('profile.html', 
                         bookings=bookings, 
                         stats=stats, 
                         user=current_user)

# --- Admin Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    try:
        def get_dashboard_data():
            users = User.query.order_by(User.username).all()
            bookings = db.session.query(Booking, User, Game)\
                .join(User, Booking.user_id == User.id)\
                .join(Game, Booking.game_id == Game.id)\
                .order_by(Booking.booking_time.desc())\
                .all()
            return users, bookings
        
        users, bookings = db_retry_operation(get_dashboard_data)
        
        return render_template('admin_dashboard.html', 
                             users=users, 
                             bookings=bookings,
                             timezone=timezone,
                             timedelta=timedelta)
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('admin_dashboard.html', 
                             users=[], 
                             bookings=[],
                             timezone=timezone,
                             timedelta=timedelta)

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out of the admin panel.', 'info')
    return redirect(url_for('landing'))

@app.route('/admin/download_report')
def download_report():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.drawString(inch, height - inch, "Sports Room Booking - Admin Report")
    p.drawString(inch, height - inch - 20, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    y_position = height - inch * 2
    p.drawString(inch, y_position, "Registered Users")
    y_position -= 20
    p.line(inch, y_position, width - inch, y_position)
    y_position -= 15
    
    users = User.query.order_by(User.username).all()
    for user in users:
        p.drawString(inch * 1.1, y_position, f"- {user.username} (Role: {user.role})")
        y_position -= 15
        if y_position < inch:
            p.showPage()
            y_position = height - inch

    y_position -= 30
    p.drawString(inch, y_position, "All Bookings")
    y_position -= 20
    p.line(inch, y_position, width - inch, y_position)
    y_position -= 15

    bookings = db.session.query(Booking, User, Game)\
        .join(User, Booking.user_id == User.id)\
        .join(Game, Booking.game_id == Game.id)\
        .order_by(Booking.booking_time.desc())\
        .all()
    
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    for booking, user, game in bookings:
        booking_dt_ist = booking.booking_time.astimezone(ist_tz)
        date_str = booking_dt_ist.strftime('%Y-%m-%d %I:%M %p')
        text = f"- {user.username} booked {game.name} for {date_str}"
        p.drawString(inch * 1.1, y_position, text)
        y_position -= 15
        if y_position < inch:
            p.showPage()
            y_position = height - inch
            
    p.save()
    buffer.seek(0)
    
    return Response(
        buffer,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=admin_report.pdf'}
    )

# The following block is for local development only and will not be run by Gunicorn on Render
if __name__ == '__main__':
    with app.app_context():
        # These commands should be run separately in a production environment
        # using a one-time script or shell command.
        print("Creating database tables if they don't exist...")
        db.create_all()
        print("Seeding initial game data if the table is empty...")
        # seed_games() # You can uncomment this if you want to seed games on every local run
    app.run(debug=True)

