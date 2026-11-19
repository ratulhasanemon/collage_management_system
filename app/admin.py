from django.contrib import admin
from .models import SiteSettings, Department, Teacher, Student, Fee, Transaction, Notice, ClassRoutine, ExamRoutine, ExamMark, FeeStructure, StudentAttendance, TeacherAttendance, Book, BookIssue, Hostel, HostelRoom, HostelAllocation, BusRoute, BusStop, TransportAllocation, TransportFeePayment


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['college_name', 'logo']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'department', 'designation', 'salary', 'phone', 'teacher_image']
    search_fields = ['first_name', 'last_name', 'email', 'phone']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['roll', 'first_name', 'last_name', 'department', 'shift', 'semester', 'phone']
    search_fields = ['roll', 'first_name', 'last_name', 'phone']
    list_filter = ['department', 'shift', 'semester']

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ['student', 'amount', 'created_at']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'amount', 'created_at']
    list_filter = ['type']

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipients', 'is_urgent', 'created_at']
    list_filter = ['is_urgent', 'recipients']

@admin.register(ClassRoutine)
class ClassRoutineAdmin(admin.ModelAdmin):
    list_display = ['department', 'shift', 'semester', 'day', 'subject', 'start_time', 'end_time', 'room_no', 'teacher']
    list_filter = ['department', 'shift', 'semester', 'day']
    search_fields = ['subject', 'room_no']

@admin.register(ExamRoutine)
class ExamRoutineAdmin(admin.ModelAdmin):
    list_display = ['department', 'semester', 'subject', 'exam_date', 'start_time', 'end_time', 'room_no']
    list_filter = ['department', 'semester', 'exam_date']
    search_fields = ['subject', 'room_no']

@admin.register(ExamMark)
class ExamMarkAdmin(admin.ModelAdmin):
    list_display = ['student', 'semester', 'subject', 'marks_obtained', 'full_marks', 'created_at']
    list_filter = ['semester']
    search_fields = ['student__roll', 'student__first_name', 'student__last_name', 'subject']

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['department', 'shift', 'semester', 'total_amount']
    list_filter = ['department', 'shift', 'semester']

@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['student__roll', 'student__first_name', 'student__last_name']

@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'date', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['teacher__first_name', 'teacher__last_name']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'total_copies', 'available_copies', 'shelf_location']
    search_fields = ['title', 'author', 'isbn']
    list_filter = ['category']


@admin.register(BookIssue)
class BookIssueAdmin(admin.ModelAdmin):
    list_display = ['book', 'borrower_type', 'borrower_name', 'issue_date', 'due_date', 'return_date']
    list_filter = ['borrower_type', 'issue_date', 'return_date']
    search_fields = ['book__title', 'student__roll', 'student__first_name', 'teacher__first_name', 'teacher__last_name']


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ['name', 'hostel_type', 'warden_name', 'warden_phone', 'total_rooms', 'total_capacity']
    list_filter = ['hostel_type']
    search_fields = ['name', 'warden_name']


@admin.register(HostelRoom)
class HostelRoomAdmin(admin.ModelAdmin):
    list_display = ['hostel', 'room_no', 'room_type', 'capacity', 'occupied_seats', 'available_seats', 'monthly_rent']
    list_filter = ['hostel', 'room_type']
    search_fields = ['room_no', 'hostel__name']


@admin.register(HostelAllocation)
class HostelAllocationAdmin(admin.ModelAdmin):
    list_display = ['student', 'room', 'bed_no', 'allocation_date', 'vacate_date', 'status']
    list_filter = ['status', 'room__hostel']
    search_fields = ['student__roll', 'student__first_name', 'student__last_name', 'room__room_no']


@admin.register(BusRoute)
class BusRouteAdmin(admin.ModelAdmin):
    list_display = ['route_name', 'vehicle_no', 'driver_name', 'driver_phone', 'capacity', 'occupied_seats', 'available_seats', 'monthly_fee']
    search_fields = ['route_name', 'vehicle_no', 'driver_name']


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ['stop_name', 'route', 'stop_order', 'pickup_time']
    list_filter = ['route']
    search_fields = ['stop_name', 'route__route_name']


@admin.register(TransportAllocation)
class TransportAllocationAdmin(admin.ModelAdmin):
    list_display = ['student', 'route', 'stop', 'allocation_date', 'status']
    list_filter = ['status', 'route']
    search_fields = ['student__roll', 'student__first_name', 'student__last_name', 'route__route_name']


@admin.register(TransportFeePayment)
class TransportFeePaymentAdmin(admin.ModelAdmin):
    list_display = ['allocation', 'month', 'year', 'amount', 'payment_date']
    list_filter = ['month', 'year']
    search_fields = ['allocation__student__roll', 'allocation__student__first_name', 'allocation__student__last_name']