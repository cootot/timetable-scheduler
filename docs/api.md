# Timetable Scheduler API Documentation

The Timetable Scheduler exposes a RESTful API powered by Django REST Framework (DRF).

## Base URL
In local development, the API is available at:
`http://localhost:8000/api/`

---

## 1. Authentication Endpoints

### Login
`POST /api/auth/login/`
Authenticates a user and returns JWT access and refresh tokens.
- **Payload:** `{ "username": "T001", "password": "password123" }`
- **Response:** `{ "refresh": "...", "access": "..." }`

### Refresh Token
`POST /api/auth/token/refresh/`
Refreshes an expired access token using a valid refresh token.
- **Payload:** `{ "refresh": "..." }`
- **Response:** `{ "access": "..." }`

### User Profile
`GET /api/auth/user/`
Retrieves the profile and role parameters of the currently authenticated user.
- **Headers:** `Authorization: Bearer <token>`
- **Response:** 
```json
{
  "id": 1,
  "username": "T001",
  "email": "t001@mail.com",
  "role": "FACULTY",
  "is_hod": false,
  "department": "CSE"
}
```

*(See [Auth Documentation](auth.md) for full details on roles and permissions.)*

---

## 2. Scheduler & Generation Endpoints

### Trigger Generation
`POST /api/scheduler/generate`
Initiates an async algorithmic generation of the timetable. (Requires HOD/Admin).
- **Payload:**
```json
{
  "name": "Even Semester 2026",
  "semester": "even",
  "year": 3
}
```
- **Response (202 Accepted):** 
```json
{
  "schedule_id": 45,
  "status": "PENDING",
  "message": "Schedule generation queued successfully." // Or "Schedule generated synchronously"
}
```

### Check Schedule Status
`GET /api/scheduler/status/<schedule_id>/`
Returns the status of an ongoing generation task (`PENDING`, `COMPLETED`, `FAILED`).

### View Timetable
`GET /api/scheduler/timetable?schedule_id=45`
Retrieves the fully structured timetable grid for frontend rendering. 
- **Query Params:** `schedule_id` (Required), `year` (Optional), `section` (Optional).

### Publish Timetable
`POST /api/scheduler/publish/<schedule_id>/`
Approves a drafted timetable and broadcasts email notifications to all mapped faculty. (Requires Admin/HOD).

---

## 3. Analytics Endpoints

### Fetch Teacher Workload
`GET /api/scheduler/analytics/workload`
Retrieves daily and weekly load hours for all faculty mapped to the current core schedule.
- **Response:** JSON array mapping teachers against their `max_hours_per_week` and current allocated `total_hours`.

### Fetch Room Utilization
`GET /api/scheduler/analytics/rooms`
Retrieves active occupancy percentages for all physical locations (Classrooms/Labs).

---

## 4. Change Request Endpoints

### Submit Change Request
`POST /api/core/change-requests/`
Allows faculty to propose a swap or modification to an approved schedule.
- **Payload:** `{ "schedule_id": 45, "reason": "Conflict with research block", "proposed_changes": {...} }`

### Review Change Request
`PATCH /api/core/change-requests/<request_id>/`
Allows HOD to `APPROVE` or `REJECT` a pending request.
- **Payload:** `{ "status": "APPROVED", "comments": "Approved for Tuesday swap." }`

---

## 5. System Administration

### Semester Rollover
`POST /api/core/rollover/`
Triggers the archiving of all active schedules and purges mappings to prepare the platform for the next academic semester constraint mappings.

*(See [Database Documentation](database.md) for details on entity schemas.)*
