# M3 Timetable Scheduling and Faculty Workload Optimization System

**Sprint 2 Ready** | Professional Academic Scheduling Platform
**Team 10** | Software Engineering Capstone Project

---

## 📋 Project Overview

The M3 Timetable Scheduling System is an intelligent scheduling platform that automatically generates conflict-free institutional timetables. The system uses constraint programming algorithms to create optimal schedules considering faculty availability, room allocation, section requirements, and workload distribution.

## 🏗️ System Architecture

The project follows a modern decoupled architecture:
- **Frontend**: React + Vite (Custom Professional Design System)
- **Backend**: Django + Django REST Framework
- **Database**: SQLite (Main) + Separate Audit Database

---

## 📁 Project Structure

```bash
timetable-scheduler/
├── backend/                    # Django Backend
│   ├── core/                  # Core Models & API
│   ├── scheduler/             # Scheduling Algorithm Logic
│   ├── tests/                 # Consolidated Testing Suite
│   ├── db.sqlite3             # Main Database
│   └── audit_db.sqlite3       # Persistent Audit Trail
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── dashboards/        # Role-specific Dashboards (Admin, HOD, Faculty)
│   │   ├── pages/             # Application Pages
│   │   ├── services/          # API Integration Layer
│   │   └── __tests__/         # Frontend Component Tests
│   └── package.json
├── Datasets/                   # Core CSV Datasets for Institutional Data
├── docs/                       # Project Documentation & UML Diagrams
│   ├── API_DOCUMENTATION.md   # Complete REST API reference
│   ├── DEV_DOCUMENTATION.md   # Developer setup & architecture guide
│   └── USER_DOCUMENTATION.md  # Guide for Admins, HODs, and Faculty
└── README.md                   # This file
```

---

## 🚀 Setup & Execution

### Backend Setup
1. `cd backend`
2. `python3 -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python manage.py migrate`
6. `python manage.py migrate --database=audit_db`
7. `python manage.py import_data --clear`
8. `python manage.py runserver`

### Frontend Setup
1. `cd frontend`
2. `npm install`
3. `npm run dev`

---

## 🧪 Testing

The project includes a comprehensive consolidated testing suite:

**Backend**:
- Run all tests: `cd backend && pytest tests/ -v`
- Available modules: `rbac/`, `data_ingestion/`, `algorithm/`, `core/`

**Frontend**:
- Run tests: `cd frontend && npm test`

---

## 👥 Team 10
- **Vamsi (505)** - Backend & Algorithm
- **Bhuvanesh (544)** - Frontend & UI/UX
- **Akshitha (555)** - Algorithm & Support
- **Kanishthika (520)** - Quality Assurance
- **Karthikeyan (539)** - DevOps & Structure

---
**Status**: CLEANED & ORGANIZED (Ready for further development)
