from django.db import models


class SiteSettings(models.Model):
    """Singleton model holding global branding: college name & logo.
    Shown in the sidebar brand box, the sidebar title, and the top-right
    avatar button across the dashboard."""
    college_name = models.CharField(max_length=150, default='MPI')
    logo = models.ImageField(upload_to='site_logo/', blank=True, null=True)

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.college_name


class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Teacher(models.Model):
    SHIFT_CHOICES = [
        ('1st', '1st Shift'),
        ('2nd', '2nd Shift'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES, blank=True, default='')
    designation = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    teacher_image = models.ImageField(upload_to='teacher_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class SalaryPayment(models.Model):
    MONTH_CHOICES = [
        ('January', 'January'), ('February', 'February'), ('March', 'March'),
        ('April', 'April'), ('May', 'May'), ('June', 'June'),
        ('July', 'July'), ('August', 'August'), ('September', 'September'),
        ('October', 'October'), ('November', 'November'), ('December', 'December'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='salary_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    year = models.IntegerField(default=2026)
    payment_date = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.first_name} - {self.month} {self.year} ({self.amount} Tk)"

class Student(models.Model):
    SHIFT_CHOICES = [
        ('1st', '1st Shift'),
        ('2nd', '2nd Shift'),
    ]
    SEMESTER_CHOICES = [
        ('1st', '1st Semester'),
        ('2nd', '2nd Semester'),
        ('3rd', '3rd Semester'),
        ('4th', '4th Semester'),
        ('5th', '5th Semester'),
        ('6th', '6th Semester'),
        ('7th', '7th Semester'),
        ('8th', '8th Semester'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    roll = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES)
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    student_image = models.ImageField(upload_to='student_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.roll} - {self.first_name} {self.last_name}"


class Fee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.roll} - ৳{self.amount}"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    title = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.type}) - ৳{self.amount}"


class Notice(models.Model):
    RECIPIENT_CHOICES = [
        ('All', 'All'),
        ('Students', 'Students Only'),
        ('Teachers', 'Teachers Only'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    recipients = models.CharField(max_length=20, choices=RECIPIENT_CHOICES, default='All')
    is_urgent = models.BooleanField(default=False)
    signatory_name = models.CharField(max_length=200, blank=True)
    signatory_designation = models.CharField(max_length=200, blank=True, default='Principal')
    image = models.ImageField(upload_to='notice_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ClassRoutine(models.Model):
    DAY_CHOICES = [
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
    ]

    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    shift = models.CharField(max_length=10, choices=Student.SHIFT_CHOICES)
    semester = models.CharField(max_length=10, choices=Student.SEMESTER_CHOICES)
    day = models.CharField(max_length=15, choices=DAY_CHOICES)
    subject = models.CharField(max_length=100)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_no = models.CharField(max_length=20)

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.department.name} - {self.shift} - {self.semester} - {self.day} - {self.subject}"


class ExamRoutine(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    semester = models.CharField(max_length=10, choices=Student.SEMESTER_CHOICES)
    subject = models.CharField(max_length=100)
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_no = models.CharField(max_length=20)

    class Meta:
        ordering = ['exam_date', 'start_time']

    def __str__(self):
        return f"{self.department.name} - {self.semester} - {self.subject} ({self.exam_date})"


class ExamMark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_marks')
    semester = models.CharField(max_length=10, choices=Student.SEMESTER_CHOICES)
    subject = models.CharField(max_length=100)
    full_marks = models.PositiveIntegerField(default=100)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subject']

    def __str__(self):
        return f"{self.student.roll} - {self.semester} - {self.subject}: {self.marks_obtained}/{self.full_marks}"


class FeeStructure(models.Model):
    """Defines the total tuition/institutional fee expected for a given
    department + shift + semester group, used to calculate outstanding dues.
    This is purely additive and does not affect any existing feature."""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    shift = models.CharField(max_length=10, choices=Student.SHIFT_CHOICES)
    semester = models.CharField(max_length=10, choices=Student.SEMESTER_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('department', 'shift', 'semester')
        ordering = ['department', 'semester']

    def __str__(self):
        return f"{self.department.name} - {self.shift} - {self.semester} Sem: ৳{self.total_amount}"


ATTENDANCE_STATUS_CHOICES = [
    ('Present', 'Present'),
    ('Absent', 'Absent'),
    ('Late', 'Late'),
]


class StudentAttendance(models.Model):
    """Daily attendance record for a single student on a single date.
    This is purely additive and does not affect any existing feature."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='Present')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.roll} - {self.date} - {self.status}"


class TeacherAttendance(models.Model):
    """Daily attendance record for a single teacher on a single date.
    This is purely additive and does not affect any existing feature."""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='Present')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.teacher.first_name} {self.teacher.last_name} - {self.date} - {self.status}"


# ===== Library Management =====
# Fully additive module: tracks book catalog/stock and the borrow/return lifecycle
# for both students and teachers. Does not modify any existing model or feature.

class Book(models.Model):
    """A title in the library catalog. `total_copies` is the physical stock;
    availability is derived from currently-unreturned BookIssue records so the
    two numbers can never drift out of sync."""
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150)
    isbn = models.CharField(max_length=20, unique=True, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True)
    publisher = models.CharField(max_length=150, blank=True)
    total_copies = models.PositiveIntegerField(default=1)
    shelf_location = models.CharField(max_length=50, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} — {self.author}"

    @property
    def issued_count(self):
        return self.issues.filter(return_date__isnull=True).count()

    @property
    def available_copies(self):
        return max(self.total_copies - self.issued_count, 0)


BORROWER_TYPE_CHOICES = [
    ('Student', 'Student'),
    ('Teacher', 'Teacher'),
]


class BookIssue(models.Model):
    """A single borrow record: one physical copy of a book lent to either a
    student or a staff member (teacher), with an issue date, due date, and an
    optional return date. `return_date` is null while the book is still out."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='issues')
    borrower_type = models.CharField(max_length=10, choices=BORROWER_TYPE_CHOICES)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='book_issues')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True, related_name='book_issues')
    issue_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return f"{self.book.title} -> {self.borrower_name} ({self.issue_date})"

    @property
    def borrower_name(self):
        if self.borrower_type == 'Student' and self.student_id:
            return f"{self.student.first_name} {self.student.last_name}"
        if self.borrower_type == 'Teacher' and self.teacher_id:
            return f"{self.teacher.first_name} {self.teacher.last_name}"
        return "Unknown"

    @property
    def is_returned(self):
        return self.return_date is not None


# ===== Hostel Management =====
# Fully additive module: tracks hostel buildings, their rooms/seat capacity,
# and which students are currently allocated to which room/bed. Does not
# modify any existing model or feature.

class Hostel(models.Model):
    """A single hostel building/block."""
    HOSTEL_TYPE_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    name = models.CharField(max_length=150)
    hostel_type = models.CharField(max_length=10, choices=HOSTEL_TYPE_CHOICES)
    warden_name = models.CharField(max_length=100, blank=True)
    warden_phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.hostel_type})"

    @property
    def total_rooms(self):
        return self.rooms.count()

    @property
    def total_capacity(self):
        return self.rooms.aggregate(models.Sum('capacity'))['capacity__sum'] or 0

    @property
    def occupied_seats(self):
        return HostelAllocation.objects.filter(room__hostel=self, status='Active').count()

    @property
    def available_seats(self):
        return max(self.total_capacity - self.occupied_seats, 0)


class HostelRoom(models.Model):
    """A single room within a hostel. `capacity` is the number of seats/beds;
    occupancy is derived from currently-active HostelAllocation records so
    the two numbers can never drift out of sync."""
    ROOM_TYPE_CHOICES = [
        ('Single', 'Single'),
        ('Double', 'Double'),
        ('Triple', 'Triple'),
        ('Dormitory', 'Dormitory'),
    ]
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    room_no = models.CharField(max_length=20)
    room_type = models.CharField(max_length=15, choices=ROOM_TYPE_CHOICES, default='Double')
    capacity = models.PositiveIntegerField(default=1)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('hostel', 'room_no')
        ordering = ['hostel', 'room_no']

    def __str__(self):
        return f"{self.hostel.name} - Room {self.room_no}"

    @property
    def occupied_seats(self):
        return self.allocations.filter(status='Active').count()

    @property
    def available_seats(self):
        return max(self.capacity - self.occupied_seats, 0)


class HostelAllocation(models.Model):
    """A single seat/bed assignment: one student placed in one room. Kept as
    a historical record — `status` moves to 'Vacated' (with a `vacate_date`)
    instead of being deleted when a student leaves the room."""
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Vacated', 'Vacated'),
    ]
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name='allocations')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='hostel_allocations')
    bed_no = models.CharField(max_length=20, blank=True)
    allocation_date = models.DateField()
    vacate_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-allocation_date', '-id']

    def __str__(self):
        return f"{self.student.roll} -> {self.room} ({self.status})"


# ===== Transport Management =====
# Fully additive module: tracks college bus routes/stops, student seat
# allocations on those routes, and the monthly transport fee payments tied
# to each allocation. Does not modify any existing model or feature.

class BusRoute(models.Model):
    """A single college bus route/vehicle."""
    route_name = models.CharField(max_length=150)
    vehicle_no = models.CharField(max_length=30)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['route_name']

    def __str__(self):
        return f"{self.route_name} ({self.vehicle_no})"

    @property
    def occupied_seats(self):
        return self.transport_allocations.filter(status='Active').count()

    @property
    def available_seats(self):
        return max(self.capacity - self.occupied_seats, 0)


class BusStop(models.Model):
    """A single pickup/drop stop along a bus route."""
    route = models.ForeignKey(BusRoute, on_delete=models.CASCADE, related_name='stops')
    stop_name = models.CharField(max_length=150)
    stop_order = models.PositiveIntegerField(default=1)
    pickup_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ['route', 'stop_order']

    def __str__(self):
        return f"{self.stop_name} ({self.route.route_name})"


class TransportAllocation(models.Model):
    """A single student's seat assignment on a bus route. Kept as a
    historical record — `status` moves to 'Inactive' instead of being
    deleted when a student stops using the service."""
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='transport_allocations')
    route = models.ForeignKey(BusRoute, on_delete=models.CASCADE, related_name='transport_allocations')
    stop = models.ForeignKey(BusStop, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_allocations')
    allocation_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-allocation_date', '-id']

    def __str__(self):
        return f"{self.student.roll} -> {self.route.route_name} ({self.status})"


class TransportFeePayment(models.Model):
    """A single monthly transport-fee payment tied to a student's route
    allocation. Mirrors the SalaryPayment pattern used for teacher salaries."""
    MONTH_CHOICES = [
        ('January', 'January'), ('February', 'February'), ('March', 'March'),
        ('April', 'April'), ('May', 'May'), ('June', 'June'),
        ('July', 'July'), ('August', 'August'), ('September', 'September'),
        ('October', 'October'), ('November', 'November'), ('December', 'December'),
    ]
    allocation = models.ForeignKey(TransportAllocation, on_delete=models.CASCADE, related_name='fee_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    year = models.IntegerField(default=2026)
    payment_date = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.allocation.student.roll} - {self.month} {self.year} ({self.amount} Tk)"