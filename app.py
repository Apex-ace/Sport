import os
import secrets
import smtplib
from email.message import EmailMessage
import json
from datetime import datetime, date, timedelta, timezone, time
from dotenv import load_dotenv, find_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
import uuid
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship

load_dotenv(find_dotenv(), override=True)

# App Initialization
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-default-secret-key-for-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    """Sends a booking confirmation email to the user."""
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

def seed_games():
    """Populates the database with the initial set of games if it's empty."""
    if Game.query.count() == 0:
        games_data = [
            {'name': 'Table Tennis', 'max_players': 4, 'duration_minutes': 60},
            {'name': 'Badminton', 'max_players': 4, 'duration_minutes': 60},
            {'name': 'Chess', 'max_players': 2, 'duration_minutes': 45},
            {'name': 'Carrom', 'max_players': 4, 'duration_minutes': 45},
            {'name': 'Pool', 'max_players': 4, 'duration_minutes': 60},
        ]
        for g in games_data:
            db.session.add(Game(**g))
        db.session.commit()

# Make datetime object available in all templates
@app.context_processor
def inject_now():
    return {'now_utc': datetime.now(timezone.utc)}

# --- Main Routes ---
@app.route('/')
def landing():
    """Serves the landing page for guests."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('landing.html')

@app.route('/home')
@login_required
def home():
    """Serves the main dashboard for authenticated users."""
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
        if 0 <= weekday <= 3: # Monday to Thursday
            valid_slots = [time(16, 0), time(16, 30)]
        elif weekday == 4: # Friday
            valid_slots = [time(14, 0), time(14, 30), time(15, 0), time(15, 30), time(16, 0), time(16, 30)]

        if selected_time not in valid_slots:
            flash('The selected time is not a valid slot for this day.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        booking_dt = datetime.combine(selected_date, selected_time).astimezone(timezone.utc)
        
        if booking_dt < datetime.now(timezone.utc):
            flash('Cannot book a slot in the past.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        existing_booking = Booking.query.filter_by(game_id=game_id, booking_time=booking_dt).first()
        if existing_booking:
            flash(f'{game.name} is already booked for this time. Please choose another slot.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        new_booking = Booking(
            user_id=current_user.id,
            game_id=game_id,
            booking_time=booking_dt
        )
        db.session.add(new_booking)
        db.session.commit()
        
        send_booking_confirmation_email(current_user.username, game.name, booking_dt)
        flash(f'Successfully booked {game.name}! A confirmation has been sent to your email.', 'success')
        
        return redirect(url_for('profile'))

    # GET request logic
    now = datetime.now(timezone.utc)
    # Fetch all future bookings for this game to disable them on the frontend
    existing_bookings_query = Booking.query.filter(
        Booking.game_id == game_id,
        Booking.booking_time >= now
    ).all()
    booked_slots = [b.booking_time.isoformat() for b in existing_bookings_query]
    
    return render_template('book_game.html', game=game, today=date.today().isoformat(), booked_slots_json=json.dumps(booked_slots))
    
# --- Auth Routes ---
@app.route('/register')
def register():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username').lower().strip()
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, role='student', id=uuid.uuid4())
            db.session.add(user)
            flash('Welcome! Creating your account.', 'success')
        
        otp = secrets.token_hex(3).upper()
        user.otp_hash = generate_password_hash(otp)
        user.otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.session.commit()
        
        if send_otp_email(user.username, otp):
            session['username_for_verification'] = user.username
            flash('An OTP has been sent to your email.', 'info')
            return redirect(url_for('verify_otp'))
        else:
            flash('Failed to send OTP email. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    username = session.get('username_for_verification')
    if not username: return redirect(url_for('login'))
    if request.method == 'POST':
        otp = request.form.get('otp').strip()
        user = User.query.filter_by(username=username).first()
        is_valid = user and user.otp_hash and user.otp_expiry > datetime.now(timezone.utc) and check_password_hash(user.otp_hash, otp)
        if is_valid:
            user.otp_hash = None
            user.otp_expiry = None
            db.session.commit()
            login_user(user, remember=True)
            session.pop('username_for_verification', None)
            return redirect(url_for('home'))
        else:
            flash('Invalid or expired OTP.', 'danger')
    return render_template('verify_otp.html', email=username)

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
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
    
    return render_template('profile.html', bookings=bookings, stats=stats, user=current_user)

# The following block is for local development only and will not be run by Gunicorn on Render
if __name__ == '__main__':
    with app.app_context():
        # These commands should be run separately in a production environment
        print("Creating database tables...")
        db.create_all()
        print("Seeding initial game data...")
        seed_games()
    app.run(debug=True)

