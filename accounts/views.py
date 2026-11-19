from django.apps import apps
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from .middleware import CORE_APP
from .models import UserProfile


def _model(name):
    return apps.get_model(CORE_APP, name)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("role_dashboard")

    login_type = request.POST.get("login_type", "admin") if request.method == "POST" else "admin"

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        username = identifier

        if login_type == "student" and identifier:
            Student = _model("Student")
            student = Student.objects.filter(roll__iexact=identifier).first()
            if student is not None:
                profile = UserProfile.objects.filter(student=student).select_related("user").first()
                if profile is not None:
                    username = profile.user.username

        user = authenticate(request, username=username, password=password)

        expected_role = {
            "admin": UserProfile.ROLE_ADMIN,
            "teacher": UserProfile.ROLE_TEACHER,
            "student": UserProfile.ROLE_STUDENT,
        }.get(login_type)

        if user is not None:
            profile = getattr(user, "profile", None)
            is_valid_admin = user.is_superuser and login_type == "admin"
            is_valid_role = profile is not None and (
                profile.role == expected_role
                or (login_type == "admin" and profile.role == UserProfile.ROLE_ACCOUNTANT)
            )

            if is_valid_admin or is_valid_role:
                login(request, user)
                return redirect("role_dashboard")

            messages.error(request, "Those credentials don't belong to a %s account." % login_type)
        else:
            if login_type == "student":
                messages.error(request, "Invalid roll number/username or password.")
            else:
                messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html", {"active_tab": login_type})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def role_dashboard(request):
    if request.user.is_superuser and not hasattr(request.user, "profile"):
        return redirect("index")

    profile = getattr(request.user, "profile", None)
    if profile is None:
        messages.error(request, "Your account has no role assigned. Contact an administrator.")
        return redirect("login")

    return redirect({
        UserProfile.ROLE_ADMIN: "index",
        UserProfile.ROLE_ACCOUNTANT: "accountant_dashboard",
        UserProfile.ROLE_TEACHER: "teacher_dashboard",
        UserProfile.ROLE_STUDENT: "student_dashboard",
    }[profile.role])


# ---------------------------------------------------------------------------
# Self-registration: lets a Teacher/Student who already exists as a record
# (added by admin via the People management screens) create their own
# login account, instead of an admin manually creating a User + UserProfile
# for every single person via /admin/. Identity is verified against two
# fields already on file, and a record can only be claimed once.
# ---------------------------------------------------------------------------

def teacher_register(request):
    if request.user.is_authenticated:
        return redirect("role_dashboard")

    Teacher = _model("Teacher")

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        teacher = Teacher.objects.filter(email__iexact=email, phone=phone).first()

        if teacher is None:
            messages.error(request, "No teacher record matches that email and phone number. Contact the administrator.")
        elif hasattr(teacher, "user_account"):
            messages.error(request, "This teacher record already has a login account. Try signing in, or use 'Forgot password'.")
        elif not username or not password:
            messages.error(request, "Username and password are required.")
        elif password != password_confirm:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, "That username is already taken. Choose another.")
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=teacher.first_name,
                last_name=teacher.last_name,
                email=teacher.email,
            )
            UserProfile.objects.create(user=user, role=UserProfile.ROLE_TEACHER, teacher=teacher)
            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("role_dashboard")

    return render(request, "accounts/teacher_register.html")


def student_register(request):
    if request.user.is_authenticated:
        return redirect("role_dashboard")

    Student = _model("Student")

    if request.method == "POST":
        roll = request.POST.get("roll", "").strip()
        phone = request.POST.get("phone", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        student = Student.objects.filter(roll__iexact=roll, phone=phone).first()

        if student is None:
            messages.error(request, "No student record matches that roll number and phone number. Contact the administrator.")
        elif hasattr(student, "user_account"):
            messages.error(request, "This student record already has a login account. Try signing in, or use 'Forgot password'.")
        elif not username or not password:
            messages.error(request, "Username and password are required.")
        elif password != password_confirm:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, "That username is already taken. Choose another.")
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=student.first_name,
                last_name=student.last_name,
                email=student.email,
            )
            UserProfile.objects.create(user=user, role=UserProfile.ROLE_STUDENT, student=student)
            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("role_dashboard")

    return render(request, "accounts/student_register.html")


# ---------------------------------------------------------------------------
# Teacher dashboard
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_TEACHER)
def teacher_dashboard(request):
    teacher = request.user.profile.teacher
    context = {"teacher": teacher}

    if teacher is not None:
        ClassRoutine = _model("ClassRoutine")
        TeacherAttendance = _model("TeacherAttendance")
        SalaryPayment = _model("SalaryPayment")
        Notice = _model("Notice")

        context["routine"] = ClassRoutine.objects.filter(teacher=teacher).select_related("department")
        context["recent_attendance"] = TeacherAttendance.objects.filter(teacher=teacher)[:10]
        context["salary_payments"] = SalaryPayment.objects.filter(teacher=teacher).order_by("-payment_date")[:10]
        context["notices"] = Notice.objects.filter(
            recipients__in=["All", "Teachers"]
        ).order_by("-created_at")[:10]

        # ---- Summary graph data (replaces the old "My Class Routine" table
        # ---- on the dashboard): weekly class-load bar chart + attendance
        # ---- distribution donut chart.
        day_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_counts = {day: 0 for day in day_order}
        for r in context["routine"]:
            if r.day in day_counts:
                day_counts[r.day] += 1
        max_day_count = max(day_counts.values()) if day_counts else 0
        context["weekly_class_load"] = [
            {
                "day": day,
                "count": count,
                "pct": round((count / max_day_count) * 100, 1) if max_day_count else 0,
            }
            for day, count in day_counts.items()
        ]

        all_attendance = TeacherAttendance.objects.filter(teacher=teacher)
        att_total = all_attendance.count()
        att_present = all_attendance.filter(status="Present").count()
        att_late = all_attendance.filter(status="Late").count()
        att_absent = all_attendance.filter(status="Absent").count()
        context["attendance_summary"] = {
            "total": att_total,
            "present": att_present,
            "late": att_late,
            "absent": att_absent,
            "present_pct": round((att_present / att_total) * 100, 1) if att_total else 0,
            "late_pct": round((att_late / att_total) * 100, 1) if att_total else 0,
            "absent_pct": round((att_absent / att_total) * 100, 1) if att_total else 0,
        }

        profile = request.user.profile
        latest_notice = context["notices"].first()
        context["has_unread_notices"] = bool(
            latest_notice and (
                profile.last_notice_seen_at is None
                or latest_notice.created_at > profile.last_notice_seen_at
            )
        )

    return render(request, "accounts/teacher_dashboard.html", context)


@role_required(UserProfile.ROLE_TEACHER)
def student_directory(request):
    """Read-only list of students for teachers (no edit/delete)."""
    Student = _model("Student")
    students = Student.objects.select_related("department").all().order_by("roll")

    semester = request.POST.get("semester") if request.method == "POST" else request.GET.get("semester", "")
    if semester:
        students = students.filter(semester=semester)

    return render(request, "accounts/student_directory.html", {
        "students": students,
        "teacher": request.user.profile.teacher,
        "semester_choices": Student.SEMESTER_CHOICES,
        "semester": semester,
    })


# ---------------------------------------------------------------------------
# Shared: exam routine (read-only for teacher + student)
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def get_exam_routine(request):
    ExamRoutine = _model("ExamRoutine")
    Student = _model("Student")
    profile = request.user.profile
    semester = request.GET.get("semester", "")

    if profile.role == UserProfile.ROLE_STUDENT and profile.student:
        exam_routine = ExamRoutine.objects.filter(
            department=profile.student.department,
            semester=profile.student.semester,
        ).select_related("department")
    elif profile.role == UserProfile.ROLE_TEACHER and profile.teacher:
        exam_routine = ExamRoutine.objects.filter(
            department=profile.teacher.department
        ).select_related("department")
        if semester:
            exam_routine = exam_routine.filter(semester=semester)
    else:
        exam_routine = ExamRoutine.objects.none()

    return render(request, "accounts/exam_routine.html", {
        "exam_routine": exam_routine,
        "teacher": profile.teacher if profile.role == UserProfile.ROLE_TEACHER else None,
        "student": profile.student if profile.role == UserProfile.ROLE_STUDENT else None,
        "semester_choices": Student.SEMESTER_CHOICES,
        "semester": semester,
    })


# ---------------------------------------------------------------------------
# Shared: profile page (read-only for teacher + student)
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def profile_view(request):
    profile = request.user.profile
    context = {}

    if profile.role == UserProfile.ROLE_TEACHER:
        context["teacher"] = profile.teacher
    elif profile.role == UserProfile.ROLE_STUDENT:
        context["student"] = profile.student

    return render(request, "accounts/profile.html", context)


@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
@require_POST
def update_profile(request):
    """AJAX — Profile Edit Tab: update name, email, phone, and profile image."""
    profile = request.user.profile
    first_name = request.POST.get("first_name", "").strip()
    last_name  = request.POST.get("last_name", "").strip()
    email      = request.POST.get("email", "").strip()
    phone      = request.POST.get("phone", "").strip()
    image      = request.FILES.get("profile_image")

    if not first_name or not last_name or not email:
        return JsonResponse({"success": False, "message": "First name, last name, and email are required."})

    try:
        image_url = None
        if profile.role == UserProfile.ROLE_TEACHER and profile.teacher:
            t = profile.teacher
            t.first_name = first_name
            t.last_name  = last_name
            t.email      = email
            t.phone      = phone
            if image:
                t.teacher_image = image
            t.save()
            if t.teacher_image:
                image_url = t.teacher_image.url
        elif profile.role == UserProfile.ROLE_STUDENT and profile.student:
            s = profile.student
            s.first_name = first_name
            s.last_name  = last_name
            s.email      = email
            s.phone      = phone
            if image:
                s.student_image = image
            s.save()
            if s.student_image:
                image_url = s.student_image.url
        else:
            return JsonResponse({"success": False, "message": "No linked record found for your account."})

        return JsonResponse({"success": True, "message": "Profile updated successfully!", "image_url": image_url})
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error: {str(e)}"})


@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
@require_POST
def change_password(request):
    """AJAX — Password Tab: verify current password and set new one."""
    user             = request.user
    current_password = request.POST.get("current_password", "")
    new_password     = request.POST.get("new_password", "")
    confirm_password = request.POST.get("confirm_password", "")

    if not user.check_password(current_password):
        return JsonResponse({"success": False, "message": "Current password is incorrect."})
    if len(new_password) < 8:
        return JsonResponse({"success": False, "message": "New password must be at least 8 characters."})
    if new_password != confirm_password:
        return JsonResponse({"success": False, "message": "Passwords do not match."})

    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)   # keeps the user logged in
    return JsonResponse({"success": True, "message": "Password changed successfully!"})


# ---------------------------------------------------------------------------
# Shared: class routine, scoped to the caller
#   - Teacher: only classes assigned to them (ClassRoutine.teacher == them)
#   - Student: only rows matching their own department, shift & semester
# ---------------------------------------------------------------------------

DAY_ORDER = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DEFAULT_DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"]


@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def get_class_routine(request):
    ClassRoutine = _model("ClassRoutine")
    profile = request.user.profile

    if profile.role == UserProfile.ROLE_TEACHER and profile.teacher:
        class_routine = ClassRoutine.objects.filter(
            teacher=profile.teacher
        ).select_related("department").order_by("day", "start_time")
    elif profile.role == UserProfile.ROLE_STUDENT and profile.student:
        student = profile.student
        class_routine = ClassRoutine.objects.filter(
            department=student.department,
            shift=student.shift,
            semester=student.semester,
        ).select_related("teacher", "department").order_by("day", "start_time")
    else:
        class_routine = ClassRoutine.objects.none()

    entries = list(class_routine)

    # Figure out which weekdays actually have classes, in calendar order.
    days_present = []
    for e in entries:
        if e.day not in days_present:
            days_present.append(e.day)
    days = sorted(days_present, key=lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else len(DAY_ORDER))
    if not days:
        days = DEFAULT_DAYS

    # Figure out the distinct time slots in use, in start-time order.
    slots = []
    for e in entries:
        key = (e.start_time, e.end_time)
        if key not in slots:
            slots.append(key)
    slots.sort(key=lambda k: k[0])

    lookup = {(e.day, e.start_time, e.end_time): e for e in entries}

    rows = [
        {
            "start_time": start,
            "end_time": end,
            "cells": [lookup.get((day, start, end)) for day in days],
        }
        for start, end in slots
    ]

    return render(request, "accounts/class_routine.html", {
        "class_routine": class_routine,
        "days": days,
        "rows": rows,
        "teacher": profile.teacher if profile.role == UserProfile.ROLE_TEACHER else None,
        "student": profile.student if profile.role == UserProfile.ROLE_STUDENT else None,
    })


# ---------------------------------------------------------------------------
# Teacher self-service: attendance report, mark attendance, enter exam marks.
# These are separate from the admin-only action endpoints in app/views.py
# (add_exam_marks, mark_student_attendance, get_teacher_attendance_report),
# which only accept POST/AJAX and aren't meant to be visited as pages. Each
# view below is scoped so a teacher only sees/marks students from classes
# they actually teach (derived from their ClassRoutine entries).
# ---------------------------------------------------------------------------

def _teacher_student_queryset(teacher):
    """All students in the teacher's own department — gives the teacher the
    same department-wide reach as an admin for marks/attendance, rather than
    limiting them to only the classes on their own routine."""
    Student = _model("Student")

    if not teacher.department_id:
        return Student.objects.none()

    return Student.objects.filter(department_id=teacher.department_id).order_by("roll")


@role_required(UserProfile.ROLE_TEACHER)
def my_attendance(request):
    teacher = request.user.profile.teacher
    context = {"teacher": teacher}

    if teacher is not None:
        TeacherAttendance = _model("TeacherAttendance")
        today = timezone.localdate()

        records = TeacherAttendance.objects.filter(teacher=teacher).order_by("-date")
        this_month = records.filter(date__year=today.year, date__month=today.month)

        present = this_month.filter(status="Present").count()
        absent = this_month.filter(status="Absent").count()
        late = this_month.filter(status="Late").count()
        total = this_month.count()
        percentage = round(((present + late) / total * 100), 2) if total else 0

        context.update({
            "records": records[:60],
            "present": present,
            "absent": absent,
            "late": late,
            "total": total,
            "percentage": percentage,
            "month_label": today.strftime("%B %Y"),
        })

    return render(request, "accounts/my_attendance.html", context)


@role_required(UserProfile.ROLE_TEACHER)
def mark_attendance_form(request):
    teacher = request.user.profile.teacher
    Student = _model("Student")
    StudentAttendance = _model("StudentAttendance")

    if request.method == "POST":
        semester = request.POST.get("semester", "")
        students = _teacher_student_queryset(teacher)
        if semester:
            students = students.filter(semester=semester)

        att_date = request.POST.get("att_date")

        saved = 0
        for student in students:
            status = request.POST.get(f"status_{student.id}")
            if not status:
                continue
            StudentAttendance.objects.update_or_create(
                student_id=student.id, date=att_date, defaults={"status": status}
            )
            saved += 1

        if saved:
            messages.success(request, f"Attendance saved for {saved} student(s) on {att_date}.")
        else:
            messages.error(request, "No attendance was saved. Pick a date and at least one status.")
        redirect_url = "mark_student_attendance_form"
        if semester:
            return redirect(f"{reverse(redirect_url)}?semester={semester}")
        return redirect(redirect_url)

    semester = request.GET.get("semester", "")
    students = _teacher_student_queryset(teacher)
    if semester:
        students = students.filter(semester=semester)

    return render(request, "accounts/mark_attendance.html", {
        "teacher": teacher,
        "students": students,
        "today": timezone.localdate(),
        "semester_choices": Student.SEMESTER_CHOICES,
        "semester": semester,
    })


@role_required(UserProfile.ROLE_TEACHER)
def enter_exam_marks_form(request):
    teacher = request.user.profile.teacher
    Student = _model("Student")
    ExamMark = _model("ExamMark")
    all_students = _teacher_student_queryset(teacher)

    if request.method == "POST":
        student_id = request.POST.get("student")
        semester = request.POST.get("semester")
        subjects = request.POST.getlist("subject[]")
        full_marks_list = request.POST.getlist("full_marks[]")
        obtained_list = request.POST.getlist("marks_obtained[]")
        filter_semester = request.POST.get("filter_semester", "")
        allowed_ids = set(all_students.values_list("id", flat=True))

        if not student_id or int(student_id) not in allowed_ids:
            messages.error(request, "You can only enter marks for your own students.")
        elif not semester or not any(subjects):
            messages.error(request, "Please select a semester and add at least one subject.")
        else:
            student = Student.objects.get(pk=student_id)
            ExamMark.objects.filter(student=student, semester=semester).delete()
            for subject, full_marks, obtained in zip(subjects, full_marks_list, obtained_list):
                if not subject:
                    continue
                ExamMark.objects.create(
                    student=student, semester=semester, subject=subject,
                    full_marks=full_marks or 100, marks_obtained=obtained or 0,
                )
            messages.success(
                request,
                f"Marksheet saved for {student.first_name} {student.last_name} ({semester} Semester).",
            )
        redirect_url = "enter_exam_marks_form"
        if filter_semester:
            return redirect(f"{reverse(redirect_url)}?semester={filter_semester}")
        return redirect(redirect_url)

    semester = request.GET.get("semester", "")
    students = all_students.filter(semester=semester) if semester else all_students

    return render(request, "accounts/enter_exam_marks.html", {
        "teacher": teacher,
        "students": students,
        "semester_choices": Student.SEMESTER_CHOICES,
        "semester": semester,
    })


# ---------------------------------------------------------------------------
# Student dashboard
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_STUDENT)
def student_dashboard(request):
    student = request.user.profile.student
    context = {"student": student}

    if student is not None:
        Fee = _model("Fee")
        ExamMark = _model("ExamMark")
        ExamRoutine = _model("ExamRoutine")
        StudentAttendance = _model("StudentAttendance")
        ClassRoutine = _model("ClassRoutine")
        Notice = _model("Notice")
        Teacher = _model("Teacher")

        context["fees"] = Fee.objects.filter(student=student).order_by("-created_at")[:10]
        context["total_paid"] = Fee.objects.filter(student=student).aggregate(Sum("amount"))["amount__sum"] or 0
        context["exam_marks"] = ExamMark.objects.filter(student=student)
        context["exam_routine"] = ExamRoutine.objects.filter(
            department=student.department, semester=student.semester
        )
        context["recent_attendance"] = StudentAttendance.objects.filter(student=student)[:10]
        context["routine"] = ClassRoutine.objects.filter(
            department=student.department, shift=student.shift, semester=student.semester
        ).select_related("teacher")
        context["notices"] = Notice.objects.filter(
            recipients__in=["All", "Students"]
        ).order_by("-created_at")[:10]
        context["teachers"] = Teacher.objects.filter(
            department=student.department
        ).select_related("department")

        # ---- Summary & Distribution: attendance breakdown + per-subject marks ----
        all_attendance = StudentAttendance.objects.filter(student=student)
        att_present = all_attendance.filter(status="Present").count()
        att_absent = all_attendance.filter(status="Absent").count()
        att_late = all_attendance.filter(status="Late").count()
        att_total = att_present + att_absent + att_late
        context["attendance_summary"] = {
            "present": att_present,
            "absent": att_absent,
            "late": att_late,
            "total": att_total,
            "present_pct": round(att_present / att_total * 100, 1) if att_total else 0,
            "absent_pct": round(att_absent / att_total * 100, 1) if att_total else 0,
            "late_pct": round(att_late / att_total * 100, 1) if att_total else 0,
            "overall_pct": round((att_present + att_late) / att_total * 100, 1) if att_total else 0,
        }

        marks_distribution = []
        for m in context["exam_marks"]:
            try:
                pct = round(float(m.marks_obtained) / float(m.full_marks) * 100, 1) if m.full_marks else 0
            except (TypeError, ValueError, ZeroDivisionError):
                pct = 0
            marks_distribution.append({"subject": m.subject, "percentage": pct})
        context["marks_distribution"] = marks_distribution

        profile = request.user.profile
        latest_notice = context["notices"].first()
        context["has_unread_notices"] = bool(
            latest_notice and (
                profile.last_notice_seen_at is None
                or latest_notice.created_at > profile.last_notice_seen_at
            )
        )

    return render(request, "accounts/student_dashboard.html", context)


# ---------------------------------------------------------------------------
# Accountant dashboard
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_ACCOUNTANT)
def accountant_dashboard(request):
    Fee = _model("Fee")
    SalaryPayment = _model("SalaryPayment")
    Transaction = _model("Transaction")

    fees_total = Fee.objects.aggregate(Sum("amount"))["amount__sum"] or 0
    income_total = Transaction.objects.filter(type="income").aggregate(Sum("amount"))["amount__sum"] or 0
    salary_total = SalaryPayment.objects.aggregate(Sum("amount"))["amount__sum"] or 0
    expense_total = Transaction.objects.filter(type="expense").aggregate(Sum("amount"))["amount__sum"] or 0

    total_income = fees_total + income_total
    total_expense = salary_total + expense_total

    context = {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_balance": total_income - total_expense,
        "recent_fees": Fee.objects.select_related("student").order_by("-created_at")[:10],
        "recent_salaries": SalaryPayment.objects.select_related("teacher").order_by("-payment_date")[:10],
        "recent_transactions": Transaction.objects.order_by("-created_at")[:10],
    }
    return render(request, "accounts/accountant_dashboard.html", context)

# ---------------------------------------------------------------------------
# Notification bell: mark all notices as seen (clears the red dot).
# Shared by both the teacher and student dashboards.
# ---------------------------------------------------------------------------

@role_required(UserProfile.ROLE_TEACHER, UserProfile.ROLE_STUDENT)
def mark_notices_seen(request):
    if request.method == "POST":
        profile = request.user.profile
        profile.last_notice_seen_at = timezone.now()
        profile.save(update_fields=["last_notice_seen_at"])
    return JsonResponse({"ok": True})