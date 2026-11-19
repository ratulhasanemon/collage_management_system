"""
Centralized route permissions for the College Management System.
(See earlier version's module docstring for full rationale — unchanged.)
"""

from django.apps import apps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import UserProfile

CORE_APP = "app"  # keep in sync with accounts/models.py

ADMIN = UserProfile.ROLE_ADMIN
ACCOUNTANT = UserProfile.ROLE_ACCOUNTANT
TEACHER = UserProfile.ROLE_TEACHER
STUDENT = UserProfile.ROLE_STUDENT

PUBLIC_URL_NAMES = {
    "login",
    "teacher_register",
    "student_register",
}

COMMON_AUTHENTICATED_URL_NAMES = {
    "role_dashboard",
    "logout",
    "teacher_dashboard",
    "student_dashboard",
    "accountant_dashboard",
}

SOFT_REDIRECT_URL_NAMES = {
    "index",
}

ROLE_PERMISSIONS = {
    # ---- Core admin dashboard & directory management ----
    "index": (),
    "add_teacher": (),
    "add_student": (),

    # ---- People management (admin only) ----
    "edit_student": (),
    "delete_student": (),
    "edit_teacher": (),
    "delete_teacher": (),

    # ---- Teacher read-only access to student directory ----
    "student_directory": (TEACHER,),

    # ---- Exam routine viewing, read-only ----
    "get_exam_routine": (TEACHER, STUDENT),

    # ---- Profile (own record only, no pk in URL) ----
    "profile": (TEACHER, STUDENT),

    # ---- Class routine viewing, read-only, filtered to the caller's own
    # ---- classes (teacher) or own department/shift/semester (student) ----
    "get_class_routine": (TEACHER, STUDENT),

    # ---- Teacher self-service pages ----
    "my_attendance": (TEACHER,),
    "mark_student_attendance_form": (TEACHER,),
    "enter_exam_marks_form": (TEACHER,),

    # ---- Notification bell (teacher + student dashboards) ----
    "mark_notices_seen": (TEACHER, STUDENT),

    # ---- Finance: admin + accountant run these ----
    "add_fee": (ACCOUNTANT,),
    "add_fee_structure": (ACCOUNTANT,),
    "add_transaction": (ACCOUNTANT,),
    "pay_salary": (ACCOUNTANT,),
    "add_transport_fee": (ACCOUNTANT,),

    # ---- Finance: viewing a receipt/voucher is also allowed for the
    # ---- specific person it belongs to (enforced by _is_owner below) ----
    "fee_receipt": (ACCOUNTANT, STUDENT),
    "salary_receipt": (ACCOUNTANT, TEACHER),

    # ---- Scheduling (admin only to create/delete) ----
    "add_routine": (),
    "delete_routine": (),
    "add_exam_routine": (),
    "delete_exam_routine": (),

    # ---- Exam marks: admin + teachers enter marks ----
    "add_exam_marks": (TEACHER,),
    "get_student_marksheet": (TEACHER, STUDENT),

    # ---- ID cards ----
    "student_id_card": (TEACHER, STUDENT),
    "teacher_id_card": (TEACHER, STUDENT),

    # ---- Attendance ----
    "mark_student_attendance": (TEACHER,),
    "mark_teacher_attendance": (),
    "get_student_attendance_report": (TEACHER, STUDENT),
    "get_teacher_attendance_report": (TEACHER,),

    # ---- Notices: admin broadcasts; teachers can also broadcast ----
    "notice_broadcaster": (TEACHER,),

    # ---- Library (admin manages catalog/issues) ----
    "add_book": (),
    "edit_book": (),
    "delete_book": (),
    "issue_book": (),
    "return_book": (),

    # ---- Hostel management (admin only) ----
    "add_hostel": (),
    "edit_hostel": (),
    "delete_hostel": (),
    "add_hostel_room": (),
    "edit_hostel_room": (),
    "delete_hostel_room": (),
    "allocate_hostel_seat": (),
    "vacate_hostel_seat": (),
    "delete_hostel_allocation": (),

    # ---- Transport management (admin only, accountant collects fees) ----
    "add_bus_route": (),
    "edit_bus_route": (),
    "delete_bus_route": (),
    "add_bus_stop": (),
    "delete_bus_stop": (),
    "allocate_transport": (),
    "deactivate_transport": (),
    "delete_transport_allocation": (),
    
    "update_profile": (TEACHER, STUDENT),
    "change_password": (TEACHER, STUDENT),
}

OWNERSHIP_CHECK_URL_NAMES = {
    "fee_receipt",
    "salary_receipt",
    "get_student_marksheet",
    "student_id_card",
    "get_student_attendance_report",
    "teacher_id_card",
    "get_teacher_attendance_report",
}


def _model(name):
    return apps.get_model(CORE_APP, name)


def _is_owner(url_name, profile, view_kwargs):
    pk = view_kwargs.get("pk")
    if pk is None:
        return True
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return False

    if url_name in ("get_student_marksheet", "student_id_card", "get_student_attendance_report"):
        if profile.role == TEACHER:
            return True
        return profile.role == STUDENT and profile.student_id == pk

    if url_name in ("teacher_id_card", "get_teacher_attendance_report"):
        if profile.role == STUDENT:
            return url_name == "teacher_id_card"
        return profile.role == TEACHER and profile.teacher_id == pk

    if url_name == "fee_receipt":
        if profile.role != STUDENT or not profile.student_id:
            return False
        Fee = _model("Fee")
        return Fee.objects.filter(pk=pk, student_id=profile.student_id).exists()

    if url_name == "salary_receipt":
        if profile.role != TEACHER or not profile.teacher_id:
            return False
        SalaryPayment = _model("SalaryPayment")
        return SalaryPayment.objects.filter(pk=pk, teacher_id=profile.teacher_id).exists()

    return True


class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        url_name = getattr(request.resolver_match, "url_name", None) if request.resolver_match else None

        if url_name is None or request.path.startswith("/admin/") or request.path.startswith("/static/") or request.path.startswith("/media/"):
            return None

        if url_name in PUBLIC_URL_NAMES:
            return None

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if request.user.is_superuser:
            return None

        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise PermissionDenied("Your account has no role assigned. Contact an administrator.")

        if profile.role == ADMIN:
            return None

        if url_name in COMMON_AUTHENTICATED_URL_NAMES:
            return None

        allowed_roles = ROLE_PERMISSIONS.get(url_name, ())
        if profile.role not in allowed_roles:
            if url_name in SOFT_REDIRECT_URL_NAMES:
                return redirect("role_dashboard")
            raise PermissionDenied("You do not have permission to access this page.")

        if url_name in OWNERSHIP_CHECK_URL_NAMES:
            if not _is_owner(url_name, profile, view_kwargs):
                raise PermissionDenied("You can only view your own records.")

        return None