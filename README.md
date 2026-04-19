# 🗳️ SecureVote — Online Voting System

A scalable, secure Online Voting System built with Django REST Framework + HTML/CSS/JS frontend. Supports National, State, and Village level elections.

## ⚡ Quick Start (Local Development)

```bash
# 1. Clone & enter project
cd Secure-online-voting-system

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers celery redis Pillow

# 4. Run migrations
cd Home
python manage.py makemigrations accounts elections voting results notifications
python manage.py migrate

# 5. Create admin user
python manage.py createsuperuser

# 6. Start server
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## 🐳 Docker Deployment

```bash
docker-compose up --build
```

This starts: Django + Gunicorn, PostgreSQL, Redis, Celery Worker, Nginx on port 80.

## 📁 Project Structure

```
Home/
├── accounts/        # User auth, JWT, OTP, profiles
├── elections/       # Election & Candidate CRUD
├── voting/          # Anonymous vote casting (SHA-256)
├── results/         # Auto vote tallying & winner
├── notifications/   # Celery async notifications
├── frontend/        # HTML/CSS/JS pages
│   ├── css/style.css
│   ├── js/api.js
│   ├── index.html       (Login/Register)
│   ├── dashboard.html   (User Dashboard)
│   ├── elections.html   (Browse Elections)
│   ├── vote.html        (Cast Vote)
│   ├── results.html     (View Results)
│   └── admin.html       (Admin Panel)
└── Home/            # Django project config
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register/` | POST | Register new user |
| `/api/auth/login/` | POST | Login (JWT) |
| `/api/auth/otp-verify/` | POST | Verify OTP |
| `/api/auth/profile/` | GET/PATCH | User profile |
| `/api/elections/elections/` | GET/POST | List/Create elections |
| `/api/elections/elections/active/` | GET | Active elections |
| `/api/elections/elections/eligible/` | GET | Eligible for user |
| `/api/elections/candidates/` | GET/POST | Manage candidates |
| `/api/voting/cast/` | POST | Cast vote |
| `/api/voting/status/<id>/` | GET | Check vote status |
| `/api/results/<id>/` | GET | Election results |
| `/api/notifications/` | GET | User notifications |

## 🔐 Security

- **JWT Authentication** with access/refresh tokens
- **SHA-256 Vote Hashing** for integrity
- **Anonymous Voting** — Vote table has no user FK
- **Transaction-safe** writes with duplicate prevention
- **Rate Limiting** — 30 req/min anon, 120 req/min auth
- **CORS** configured for cross-origin requests

## 👤 Default Admin

- **Email**: admin@vote.com
- **Password**: admin123
