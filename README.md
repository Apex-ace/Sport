Sports Room Booking
--------------------

A modern, responsive web application for booking indoor sports games. 
Built with a Flask backend and a Supabase PostgreSQL database, this application provides a seamless, passwordless user experience and a complete admin panel for data management.

Live Demo  https://sport-nhbk.onrender.com


✨ Key Features

Passwordless OTP Login: Secure and user-friendly email-based one-time password authentication. New users are registered automatically on their first login attempt.

Dynamic Booking System: An intuitive, responsive interface for viewing available games and booking them at predefined time slots.

Real-time slot availability checking prevents double-booking.Automatic booking confirmation emails are sent to users upon success.

User Profile Page: A dedicated page for users to view their upcoming and past bookings in a clean, organized list.

Comprehensive Admin Panel: A separate, password-protected dashboard for administrators to manage the platform.View a complete list of all registered users.View a detailed log of all bookings made across the platform.Download a comprehensive PDF report of all users and their bookings.

🚀 Technology StackBackend: 
-----------
Python, Flask, GunicornDatabase: Supabase (PostgreSQL)ORM: Flask-SQLAlchemyFrontend: HTML, Tailwind CSS, Jinja2Authentication: 

Flask-Login for session management, with a custom OTP logic.PDF Generation: ReportLab for creating downloadable admin reports.

Getting Started
---------

Prerequisites Python 3.10 or newerA Supabase account for the database.

An SMTP provider (like SendGrid or Mailgun) for sending emails.Local Development 

SetupClone the repository:git clone [https://github.com/your-username/jit-sports-booking.git](https://github.com/your-username/jit-sports-booking.git)

cd jit-sports-booking

Create and activate a virtual environment:python3 -m venv venv
source venv/bin/activate

Install dependencies:pip install -r requirements.txt

Set up Environment Variables:Create a .env file in the project root and add your credentials:SECRET_KEY='a_long_and_random_secret_string_for_sessions'

DATABASE_URL='postgresql://postgres:[YOUR-PASSWORD]@[YOUR-SUPABASE-HOST]:5432/postgres'

SMTP_SERVER='smtp.example.com'

SMTP_PORT=587
SMTP_USERNAME='your-smtp-username'

SMTP_PASSWORD='your-smtp-password'

MAIL_SENDER='noreply@yourdomain.com'

Set up the Database Schema:Navigate to the SQL Editor in your Supabase project.Copy the contents of supabase_schema.sql and run it to create the necessary tables and policies.Run the application:python app.py

The application will be running at http://127.0.0.1:5000.

Your application should now be live and fully functional.