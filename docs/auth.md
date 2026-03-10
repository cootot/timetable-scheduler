# Timetable Scheduler Authentication & Authorization

The Timetable Scheduler platform operates strictly on a **Role-Based Access Control (RBAC)** architecture utilizing **JSON Web Tokens (JWT)**.

## 1. Authentication Strategy

**Method:** `Bearer Token` based validation using `djangorestframework-simplejwt`.

- Access tokens are configured to expire in **15 minutes**.
- Refresh tokens are configured to expire in **7 days**.
- The `Accounts` application overrides the default Django authentication to map closely to academic identities.

### Standard Login Flow
1. **User Client** authenticates with username (Teacher ID) and raw password at `/api/auth/login`.
2. **Django Backend** validates credentials and returns a signed HS256 JWT access payload containing the `user_id` and role permissions.
3. **React Client** stores the token in `localStorage` and appends it to all subsequent API `Authorization` headers.

## 2. The Identity Model (`CustomUser`)

The backend abstracts authentication through a custom user model `User` integrating directly with the `Teacher` domain model.

**Key Fields in Identity:**
- `username`: Academic ID (e.g., "T001").
- `email`: Institutional email.
- `role`: Enum string matching permissions.
- `department`: Linked automatically to the matched Teacher object.

## 3. Organizational Roles & Permissions

The application implements three hardened permission tiers managed via custom DRF decorators in `/accounts/permissions.py`:

### Tier 1: System Admin / Principal
*Absolute global access.*
- **Identifier:** `role='ADMIN'` or Django `is_superuser=True`.
- **Capabilities:**
  - Complete read/write access to all endpoints.
  - Trigger Semester Rollovers (archiving old timetables, wiping active schedules).
  - Execute full Database Backups and Restores.
  - Force Publish any draft schedule without review.

### Tier 2: Head of Department (HOD)
*Departmental oversight access.*
- **Identifier:** `is_hod=True`.
- **Capabilities:**
  - View all schedules irrespective of assignment.
  - View global Workload Analytics and Room Utilization dashboards.
  - **Trigger Timetable Generation Algorithms.**
  - **Approve or Deny Change Requests** submitted by faculty in their department.
  - Grant read-only access to historical archives.
- **REST Decorator:** `@permission_classes([IsHODOrAdmin])`

### Tier 3: General Faculty
*Standard user access.*
- **Identifier:** Regular `Teacher` entry.
- **Capabilities:**
  - View published Timetables (read-only grids).
  - Check their own weekly allocated Workloads.
  - **Submit Timetable Change Requests** (e.g., asking to swap PE2 to an afternoon slot).
  - Receive automated SMTP email alerts when an applicable schedule is generated.
- **REST Decorator:** `@permission_classes([IsFacultyOrAbove])`

## 4. Securing Views

All API endpoints enforcing role validations implement DRF’s decorator pipeline:

```python
from accounts.permissions import IsHODOrAdmin

@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def trigger_generation(request):
    # Only Admin or HOD can initiate the Celery generation task
    pass
```

## 5. Security Measures
- **Password Hashing:** Django’s native `Argon2` or `PBKDF2` hashing is enforced.
- **CSRF Protection:** Managed seamlessly by Vite + DRF proxy settings during form POST operations.
- **Stateless Verification:** Backend maintains no session state; validation strictly relies on JWT cryptographic signatures preventing horizontal payload tampering.
