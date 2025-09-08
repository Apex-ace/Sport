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
from sqlalchemy import func
import pytz

load_dotenv(find_dotenv(), override=True)

# App Initialization
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-default-secret-key-for-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = "441106"
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True, 'pool_recycle': 300, 'pool_timeout': 20, 'max_overflow': 0
}
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
    max_players = db.Column(db.Integer, nullable=False, default=1)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    bookings = relationship("Booking", back_populates="game")

class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('profiles.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    booking_time = db.Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = db.Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String, nullable=False, default='Confirmed')
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
    ist_tz = pytz.timezone('Asia/Kolkata')
    booking_dt_ist = booking_dt.astimezone(ist_tz)
    date_str = booking_dt_ist.strftime('%A, %B %d, %Y')
    time_str = booking_dt_ist.strftime('%I:%M %p')
    
    msg = EmailMessage()
    msg.set_content(f"""Hi {recipient_email.split('@')[0]},

Your booking for {game_name} is confirmed!

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
        'user_bookings': Booking.query.filter_by(user_id=current_user.id, status='Confirmed').count(),
        'today_bookings': Booking.query.filter(
            func.date(Booking.booking_time) == date.today(), 
            Booking.status == 'Confirmed'
        ).count()
    }
    return render_template('home.html', games=games, stats=stats)

@app.route('/book/<int:game_id>', methods=['GET', 'POST'])
@login_required
def book_game(game_id):
    game = Game.query.get_or_404(game_id)
    ist_tz = pytz.timezone('Asia/Kolkata')
    
    if request.method == 'POST':
        booking_date_str = request.form.get('booking_date')
        booking_time_str = request.form.get('booking_time')

        if not booking_date_str or not booking_time_str:
            flash('Please select both a date and a time.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        selected_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        selected_time = datetime.strptime(booking_time_str, '%H:%M').time()
        
        start_of_day_ist = ist_tz.localize(datetime.combine(selected_date, time.min))
        end_of_day_ist = ist_tz.localize(datetime.combine(selected_date, time.max))
        
        todays_bookings_count = Booking.query.filter(
            Booking.user_id == current_user.id,
            Booking.booking_time >= start_of_day_ist.astimezone(timezone.utc),
            Booking.booking_time <= end_of_day_ist.astimezone(timezone.utc),
            Booking.status == 'Confirmed'
        ).count()
        
        if todays_bookings_count >= 2:
            flash('You have already reached the maximum of two bookings for this day.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        is_new_user = Booking.query.filter_by(user_id=current_user.id).first() is None
        priority_slots = [
            (2, time(16, 0)),
            (4, time(15, 0)),
            (4, time(16, 30))
        ]
        
        if not is_new_user and (selected_date.weekday(), selected_time) in priority_slots:
            flash('This slot is reserved for new users. Please choose another.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        naive_dt = datetime.combine(selected_date, selected_time)
        booking_dt_in_ist = ist_tz.localize(naive_dt)
        booking_dt_utc = booking_dt_in_ist.astimezone(timezone.utc)
        
        if booking_dt_utc < datetime.now(timezone.utc):
            flash('Cannot book a slot in the past.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        existing_booking = Booking.query.filter_by(game_id=game_id, booking_time=booking_dt_utc, status='Confirmed').first()
        if existing_booking:
            flash(f'{game.name} is already booked for this time. Please choose another slot.', 'danger')
            return redirect(url_for('book_game', game_id=game_id))

        new_booking = Booking(user_id=current_user.id, game_id=game_id, booking_time=booking_dt_utc, status='Confirmed')
        db.session.add(new_booking)
        db.session.commit()
        
        send_booking_confirmation_email(current_user.username, game.name, booking_dt_utc)
        flash(f'Successfully booked {game.name}! A confirmation has been sent to your email.', 'success')
        
        return redirect(url_for('profile'))

    is_new_user_check = Booking.query.filter_by(user_id=current_user.id).first() is None
    now = datetime.now(timezone.utc)
    existing_bookings_query = Booking.query.filter(
        Booking.game_id == game_id, 
        Booking.booking_time >= now,
        Booking.status == 'Confirmed'
    ).all()
    booked_slots = [b.booking_time.isoformat() for b in existing_bookings_query]
    
    return render_template('book_game.html', game=game, booked_slots_json=json.dumps(booked_slots), is_new_user=json.dumps(is_new_user_check), today=date.today().isoformat())

# --- Cancellation Route ---
@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    is_owner = booking.user_id == current_user.id
    is_admin = session.get('admin_logged_in', False)

    if not is_owner and not is_admin:
        flash('You are not authorized to cancel this booking.', 'danger')
        return redirect(url_for('profile'))
    
    if booking.booking_time < datetime.now(timezone.utc) and booking.status == 'Confirmed':
        flash('Cannot cancel a booking that is in the past.', 'danger')
        return redirect(request.referrer or url_for('profile'))
        
    booking.status = 'Cancelled'
    db.session.commit()
    flash(f'The booking for {booking.game.name} has been cancelled.', 'success')
    
    return redirect(request.referrer or url_for('profile'))

# --- Auth Routes ---
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
        if user and user.otp_hash and user.otp_expiry > datetime.now(timezone.utc) and check_password_hash(user.otp_hash, otp):
            user.otp_hash = None
            user.otp_expiry = None
            db.session.commit()
            login_user(user, remember=True)
            session.pop('username_for_verification', None)
            return redirect(url_for('home'))
        else:
            flash('Invalid or expired OTP.', 'danger')
            
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
        'user_bookings': Booking.query.filter_by(user_id=current_user.id, status='Confirmed').count()
    }
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
    users = User.query.order_by(User.username).all()
    bookings = db.session.query(Booking, User, Game)\
        .join(User, Booking.user_id == User.id)\
        .join(Game, Booking.game_id == Game.id)\
        .order_by(Booking.booking_time.desc())\
        .all()
    return render_template('admin_dashboard.html', 
                         users=users, 
                         bookings=bookings)

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

    p.drawString(inch, height - inch, "Sports Room Booking Report")
    p.drawString(inch, height - inch - 20, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    y = height - inch * 2
    
    bookings = db.session.query(Booking, User, Game)\
        .join(User, Booking.user_id == User.id)\
        .join(Game, Booking.game_id == Game.id)\
        .order_by(Booking.booking_time.desc())\
        .all()
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    for booking, user, game in bookings:
        booking_dt_ist = booking.booking_time.astimezone(ist_tz)
        date_str = booking_dt_ist.strftime('%Y-%m-%d %I:%M %p')
        text = f"- {user.username} booked {game.name} for {date_str} (Status: {booking.status})"
        p.drawString(inch, y, text)
        y -= 15
        if y < inch:
            p.showPage()
            y = height - inch
            
    p.save()
    buffer.seek(0)
    
    return Response(
        buffer,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=admin_report.pdf'}
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)