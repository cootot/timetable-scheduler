# M3 Timetable Scheduling System (Sprint 2 Final)

**Production-Ready** | Team 10 Capstone Project

---

## 🏗️ System Architecture

- **Frontend**: React + Vite
- **Backend**: Django REST Framework
- **Task Queue**: Celery + Redis
- **Database**: SQLite (Main) + Separate Audit DB

## 🚀 DevOps Setup Guide

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Redis Server (Running on localhost:6379)

### 2. Backend Initialization
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment Setup
cp .env.example .env

# Database Migrations
python manage.py migrate
python manage.py migrate --database=audit_db

# Initial Data Load
python manage.py import_data --clear
python manage.py setup_standard_users
```

### 3. Running the Application
| Component | Command |
| :--- | :--- |
| **Backend** | `python manage.py runserver` |
| **Worker** | `celery -A timetable_project worker --loglevel=info` |
| **Frontend** | `cd frontend && npm install && npm run dev` |

## 🔐 Default Access
| Role | Username | Password |
| :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` |
| **HOD** | `hod` | `hod123` |
| **Faculty** | `T001` | `faculty123` |

---
**Status**: 100% Verified Technical Handover State.
