from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.role_dashboard, name="role_dashboard"),
    path("teacher-dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    path("accountant-dashboard/", views.accountant_dashboard, name="accountant_dashboard"),
    path("students/", views.student_directory, name="student_directory"),
    path("exam-routine/", views.get_exam_routine, name="get_exam_routine"),
    path("profile/", views.profile_view, name="profile"),
    path("class-routine/", views.get_class_routine, name="get_class_routine"),
    path("register/teacher/", views.teacher_register, name="teacher_register"),
    path("register/student/", views.student_register, name="student_register"),
    path("my-attendance/", views.my_attendance, name="my_attendance"),
    path("mark-attendance/", views.mark_attendance_form, name="mark_student_attendance_form"),
    path("enter-exam-marks/", views.enter_exam_marks_form, name="enter_exam_marks_form"),
    path("notices/mark-seen/", views.mark_notices_seen, name="mark_notices_seen"),
    path("update-profile/", views.update_profile, name="update_profile"),
    path("change-password/", views.change_password, name="change_password"),
]