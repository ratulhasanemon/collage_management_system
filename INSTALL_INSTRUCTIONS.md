# Multi-Role Dashboards & Permissions — Setup Guide

This adds a new, self-contained Django app called **`accounts`**. It does
**not** modify `models.py`, `views.py`, `urls.py`, or `admin.py` from your
existing app — everything is additive:

```
accounts/
  __init__.py
  apps.py
  models.py          # UserProfile (role + optional link to Teacher/Student)
  decorators.py       # role_required() for the new views
  middleware.py        # ROLE_PERMISSIONS map — this is what actually locks
                       # down your existing routes, without touching them
  views.py             # login, logout, and 4 dashboard views
  urls.py
  admin.py             # registers UserProfile in /admin/
  templates/accounts/
    login.html
    base_dashboard.html
    teacher_dashboard.html
    student_dashboard.html
    accountant_dashboard.html
```

## 1. Copy the app in

Drop the `accounts/` folder next to your existing app (the one with the
`models.py` you shared) at the project root, alongside `manage.py`.

## 2. Rename one placeholder

Your existing app's name wasn't in the files you shared, so `accounts`
refers to it as `"core"` in two places. Open these two files and change
`CORE_APP = "core"` to your app's real name (the app label you use in
`INSTALLED_APPS`, e.g. `"school"`, `"management"`, etc.):

- `accounts/models.py`
- `accounts/middleware.py`

## 3. `settings.py` changes

```python
INSTALLED_APPS = [
    ...
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "your_existing_app",
    "accounts",              # add this
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.RoleBasedAccessMiddleware",   # add this, LAST
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "role_dashboard"
LOGOUT_REDIRECT_URL = "login"
```

## 4. Project `urls.py` changes

Add one include line — your existing app's `urls.py` is untouched:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("your_existing_app.urls")),
]
```

## 5. Migrate

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

## 6. Create accounts and assign roles

Do this in `/admin/` (Django admin, auto-registered by `accounts/admin.py`):

1. Create a `User` for each person under **Authentication and
   Authorization → Users** (or reuse existing ones).
2. Go to **Accounts & Roles → User Profiles → Add**, pick the `User`, set
   `role`, and — for Teacher/Student roles — link the matching `Teacher` or
   `Student` row. This link is what makes a teacher's/student's own pages
   (receipts, ID card, marksheet, attendance) show *their* data only.
3. For your own admin login, either mark the `User` as **superuser** (bypasses
   the role system entirely, same as today), or give it a `UserProfile` with
   `role=Admin`.

Accountant accounts don't need a Teacher/Student link — leave both blank.

## 7. Try it

Visit `/login/`. Each role lands somewhere different after signing in:

| Role | Redirects to | Can reach |
|---|---|---|
| Admin / superuser | `/` (your existing `index` dashboard, unchanged) | everything |
| Accountant | `/accountant-dashboard/` | fees, salary, transactions, fee structure, transport fee |
| Teacher | `/teacher-dashboard/` | own routine, own salary receipts, own attendance, exam-marks entry, marking student attendance |
| Student | `/student-dashboard/` | own fee receipts, own routine, own marks, own attendance, own ID card |

Anonymous visitors get redirected to `/login/` for every page except the
login page itself. Logged-in users who hit a page outside their role get a
403 (Django's default "Forbidden" page — style it with a `403.html` in your
templates folder if you'd like a branded version).

## How the permission model works (so you can extend it safely)

All the access rules live in **one file**: `accounts/middleware.py`,
specifically the `ROLE_PERMISSIONS` dict (which roles can reach which
`url_name`) and `OWNERSHIP_CHECK_URL_NAMES` / `_is_owner()` (which pages are
further restricted to "your own record only" — e.g. a student hitting
`/fee/17/receipt/` only succeeds if fee #17 belongs to *them*).

To open up or lock down a route later, edit that one dict — no need to
touch `views.py`, `urls.py`, or add decorators anywhere else.

## Notes / things you may want to add later

- **Sidebar logout link in your existing `index.html`**: since admins now
  log in too, you may want to add a "Sign Out" link there pointing at
  `{% url 'logout' %}`. Not required for the permission system to work —
  purely a UX nicety. I left your `index.html` untouched since it wasn't
  part of this request.
- **Self-service editing**: `edit_student` / `edit_teacher` are currently
  admin-only. If you want students/teachers to edit their own contact info,
  add `edit_student`/`edit_teacher` to `OWNERSHIP_CHECK_URL_NAMES` and a
  matching branch in `_is_owner()` (same pattern as the existing entries).
- **Custom 403 page**: add a `templates/403.html` at your project's
  template root for a branded "Access Denied" screen instead of Django's
  default one.
