# Sports Room Booking  

A **modern, responsive web application** for booking indoor sports facilities.  
Built with a **Flask backend** and a **Supabase PostgreSQL database**, it delivers a **seamless, passwordless user experience** and a **complete admin panel** for managing data efficiently.  

🔗 **[Live Demo](https://sport-nhbk.onrender.com)**  

---

##  Key Features  

- ** Passwordless OTP Login**  
  - Secure, email-based one-time password authentication.  
  - New users are automatically registered on their first login attempt.  

- ** Dynamic Booking System**  
  - Clean, responsive interface for browsing available games.  
  - Book predefined time slots in real time.  
  - **No double-bookings** — real-time slot availability checks.  
  - Automatic confirmation emails for successful bookings.  

- ** User Profile Page**  
  - Users can view **upcoming** and **past bookings** in a neat timeline.  

- ** Admin Panel**  
  - Secure, password-protected dashboard for admins.  
  - View all registered users.  
  - Access complete booking logs.  
  - Download **comprehensive PDF reports** of users & bookings.  

---

##  Technology Stack  

**Backend:** Python, Flask, Gunicorn  
**Database:** Supabase (PostgreSQL)  
**ORM:** Flask-SQLAlchemy  
**Frontend:** HTML, Tailwind CSS, Jinja2  
**Authentication:** Flask-Login + custom OTP logic  
**Reports:** ReportLab for PDF generation  

---

## ⚡ Getting Started  

###  Prerequisites  
- Python **3.10+**  
- Supabase account (PostgreSQL database)  
- SMTP provider (SendGrid, Mailgun, etc.) for sending emails  

---

###  Local Development Setup  

1. **Clone the repository**  
   ```bash
   git clone https://github.com/your-username/jit-sports-booking.git
   cd jit-sports-booking