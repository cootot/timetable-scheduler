# Timetable Scheduler [WIP]

## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
- [Architecture](#architecture)
- [The Web Dashboard](#the-web-dashboard)
- [The Generator Engine](#the-generator-engine)
- [Asynchronous & Synchronous Generation](#asynchronous--synchronous-generation)
- [Role-Based Access Control](#role-based-access-control)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [LICENSE](#license)
- [Team](#team)

More documentation available at `/docs`. See:
- [API Documentation](docs/api.md)
- [Auth Documentation](docs/auth.md)
- [Database Documentation](docs/database.md)

## Overview
Timetable Scheduler is a unified academic scheduling platform that seamlessly generates, validates, and manages university timetables mathematically. By integrating directly with institutional constraints (faculty workloads, room capacities, consecutive labs), it acts as an intelligent constraint-satisfaction engine to perfectly synchronize resources—effectively eliminating manual timetable clashes.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm
- PostgreSQL (or SQLite for dev)
- Git

### Initial Setup
Clone the repository:
```bash
git clone https://github.com/bhuvanesh-sudo/timetable-scheduler.git
cd timetable-scheduler
```

Create a `.env` file in the `backend/` directory:
```bash
cp backend/.env.example backend/.env
```

Configure backend environment variables (`backend/.env`):
```env
# Database
POSTGRES_CONNECTION_URL="postgresql://user:pass@localhost/timetable"

# Auth
SECRET_KEY="YOUR_SECRET_KEY"
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=15

# SMTP
EMAIL_HOST="smtp.gmail.com"
EMAIL_PORT=587
EMAIL_HOST_USER="your-email@gmail.com"
EMAIL_HOST_PASSWORD="your-app-password"
```

### Installation
**Backend Setup:**
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # On Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py import_data --clear  # Seed database with initial CSV data
python manage.py create_admin         # Create initial superuser
```

**Frontend Setup:**
```bash
cd frontend
npm install
```

### Local Development
**Run Backend:**
```bash
cd backend
python manage.py runserver
```

**Run Frontend:**
```bash
cd frontend
npm run dev
```


## Architecture
The platform utilizes a **React + Vite** frontend and a **Django / Django REST Framework** backend.

### The Web Dashboard
The web dashboard allows institutional users to manage academic operations effortlessly. It enables users to:
- **Log In** via role-based access tokens (Admin, HOD, Faculty).
- **Generate Timetables** using a unified modal constraint checklist.
- **View Core Analytics** such as faculty weekly workload and room utilization.
- **Manage Change Requests** from faculty seeking adjustments.
- **Export and Import** timetable mappings in CSV format.

### The Generator Engine
The core of the system resides in the Django backend (`scheduler/algorithm.py`). It uses an algorithmic constraint-satisfaction approach (backtracking search with heuristics) to map variables:
- **Entities:** Teachers, Courses (Lectures, Tutorials, Labs), Rooms, Sections.
- **Constraints:** Total teacher workload, room availability, overlapping classes, concurrent parallel electives.
- **Elective Resolution:** The engine seamlessly groups parallel elective sessions (e.g., PE1, PE2) into unified time blocks to prevent double-booking faculty mathematically.

### Asynchronous & Synchronous Generation
Because scheduling 150+ teachers and sections involves resolving millions of constraints mathematically, the API defaults to trying to delegate generation to an asynchronous background task if a Celery broker is active. However, if no broker is active, the engine safely falls back to synchronous execution within the main Python thread.
- Triggering generation creates a `PENDING` schedule entity.
- The constraint engine computes combinations and proves validity.
- Once generation resolves with zero clashes, the output writes directly to the PostgreSQL database, turning the status to `COMPLETED`.

### Role-Based Access Control
The application operates on a strict tri-tier governance model:
1. **Admin / Principal:** Has global read/write, database backup, and semester rollover powers.
2. **Head of Department (HOD):** Can trigger timetable generation, approve/deny faculty change requests, and view department workloads.
3. **Faculty:** Can only view approved generated schedules and submit change requests for conflict resolutions.

## Project Structure
```text
timetable-scheduler/
   ├── backend/                           # Django Application
   │   ├── accounts/                      # Auth, User Models, Permissions
   │   ├── core/                          # Core Data Models (Courses, etc) & Management Commands
   │   ├── scheduler/                     # Scheduling API, Algorithmic Engine & Email Tasks
   │   ├── timetable_project/             # Main Django Settings & WSGI
   │   └── manage.py
   │
   ├── frontend/                          # React + Vite Frontend
   │   ├── src/
   │   │   ├── components/                # Reusable UI Blocks (Modals, Grids)
   │   │   ├── pages/                     # Dashboard Views (Admin, HOD, Faculty)
   │   │   ├── utils/                     # API interceptors & Auth context
   │   │   └── App.jsx
   │
   ├── Datasets/                          # Raw CSV Data for seeding algorithm
   ├── docs/                              # Markdown documentation
   └── .github/workflows/                 # CI/CD Pipelines
```

## Testing
The backend is thoroughly tested using `pytest`.

```bash
# Run all backend tests
cd backend
pytest

# Run tests with coverage
pytest --cov=.

# Run specific functional test suite
pytest tests/test_algorithm.py
```

## Contributing
1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Commit your changes: `git commit -m 'feat: Add some feature'`
3. Push to the branch: `git push origin feature/your-feature-name`
4. Submit a pull request.

## LICENSE
This project is licensed under the MIT License.

## Team
- **Frontend / Backend Development:** Timetable Team
