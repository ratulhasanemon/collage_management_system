from django.conf import settings
from django.db import models

# ---------------------------------------------------------------------------
# IMPORTANT: replace 'core' below with the actual app label of the app that
# contains your existing models.py (Teacher, Student, etc.) — the one whose
# admin.py/urls.py/views.py you shared. Using the 'app_label.ModelName'
# string form (instead of importing the classes) avoids any circular-import
# risk and means this file never has to touch your existing models.py.
# ---------------------------------------------------------------------------
CORE_APP = "app"


class UserProfile(models.Model):
    """Attaches a role — and, for staff/students, a link back to their
    existing Teacher/Student record — to a standard Django auth User.

    This is purely additive: it does not modify Teacher, Student, or any
    other existing model. One UserProfile per login account.
    """

    ROLE_ADMIN = "admin"
    ROLE_ACCOUNTANT = "accountant"
    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_ACCOUNTANT, "Accountant"),
        (ROLE_TEACHER, "Teacher"),
        (ROLE_STUDENT, "Student"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Only one of these should be set, matching `role`. Both are optional
    # because Admin and Accountant accounts don't correspond to a
    # Teacher/Student row.
    teacher = models.OneToOneField(
        f"{CORE_APP}.Teacher",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_account",
    )
    student = models.OneToOneField(
        f"{CORE_APP}.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_account",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Used to compute whether the notification bell should show a red dot —
    # a notice is "unread" if it was created after this timestamp. Updated
    # every time the person opens the notification panel.
    last_notice_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def teacher_id_value(self):
        return self.teacher_id

    @property
    def student_id_value(self):
        return self.student_id