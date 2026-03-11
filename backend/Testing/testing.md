# Timetable Scheduler - Testing Documentation

This document providing a detailed breakdown of the testing suite for the Timetable Scheduler project.

## 1. Unit Testing (Module-wise)
Unit tests focus on individual components in isolation.

### A. Models (`Unit/models/`)
- **Teacher Model**:
    - **Input**: `teacher_id='T999'`, `max_hours_per_week=18`.
    - **Validation**: Ensures `max_hours_per_week` is within 0-100 range.
    - **Result**: PASSED.
- **Course Model**:
    - **Input**: Core and Lab courses with different credit/slot configurations.
    - **Result**: PASSED.

### B. Algorithm (`Unit/algorithm/`)
- **Scheduler Logic**:
    - **Input**: Set of courses, teachers, and rooms with specific constraints (e.g., theory in classroom, practical in lab).
    - **Scenarios**: Normal generation, handling impossible constraints (graceful failure).
    - **Result**: PASSED.

### C. RBAC (`Unit/rbac/`)
- **Permissions**:
    - **Input**: Test users with roles `ADMIN`, `HOD`, `FACULTY`.
    - **Validation**: Admin can create users; HOD can request changes; Faculty can only view.
    - **Result**: PASSED.

---

## 2. Integration Testing (`Integration/`)
Integration tests verify the collaboration between multiple modules.

### A. HOD/Admin Workflow
- **Scenario**: HOD submits a `ChangeRequest` for a teacher's email change.
- **Input**: `proposed_data={"email": "new@test.com"}`.
- **Flow**: HOD creates -> Admin views -> Admin approves -> Teacher model updates automatically.
- **Result**: PASSED.

---

## 3. Regression Testing (`Regression/`)
Regression tests ensure that high-level system requirements remain satisfied after code changes.

### A. Master Verification
- **Process**: Generates complete ODD and EVEN semester timetables from full datasets.
- **Input**: CSV datasets from `Datasets/` directory.
- **Metrics Verified**:
    - **Daily Coverage**: Zero faculty members with 5+ slots missing a day.
    - **Room Conflicts**: Zero theory classes scheduled in laboratory rooms.
    - **Workload**: Faculty workloads kept within optimized limits.
- **Result**: PASSED (100% resolution of daily coverage gaps).

---

## 4. End-to-End (E2E) & API Testing
### A. E2E Smoke Tests (`E2E/`)
- **Input**: API client forced-authenticating as admin.
- **Validation**: Dashboard and timetable list accessibility.
- **Result**: PASSED.

### B. API Endpoint Verification (`API/`)
- **Endpoints**: `/api/accounts/`, `/api/scheduler/`, `/api/notifications/`.
- **Validation**: CORS headers, JWT authentication, and correct JSON response formats.
- **Result**: PASSED.

---

##  Summary Table
| Category | Test Count | Status | Key Bug Fixes |
| :--- | :--- | :--- | :--- |
| **Unit** | ~60 | ✅ PASSED | Corrected Max Hours validation (100h) |
| **Integration** | 5 | ✅ PASSED | Fixed HOD permission leakage |
| **Regression** | 2 | ✅ PASSED | Optimized daily coverage logic |
| **API/E2E** | 5 | ✅ PASSED | Fixed User model import paths |
