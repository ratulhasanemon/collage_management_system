from datetime import timedelta
import io
import textwrap
from django.utils import timezone
from django.utils.timezone import localdate
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
from .models import Department, Teacher, Student, Fee, Transaction, Notice, SalaryPayment, ClassRoutine, ExamRoutine, ExamMark, FeeStructure, StudentAttendance, TeacherAttendance, Book, BookIssue, Hostel, HostelRoom, HostelAllocation, BusRoute, BusStop, TransportAllocation, TransportFeePayment, SiteSettings
from django.shortcuts import get_object_or_404, redirect, render
from .models import Student

DAY_ORDER = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

# Change this to your institute's actual name — it's used as the header
# on every auto-generated notice image.
INSTITUTE_NAME = "MAGURA POLYTECHNIC INSTITUTE"


def _notice_font(size, bold=False):
    """Best-effort serif font loader with a safe fallback."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf",
        "Times New Roman Bold.ttf" if bold else "Times New Roman.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _signature_font(size):
    """
    Best-effort handwriting/script font loader for the signature line.
    Falls back to an italic serif if no script font is installed on the
    server — for a nicer look, drop a script font (e.g. 'Dancing Script',
    'Great Vibes', 'Pacifico') into your project and add its filename here.
    """
    candidates = [
        "DancingScript-Regular.ttf",
        "GreatVibes-Regular.ttf",
        "Pacifico-Regular.ttf",
        "Allura-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "DejaVuSerif-Italic.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_notice_image(notice):
    """
    Renders the notice as a printed-notice-style image (institute name,
    "Notice" heading, date, title, details, and a signature line) and
    saves it onto notice.image — this is what shows on the student/teacher
    dashboards and inside the notification bell.
    """
    width = 900
    margin = 60
    wrap_width = 62

    title_font = _notice_font(28)
    heading_font = _notice_font(22)
    body_font = _notice_font(20)
    small_font = _notice_font(18)
    signature_font = _signature_font(40)

    wrapped_body = textwrap.wrap(notice.content or '', width=wrap_width) or ['']

    top_block_height = 40 + 46 + 56 + 50 + 50   # institute name + "Notice" + date + title + spacing
    body_height = len(wrapped_body) * 34
    signature_block_height = 190  # room for the handwritten name + line + designation
    height = top_block_height + body_height + signature_block_height

    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, width - 8, height - 8], outline='black', width=2)

    def center_text(y, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((width - w) / 2, y), text, font=font, fill='black')

    y = 40
    center_text(y, INSTITUTE_NAME, title_font)
    y += 56
    center_text(y, "Notice", heading_font)
    y += 66

    date_str = timezone.localtime(notice.created_at).strftime('%d %b %Y') if notice.created_at else localdate().strftime('%d %b %Y')
    draw.text((margin, y), date_str, font=body_font, fill='black')
    y += 60

    draw.text((margin, y), notice.title, font=heading_font, fill='black')
    y += 50

    for line in wrapped_body:
        draw.text((margin, y), line, font=body_font, fill='black')
        y += 34

    y += 50
    # Handwritten-style signature (the name typed in the form), sitting on the line
    if notice.signatory_name:
        draw.text((margin, y), notice.signatory_name, font=signature_font, fill='black')
    y += 56
    draw.line([(margin, y), (margin + 260, y)], fill='black', width=1)
    y += 10
    signatory = notice.signatory_designation or 'Principal'
    draw.text((margin, y), f"({signatory})", font=small_font, fill='black')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    notice.image.save(f"notice_{notice.pk}.png", ContentFile(buffer.read()), save=True)


def calculate_grade(percentage):
    if percentage >= 80:
        return 'A+'
    elif percentage >= 70:
        return 'A'
    elif percentage >= 60:
        return 'A-'
    elif percentage >= 50:
        return 'B'
    elif percentage >= 40:
        return 'C'
    elif percentage >= 33:
        return 'D'
    else:
        return 'F'

def index(request):
    departments = Department.objects.all()

    # Get active filters
    dept_id = request.GET.get('department')
    shift = request.GET.get('shift')
    semester = request.GET.get('semester')
    search_query = request.GET.get('search')
    
    # Pie Chart Time Filter (Default: 1year)
    pie_filter = request.GET.get('pie_filter', '1year')
    now = timezone.now()

    if pie_filter == '7days':
        start_date = now - timedelta(days=7)
    elif pie_filter == '1month':
        start_date = now - timedelta(days=30)
    else:  # 1year
        start_date = now - timedelta(days=365)

    # Base Querysets
    student_qs = Student.objects.all()
    teacher_qs = Teacher.objects.all()
    fee_qs = Fee.objects.all().order_by('-created_at')

    # Apply Department Filter
    if dept_id:
        student_qs = student_qs.filter(department_id=dept_id)
        teacher_qs = teacher_qs.filter(department_id=dept_id)
        fee_qs = fee_qs.filter(student__department_id=dept_id)

    # Apply Shift Filter
    if shift:
        student_qs = student_qs.filter(shift=shift)
        fee_qs = fee_qs.filter(student__shift=shift)
        teacher_qs = teacher_qs.filter(shift=shift)

    # Apply Semester Filter
    if semester:
        student_qs = student_qs.filter(semester=semester)
        fee_qs = fee_qs.filter(student__semester=semester)

    # Apply Search Filter
    if search_query:
        student_qs = student_qs.filter(
            Q(roll__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
        teacher_qs = teacher_qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(designation__icontains=search_query)
        )

    # Statistics Calculations (Overall Dashboard)
    total_students = student_qs.count()
    total_teachers = teacher_qs.count()

    fees_total = fee_qs.aggregate(Sum('amount'))['amount__sum'] or 0
    income_total = Transaction.objects.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_income = income_total + fees_total

    salary_expenses = SalaryPayment.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    other_expenses = Transaction.objects.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = salary_expenses + other_expenses

    # --- Filtered Calculations for Pie Chart (Based on Time Range) ---
    filtered_fees = Fee.objects.filter(created_at__gte=start_date).aggregate(Sum('amount'))['amount__sum'] or 0
    filtered_other_income = Transaction.objects.filter(type='income', created_at__gte=start_date).aggregate(Sum('amount'))['amount__sum'] or 0
    filtered_income = filtered_fees + filtered_other_income

    filtered_salaries = SalaryPayment.objects.filter(payment_date__gte=start_date).aggregate(Sum('amount'))['amount__sum'] or 0
    filtered_other_expenses = Transaction.objects.filter(type='expense', created_at__gte=start_date).aggregate(Sum('amount'))['amount__sum'] or 0
    filtered_expense = filtered_salaries + filtered_other_expenses

    # --- Profit / Loss Calculation ---
    net_profit = total_income - total_expense
    if net_profit > 0:
        profit_status = 'profit'
    elif net_profit < 0:
        profit_status = 'loss'
    else:
        profit_status = 'balanced'

    # --- Class Routine Filters (separate query params so they don't clash with the dashboard filters) ---
    routine_dept_id = request.GET.get('routine_department')
    routine_shift = request.GET.get('routine_shift')
    routine_semester = request.GET.get('routine_semester')

    routine_qs = ClassRoutine.objects.select_related('department', 'teacher').all()
    if routine_dept_id:
        routine_qs = routine_qs.filter(department_id=routine_dept_id)
    if routine_shift:
        routine_qs = routine_qs.filter(shift=routine_shift)
    if routine_semester:
        routine_qs = routine_qs.filter(semester=routine_semester)

    routines = sorted(
        routine_qs,
        key=lambda r: (DAY_ORDER.index(r.day) if r.day in DAY_ORDER else 99, r.start_time)
    )

    # --- Build a Time x Day grid for the visual "Class Schedule" table ---
    time_slots = sorted(set((r.start_time, r.end_time) for r in routines))
    routine_grid = []
    for start, end in time_slots:
        row_cells = []
        for day in DAY_ORDER:
            entries = [r for r in routines if r.start_time == start and r.end_time == end and r.day == day]
            row_cells.append({'day': day, 'entries': entries})
        routine_grid.append({'start_time': start, 'end_time': end, 'cells': row_cells})

    # --- Exam Routine Filters (separate query params, department + semester only) ---
    exam_dept_id = request.GET.get('exam_department')
    exam_semester = request.GET.get('exam_semester')

    exam_routine_qs = ExamRoutine.objects.select_related('department').all()
    if exam_dept_id:
        exam_routine_qs = exam_routine_qs.filter(department_id=exam_dept_id)
    if exam_semester:
        exam_routine_qs = exam_routine_qs.filter(semester=exam_semester)

    exam_routines = exam_routine_qs.order_by('exam_date', 'start_time')

    # --- Due Fees Tracker (Financial section) — separate filter params ---
    due_dept_id = request.GET.get('due_department')
    due_shift = request.GET.get('due_shift')
    due_semester = request.GET.get('due_semester')

    fee_structures = FeeStructure.objects.select_related('department').all()
    structure_map = {(fs.department_id, fs.shift, fs.semester): fs.total_amount for fs in fee_structures}

    due_student_qs = Student.objects.select_related('department').annotate(total_paid=Sum('fee__amount'))
    if due_dept_id:
        due_student_qs = due_student_qs.filter(department_id=due_dept_id)
    if due_shift:
        due_student_qs = due_student_qs.filter(shift=due_shift)
    if due_semester:
        due_student_qs = due_student_qs.filter(semester=due_semester)

    due_students = []
    for s in due_student_qs:
        expected = structure_map.get((s.department_id, s.shift, s.semester))
        if expected is None:
            continue  # no fee structure configured yet for this department/shift/semester
        paid = s.total_paid or 0
        due_amount = expected - paid
        if due_amount > 0:
            due_students.append({
                'student': s,
                'total_fee': expected,
                'paid': paid,
                'due': due_amount,
            })
    due_students.sort(key=lambda x: x['due'], reverse=True)

    # --- Daily Attendance Tracking ---
    # Student and Teacher attendance are fully independent of each other: each has
    # its own date/department (and, for students, shift/semester) filter params,
    # so changing one tab's filters never affects the other tab.

    # Student attendance filters
    att_date_str = request.GET.get('att_date') or localdate().isoformat()
    att_dept_id = request.GET.get('att_department')
    att_shift = request.GET.get('att_shift')
    att_semester = request.GET.get('att_semester')

    attendance_student_qs = Student.objects.select_related('department').all()
    if att_dept_id:
        attendance_student_qs = attendance_student_qs.filter(department_id=att_dept_id)
    if att_shift:
        attendance_student_qs = attendance_student_qs.filter(shift=att_shift)
    if att_semester:
        attendance_student_qs = attendance_student_qs.filter(semester=att_semester)

    existing_student_attendance = {
        sa.student_id: sa.status
        for sa in StudentAttendance.objects.filter(date=att_date_str, student__in=attendance_student_qs)
    }
    attendance_rows = [
        {'student': s, 'status': existing_student_attendance.get(s.id, 'Present')}
        for s in attendance_student_qs
    ]
    student_att_summary = {'Present': 0, 'Absent': 0, 'Late': 0}
    for status in existing_student_attendance.values():
        if status in student_att_summary:
            student_att_summary[status] += 1

    # Teacher attendance filters (independent params, prefixed with "teacher_")
    teacher_att_date_str = request.GET.get('teacher_att_date') or localdate().isoformat()
    teacher_att_dept_id = request.GET.get('teacher_att_department')

    teacher_attendance_qs = Teacher.objects.select_related('department').all()
    if teacher_att_dept_id:
        teacher_attendance_qs = teacher_attendance_qs.filter(department_id=teacher_att_dept_id)

    existing_teacher_attendance = {
        ta.teacher_id: ta.status
        for ta in TeacherAttendance.objects.filter(date=teacher_att_date_str, teacher__in=teacher_attendance_qs)
    }
    teacher_attendance_rows = [
        {'teacher': t, 'status': existing_teacher_attendance.get(t.id, 'Present')}
        for t in teacher_attendance_qs
    ]
    teacher_att_summary = {'Present': 0, 'Absent': 0, 'Late': 0}
    for status in existing_teacher_attendance.values():
        if status in teacher_att_summary:
            teacher_att_summary[status] += 1

    # --- Library Management ---
    # Fully additive: uses its own "lib_" prefixed filter params so it never
    # interacts with any other section's filters.
    lib_search = request.GET.get('lib_search')
    lib_category = request.GET.get('lib_category')

    book_qs = Book.objects.all()
    if lib_category:
        book_qs = book_qs.filter(category=lib_category)
    if lib_search:
        book_qs = book_qs.filter(
            Q(title__icontains=lib_search) |
            Q(author__icontains=lib_search) |
            Q(isbn__icontains=lib_search)
        )

    total_books = Book.objects.count()
    total_book_copies = Book.objects.aggregate(Sum('total_copies'))['total_copies__sum'] or 0
    total_issued_books = BookIssue.objects.filter(return_date__isnull=True).count()
    total_available_copies = max(total_book_copies - total_issued_books, 0)
    book_categories = (
        Book.objects.exclude(category='').exclude(category__isnull=True)
        .values_list('category', flat=True).distinct().order_by('category')
    )

    issue_status = request.GET.get('issue_status', '')
    issue_qs = BookIssue.objects.select_related('book', 'student', 'teacher').all()
    today = localdate()
    if issue_status == 'issued':
        issue_qs = issue_qs.filter(return_date__isnull=True)
    elif issue_status == 'returned':
        issue_qs = issue_qs.filter(return_date__isnull=False)
    elif issue_status == 'overdue':
        issue_qs = issue_qs.filter(return_date__isnull=True, due_date__lt=today)

    book_issues = issue_qs.order_by('-issue_date', '-id')
    overdue_book_count = BookIssue.objects.filter(return_date__isnull=True, due_date__lt=today).count()

    # --- Hostel Management ---
    # Fully additive: uses its own "hs_" prefixed filter params so it never
    # interacts with any other section's filters.
    hs_search = request.GET.get('hs_search')

    hostels = Hostel.objects.all()
    hostel_rooms_qs = HostelRoom.objects.select_related('hostel').all()
    if hs_search:
        hostel_rooms_qs = hostel_rooms_qs.filter(
            Q(room_no__icontains=hs_search) | Q(hostel__name__icontains=hs_search)
        )

    total_hostels = Hostel.objects.count()
    total_hostel_rooms = HostelRoom.objects.count()
    total_hostel_capacity = HostelRoom.objects.aggregate(Sum('capacity'))['capacity__sum'] or 0
    total_hostel_occupied = HostelAllocation.objects.filter(status='Active').count()
    total_hostel_available = max(total_hostel_capacity - total_hostel_occupied, 0)

    hostel_allocations = (
        HostelAllocation.objects.select_related('room', 'room__hostel', 'student').all()
    )

    # --- Transport Management ---
    # Fully additive: uses its own "tr_" prefixed filter params so it never
    # interacts with any other section's filters.
    tr_search = request.GET.get('tr_search')

    bus_routes = BusRoute.objects.all()
    bus_stops = BusStop.objects.select_related('route').all()
    transport_allocations_qs = TransportAllocation.objects.select_related('student', 'route', 'stop').all()
    if tr_search:
        transport_allocations_qs = transport_allocations_qs.filter(
            Q(student__roll__icontains=tr_search) |
            Q(student__first_name__icontains=tr_search) |
            Q(student__last_name__icontains=tr_search) |
            Q(route__route_name__icontains=tr_search)
        )

    total_bus_routes = BusRoute.objects.count()
    total_transport_capacity = BusRoute.objects.aggregate(Sum('capacity'))['capacity__sum'] or 0
    total_transport_occupied = TransportAllocation.objects.filter(status='Active').count()
    total_transport_available = max(total_transport_capacity - total_transport_occupied, 0)

    transport_fee_payments = (
        TransportFeePayment.objects.select_related('allocation', 'allocation__student', 'allocation__route')
        .order_by('-payment_date')
    )
    active_transport_allocations = TransportAllocation.objects.filter(status='Active').select_related('student', 'route')

    context = {
        'site_settings': SiteSettings.load(),
        'departments': departments,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_income': total_income,
        'total_expense': total_expense,
        'filtered_income': filtered_income,    # পাই চার্টের জন্য নির্দিষ্ট সময়ের আয়
        'filtered_expense': filtered_expense,   # পাই চার্টের জন্য নির্দিষ্ট সময়ের ব্যয়
        'net_profit': abs(net_profit),          # পজিটিভ মান (লাভ বা ক্ষতি)
        'raw_net_profit': net_profit,
        'profit_status': profit_status,        # profit, loss অথবা balanced
        'recent_notices': Notice.objects.all().order_by('-created_at')[:30],
        'teachers': teacher_qs,
        'students': student_qs,
        'fees': fee_qs,
        'transactions': Transaction.objects.all().order_by('-created_at'),
        'salary_payments': SalaryPayment.objects.all().order_by('-payment_date'),
        'routines': routines,
        'routine_grid': routine_grid,
        'routine_days_order': DAY_ORDER,
        'exam_routines': exam_routines,
        'due_students': due_students,
        'fee_structures': fee_structures,
        'att_date': att_date_str,
        'attendance_rows': attendance_rows,
        'student_att_summary': student_att_summary,
        'teacher_att_date': teacher_att_date_str,
        'teacher_attendance_rows': teacher_attendance_rows,
        'teacher_att_summary': teacher_att_summary,
        'books': book_qs,
        'total_books': total_books,
        'total_book_copies': total_book_copies,
        'total_issued_books': total_issued_books,
        'total_available_copies': total_available_copies,
        'book_categories': book_categories,
        'book_issues': book_issues,
        'issue_status': issue_status,
        'overdue_book_count': overdue_book_count,
        'today': today,
        'hostels': hostels,
        'hostel_rooms': hostel_rooms_qs,
        'hostel_allocations': hostel_allocations,
        'total_hostels': total_hostels,
        'total_hostel_rooms': total_hostel_rooms,
        'total_hostel_capacity': total_hostel_capacity,
        'total_hostel_occupied': total_hostel_occupied,
        'total_hostel_available': total_hostel_available,
        'hs_search': hs_search,
        'bus_routes': bus_routes,
        'bus_stops': bus_stops,
        'transport_allocations': transport_allocations_qs,
        'active_transport_allocations': active_transport_allocations,
        'transport_fee_payments': transport_fee_payments,
        'total_bus_routes': total_bus_routes,
        'total_transport_capacity': total_transport_capacity,
        'total_transport_occupied': total_transport_occupied,
        'total_transport_available': total_transport_available,
        'tr_search': tr_search,
    }
    return render(request, 'index.html', context)


# Action Views
def add_teacher(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if Teacher.objects.filter(email=email).exists():
            messages.error(request, 'Error: A teacher with this email already exists!')
            return redirect('index')

        Teacher.objects.create(
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            email=email,
            phone=request.POST.get('phone'),
            department_id=request.POST.get('department'),
            shift=request.POST.get('shift', ''),
            designation=request.POST.get('designation'),
            salary=request.POST.get('salary'),
            teacher_image=request.FILES.get('teacher_image'),
        )
        messages.success(request, 'Teacher added successfully!')
    return redirect('index')


def edit_teacher(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == 'POST':
        teacher.first_name = request.POST.get('first_name')
        teacher.last_name = request.POST.get('last_name')
        teacher.email = request.POST.get('email')
        teacher.phone = request.POST.get('phone')
        teacher.department_id = request.POST.get('department')
        teacher.shift = request.POST.get('shift', '')
        teacher.designation = request.POST.get('designation')
        teacher.salary = request.POST.get('salary')

        if request.FILES.get('teacher_image'):
            teacher.teacher_image = request.FILES.get('teacher_image')

        teacher.save()
        messages.success(request, 'Teacher updated successfully!')
        return redirect('index')

    departments = Department.objects.all()
    return render(request, 'edit_teacher.html', {'teacher': teacher, 'departments': departments})


def delete_teacher(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    teacher.delete()
    messages.success(request, 'Teacher deleted successfully!')
    return redirect('index')


def pay_salary(request):
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher')
        amount = request.POST.get('amount')
        month = request.POST.get('month')
        year = request.POST.get('year')
        note = request.POST.get('note', '')

        # Check if already paid for this month and year
        if SalaryPayment.objects.filter(teacher_id=teacher_id, month=month, year=year).exists():
            messages.error(request, f'Salary for {month} {year} has already been paid to this teacher!')
            return redirect('index')

        SalaryPayment.objects.create(
            teacher_id=teacher_id,
            amount=amount,
            month=month,
            year=year,
            note=note
        )
        messages.success(request, 'Salary paid successfully!')
    return redirect('index')


def add_student(request):
    if request.method == 'POST':
        # ইমেজ ফাইল রিসিভ করা হচ্ছে
        student_image = request.FILES.get('student_image')

        Student.objects.create(
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            roll=request.POST.get('roll'),
            department_id=request.POST.get('department'),
            shift=request.POST.get('shift'),
            semester=request.POST.get('semester'),
            email=request.POST.get('email'),
            phone=request.POST.get('phone'),
            student_image=student_image  # ইমেজ ফিল্ড ডাটাবেজে সেভ করা হচ্ছে
        )
        messages.success(request, 'Student enrolled successfully!')
    return redirect('index')

def edit_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        # ফর্ম থেকে ডাটা রিসিভ করে আপডেট করা
        student.first_name = request.POST.get('first_name')
        student.last_name = request.POST.get('last_name')
        student.roll = request.POST.get('roll')
        student.phone = request.POST.get('phone')
        student.email = request.POST.get('email')
        
        # যদি ছবি আপলোড করা হয়
        if request.FILES.get('student_image'):
            student.student_image = request.FILES.get('student_image')
            
        student.save()
        messages.success(request, 'Student updated successfully!')
        return redirect('index') # আপডেট হওয়ার পর ড্যাশবোর্ড বা হোম পেজে নিয়ে যাবে
        
    return render(request, 'edit_student.html', {'student': student})

def delete_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.delete()
    messages.success(request, 'Student deleted successfully!')
    return redirect('index') # ডিলিট করার পর ড্যাশবোর্ড বা আগের পেজে রিডায়রেক্ট করবে


def add_fee(request):
    if request.method == 'POST':
        Fee.objects.create(
            student_id=request.POST.get('student'),
            amount=request.POST.get('amount'),
        )
        messages.success(request, 'Fee collected successfully!')
    return redirect('index')


def fee_receipt(request, pk):
    """Printable/downloadable money receipt for a student fee payment."""
    fee = get_object_or_404(Fee.objects.select_related('student', 'student__department'), pk=pk)
    return render(request, 'fee_receipt.html', {'fee': fee})


def salary_receipt(request, pk):
    """Printable/downloadable payment voucher for a teacher salary payment."""
    payment = get_object_or_404(
        SalaryPayment.objects.select_related('teacher', 'teacher__department'), pk=pk
    )
    return render(request, 'salary_receipt.html', {'payment': payment})


def add_fee_structure(request):
    """Set/update the expected total fee for a department + shift + semester group,
    used by the Due Fees Tracker to calculate outstanding dues."""
    if request.method == 'POST':
        FeeStructure.objects.update_or_create(
            department_id=request.POST.get('department'),
            shift=request.POST.get('shift'),
            semester=request.POST.get('semester'),
            defaults={'total_amount': request.POST.get('total_amount')},
        )
        messages.success(request, 'Fee structure saved successfully!')
    return redirect('index')


def add_transaction(request):
    if request.method == 'POST':
        Transaction.objects.create(
            title=request.POST.get('title'),
            type=request.POST.get('type'),
            amount=request.POST.get('amount'),
        )
        messages.success(request, 'Transaction added successfully!')
    return redirect('index')


def notice_broadcaster(request):
    if request.method == 'POST':
        notice = Notice.objects.create(
            title=request.POST.get('title'),
            recipients=request.POST.get('recipients'),
            content=request.POST.get('content'),
            is_urgent=request.POST.get('is_urgent') == 'on',
            signatory_name=request.POST.get('signatory_name') or '',
            signatory_designation=request.POST.get('signatory_designation') or 'Principal',
        )
        generate_notice_image(notice)
        messages.success(request, 'Notice published successfully!')
    return redirect('index')


def edit_notice(request, pk):
    """Updates a notice and re-generates its image. Rendered via an
    in-page modal on the Notice Broadcaster view rather than a separate
    template, so this only ever receives POST submissions; GET simply
    redirects back."""
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        notice.title = request.POST.get('title')
        notice.recipients = request.POST.get('recipients')
        notice.content = request.POST.get('content')
        notice.is_urgent = request.POST.get('is_urgent') == 'on'
        notice.signatory_name = request.POST.get('signatory_name') or ''
        notice.signatory_designation = request.POST.get('signatory_designation') or 'Principal'
        notice.save()
        generate_notice_image(notice)
        messages.success(request, 'Notice updated successfully!')
    return redirect('index')


def delete_notice(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    notice.delete()
    messages.success(request, 'Notice deleted successfully!')
    return redirect('index')


# ===== Class Routine =====
def add_routine(request):
    if request.method == 'POST':
        ClassRoutine.objects.create(
            department_id=request.POST.get('department'),
            shift=request.POST.get('shift'),
            semester=request.POST.get('semester'),
            day=request.POST.get('day'),
            subject=request.POST.get('subject'),
            teacher_id=request.POST.get('teacher') or None,
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            room_no=request.POST.get('room_no'),
        )
        messages.success(request, 'Class routine entry added successfully!')
    return redirect('index')


def delete_routine(request, pk):
    routine = get_object_or_404(ClassRoutine, pk=pk)
    routine.delete()
    messages.success(request, 'Routine entry deleted successfully!')
    return redirect('index')


# ===== Exam Routine =====
def add_exam_routine(request):
    if request.method == 'POST':
        ExamRoutine.objects.create(
            department_id=request.POST.get('department'),
            semester=request.POST.get('semester'),
            subject=request.POST.get('subject'),
            exam_date=request.POST.get('exam_date'),
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            room_no=request.POST.get('room_no'),
        )
        messages.success(request, 'Exam routine entry added successfully!')
    return redirect('index')


def delete_exam_routine(request, pk):
    exam_routine = get_object_or_404(ExamRoutine, pk=pk)
    exam_routine.delete()
    messages.success(request, 'Exam routine entry deleted successfully!')
    return redirect('index')


# ===== Exam Marks / Marksheet =====
def add_exam_marks(request):
    if request.method == 'POST':
        student_id = request.POST.get('student')
        semester = request.POST.get('semester')
        subjects = request.POST.getlist('subject[]')
        full_marks_list = request.POST.getlist('full_marks[]')
        obtained_list = request.POST.getlist('marks_obtained[]')

        if not student_id or not semester or not subjects:
            messages.error(request, 'Please select a student, semester, and add at least one subject.')
            return redirect('index')

        student = get_object_or_404(Student, pk=student_id)

        # Re-submitting for the same student & semester regenerates the marksheet from scratch
        ExamMark.objects.filter(student=student, semester=semester).delete()

        for subject, full_marks, obtained in zip(subjects, full_marks_list, obtained_list):
            if not subject:
                continue
            ExamMark.objects.create(
                student=student,
                semester=semester,
                subject=subject,
                full_marks=full_marks or 100,
                marks_obtained=obtained or 0,
            )

        messages.success(request, f'Marksheet generated for {student.first_name} {student.last_name} ({semester} Semester)!')
    return redirect('index')


def get_student_marksheet(request, pk):
    student = get_object_or_404(Student, pk=pk)
    semester = request.GET.get('semester', '1st')

    marks = ExamMark.objects.filter(student=student, semester=semester).order_by('subject')

    subjects_data = []
    total_obtained = 0
    total_full = 0
    for m in marks:
        percentage = (float(m.marks_obtained) / m.full_marks * 100) if m.full_marks else 0
        subjects_data.append({
            'subject': m.subject,
            'full_marks': m.full_marks,
            'marks_obtained': str(m.marks_obtained),
            'grade': calculate_grade(percentage),
        })
        total_obtained += float(m.marks_obtained)
        total_full += m.full_marks

    overall_percentage = round((total_obtained / total_full * 100), 2) if total_full else 0
    semester_label = dict(Student.SEMESTER_CHOICES).get(semester, semester)

    payload = {
        'student': f'{student.first_name} {student.last_name}',
        'roll': student.roll,
        'semester': semester,
        'subjects': subjects_data,
        'total_obtained': total_obtained,
        'total_full': total_full,
        'percentage': overall_percentage,
        'grade': calculate_grade(overall_percentage),
        'has_data': len(subjects_data) > 0,
    }

    # Keep JSON available for any existing AJAX/API callers (e.g. the admin
    # dashboard's Marksheet modal, which calls this via plain fetch()), but
    # render a proper page for normal browser navigation (the student sidebar
    # link). We tell the two apart using the Accept header: a real browser
    # navigation sends "Accept: text/html,...", while a bare fetch() call
    # (as used in index.html) does not — so index.html needs no changes.
    accept_header = request.headers.get('accept', '')
    wants_json = (
        request.GET.get('format') == 'json'
        or request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'text/html' not in accept_header
    )
    if wants_json:
        return JsonResponse(payload)

    return render(request, 'accounts/marksheet.html', {
        **payload,
        'student': student,
        'semester_label': semester_label,
        'semester_choices': Student.SEMESTER_CHOICES,
    })


# ===== Digital ID Card Generator =====
def student_id_card(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'id_card_student.html', {
        'student': student,
        'card_year': localdate().year,
    })


def teacher_id_card(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    return render(request, 'id_card_teacher.html', {
        'teacher': teacher,
        'card_year': localdate().year,
    })


# ===== Daily Attendance Tracking =====
def mark_student_attendance(request):
    """Bulk save Present/Absent/Late status for a set of students on a given date.
    Re-submitting for the same student & date overwrites that day's status."""
    if request.method == 'POST':
        att_date = request.POST.get('att_date')
        student_ids = request.POST.getlist('student_id[]')
        statuses = request.POST.getlist('status[]')

        saved_count = 0
        for student_id, status in zip(student_ids, statuses):
            if not student_id or not status:
                continue
            StudentAttendance.objects.update_or_create(
                student_id=student_id,
                date=att_date,
                defaults={'status': status},
            )
            saved_count += 1

        messages.success(request, f'Attendance saved for {saved_count} student(s) on {att_date}.')
    return redirect('index')


def mark_teacher_attendance(request):
    """Bulk save Present/Absent/Late status for a set of teachers on a given date.
    Re-submitting for the same teacher & date overwrites that day's status."""
    if request.method == 'POST':
        att_date = request.POST.get('att_date')
        teacher_ids = request.POST.getlist('teacher_id[]')
        statuses = request.POST.getlist('status[]')

        saved_count = 0
        for teacher_id, status in zip(teacher_ids, statuses):
            if not teacher_id or not status:
                continue
            TeacherAttendance.objects.update_or_create(
                teacher_id=teacher_id,
                date=att_date,
                defaults={'status': status},
            )
            saved_count += 1

        messages.success(request, f'Attendance saved for {saved_count} teacher(s) on {att_date}.')
    return redirect('index')


def get_student_attendance_report(request, pk):
    """JSON monthly attendance report for a single student (Present/Absent/Late counts
    and an attendance percentage). Present and Late days both count as 'attended' days
    for the percentage, since a Late student still attended that day."""
    student = get_object_or_404(Student, pk=pk)
    today = localdate()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    records = StudentAttendance.objects.filter(student=student, date__year=year, date__month=month).order_by('date')

    present = records.filter(status='Present').count()
    absent = records.filter(status='Absent').count()
    late = records.filter(status='Late').count()
    total = records.count()

    percentage = round(((present + late) / total * 100), 2) if total else 0

    payload = {
        'name': f'{student.first_name} {student.last_name}',
        'roll': student.roll,
        'month': month,
        'year': year,
        'present': present,
        'absent': absent,
        'late': late,
        'total_days': total,
        'percentage': percentage,
        'has_data': total > 0,
        'records': [{'date': r.date.strftime('%d %b %Y'), 'status': r.status} for r in records],
    }

    # Keep JSON available for any existing AJAX/API callers (e.g. the admin
    # dashboard's attendance report modal, which calls this via plain fetch()),
    # but render a proper page for normal browser navigation (the student
    # sidebar link). Same Accept-header detection as get_student_marksheet
    # above — no changes needed in index.html.
    accept_header = request.headers.get('accept', '')
    wants_json = (
        request.GET.get('format') == 'json'
        or request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'text/html' not in accept_header
    )
    if wants_json:
        return JsonResponse(payload)

    month_choices = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]
    month_name = dict(month_choices).get(month, month)

    return render(request, 'accounts/attendance_report.html', {
        **payload,
        'student': student,
        'month_name': month_name,
        'month_choices': month_choices,
        'year_choices': range(today.year - 3, today.year + 1),
    })


def get_teacher_attendance_report(request, pk):
    """JSON monthly attendance report for a single teacher (Present/Absent/Late counts
    and an attendance percentage). Present and Late days both count as 'attended' days
    for the percentage, since a Late teacher still attended that day."""
    teacher = get_object_or_404(Teacher, pk=pk)
    today = localdate()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    records = TeacherAttendance.objects.filter(teacher=teacher, date__year=year, date__month=month).order_by('date')

    present = records.filter(status='Present').count()
    absent = records.filter(status='Absent').count()
    late = records.filter(status='Late').count()
    total = records.count()

    percentage = round(((present + late) / total * 100), 2) if total else 0

    return JsonResponse({
        'name': f'{teacher.first_name} {teacher.last_name}',
        'month': month,
        'year': year,
        'present': present,
        'absent': absent,
        'late': late,
        'total_days': total,
        'percentage': percentage,
        'has_data': total > 0,
        'records': [{'date': r.date.strftime('%d %b %Y'), 'status': r.status} for r in records],
    })


# ===== Library Management =====
def add_book(request):
    if request.method == 'POST':
        isbn = request.POST.get('isbn') or None
        if isbn and Book.objects.filter(isbn=isbn).exists():
            messages.error(request, f'A book with ISBN {isbn} already exists in the catalog!')
            return redirect('index')

        Book.objects.create(
            title=request.POST.get('title'),
            author=request.POST.get('author'),
            isbn=isbn,
            category=request.POST.get('category', ''),
            publisher=request.POST.get('publisher', ''),
            total_copies=request.POST.get('total_copies') or 1,
            shelf_location=request.POST.get('shelf_location', ''),
        )
        messages.success(request, 'Book added to the library catalog successfully!')
    return redirect('index')


def edit_book(request, pk):
    """Updates book details/stock. Rendered via an in-page modal on the Library
    Management view rather than a separate template, so this only ever
    receives POST submissions; GET simply redirects back."""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        isbn = request.POST.get('isbn') or None
        if isbn and Book.objects.filter(isbn=isbn).exclude(pk=book.pk).exists():
            messages.error(request, f'Another book already uses ISBN {isbn}!')
            return redirect('index')

        new_total = request.POST.get('total_copies')
        if new_total is not None and int(new_total) < book.issued_count:
            messages.error(
                request,
                f'Cannot set total copies below {book.issued_count} — that many copies of '
                f'"{book.title}" are currently issued and not yet returned.'
            )
            return redirect('index')

        book.title = request.POST.get('title')
        book.author = request.POST.get('author')
        book.isbn = isbn
        book.category = request.POST.get('category', '')
        book.publisher = request.POST.get('publisher', '')
        book.total_copies = new_total or book.total_copies
        book.shelf_location = request.POST.get('shelf_location', '')
        book.save()
        messages.success(request, 'Book details updated successfully!')
    return redirect('index')


def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if book.issues.filter(return_date__isnull=True).exists():
        messages.error(request, f'Cannot delete "{book.title}" — it has copies currently issued and not yet returned.')
        return redirect('index')
    book.delete()
    messages.success(request, 'Book removed from the library catalog.')
    return redirect('index')


def issue_book(request):
    """Issues one copy of a book to either a student or a teacher."""
    if request.method == 'POST':
        book_id = request.POST.get('book')
        borrower_type = request.POST.get('borrower_type')
        student_id = request.POST.get('student') or None
        teacher_id = request.POST.get('teacher') or None
        issue_date = request.POST.get('issue_date')
        due_date = request.POST.get('due_date')

        book = get_object_or_404(Book, pk=book_id)

        if book.available_copies <= 0:
            messages.error(request, f'No available copies of "{book.title}" left to issue right now.')
            return redirect('index')

        if borrower_type == 'Student' and not student_id:
            messages.error(request, 'Please select a student to issue this book to.')
            return redirect('index')
        if borrower_type == 'Teacher' and not teacher_id:
            messages.error(request, 'Please select a teacher to issue this book to.')
            return redirect('index')

        BookIssue.objects.create(
            book=book,
            borrower_type=borrower_type,
            student_id=student_id if borrower_type == 'Student' else None,
            teacher_id=teacher_id if borrower_type == 'Teacher' else None,
            issue_date=issue_date,
            due_date=due_date,
        )
        messages.success(request, f'"{book.title}" issued successfully!')
    return redirect('index')


def return_book(request, pk):
    """Marks a single book-issue record as returned (sets return_date)."""
    issue = get_object_or_404(BookIssue, pk=pk)
    if request.method == 'POST':
        if issue.return_date:
            messages.info(request, 'This book has already been marked as returned.')
            return redirect('index')
        issue.return_date = request.POST.get('return_date') or localdate()
        issue.save()
        messages.success(request, f'"{issue.book.title}" marked as returned.')
    return redirect('index')


# ===== Hostel Management Views =====
# Fully additive: does not touch any existing view or feature.

def add_hostel(request):
    if request.method == 'POST':
        Hostel.objects.create(
            name=request.POST.get('name'),
            hostel_type=request.POST.get('hostel_type'),
            warden_name=request.POST.get('warden_name', ''),
            warden_phone=request.POST.get('warden_phone', ''),
            address=request.POST.get('address', ''),
        )
        messages.success(request, 'Hostel added successfully!')
    return redirect('index')


def edit_hostel(request, pk):
    """Updates hostel details. Rendered via an in-page modal on the Hostel
    Management view rather than a separate template, so this only ever
    receives POST submissions; GET simply redirects back."""
    hostel = get_object_or_404(Hostel, pk=pk)
    if request.method == 'POST':
        hostel.name = request.POST.get('name')
        hostel.hostel_type = request.POST.get('hostel_type')
        hostel.warden_name = request.POST.get('warden_name', '')
        hostel.warden_phone = request.POST.get('warden_phone', '')
        hostel.address = request.POST.get('address', '')
        hostel.save()
        messages.success(request, 'Hostel details updated successfully!')
    return redirect('index')


def delete_hostel(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    if HostelAllocation.objects.filter(room__hostel=hostel, status='Active').exists():
        messages.error(request, f'Cannot delete "{hostel.name}" — it has residents currently allocated to its rooms.')
        return redirect('index')
    hostel.delete()
    messages.success(request, 'Hostel removed successfully.')
    return redirect('index')


def add_hostel_room(request):
    if request.method == 'POST':
        hostel_id = request.POST.get('hostel')
        room_no = request.POST.get('room_no')
        if HostelRoom.objects.filter(hostel_id=hostel_id, room_no=room_no).exists():
            messages.error(request, f'Room {room_no} already exists in this hostel!')
            return redirect('index')

        HostelRoom.objects.create(
            hostel_id=hostel_id,
            room_no=room_no,
            room_type=request.POST.get('room_type'),
            capacity=request.POST.get('capacity') or 1,
            monthly_rent=request.POST.get('monthly_rent') or 0,
        )
        messages.success(request, 'Room added successfully!')
    return redirect('index')


def edit_hostel_room(request, pk):
    """Updates room details/capacity. Rendered via an in-page modal, so this
    only ever receives POST submissions; GET simply redirects back."""
    room = get_object_or_404(HostelRoom, pk=pk)
    if request.method == 'POST':
        new_capacity = request.POST.get('capacity')
        if new_capacity is not None and int(new_capacity) < room.occupied_seats:
            messages.error(
                request,
                f'Cannot set capacity below {room.occupied_seats} — that many seats in '
                f'Room {room.room_no} are currently occupied.'
            )
            return redirect('index')

        room.room_no = request.POST.get('room_no')
        room.room_type = request.POST.get('room_type')
        room.capacity = new_capacity or room.capacity
        room.monthly_rent = request.POST.get('monthly_rent') or room.monthly_rent
        room.save()
        messages.success(request, 'Room details updated successfully!')
    return redirect('index')


def delete_hostel_room(request, pk):
    room = get_object_or_404(HostelRoom, pk=pk)
    if room.allocations.filter(status='Active').exists():
        messages.error(request, f'Cannot delete Room {room.room_no} — it currently has residents allocated to it.')
        return redirect('index')
    room.delete()
    messages.success(request, 'Room removed successfully.')
    return redirect('index')


def allocate_hostel_seat(request):
    """Allocates one seat/bed in a room to a student."""
    if request.method == 'POST':
        room_id = request.POST.get('room')
        student_id = request.POST.get('student')
        room = get_object_or_404(HostelRoom, pk=room_id)

        if room.available_seats <= 0:
            messages.error(request, f'No available seats left in Room {room.room_no} right now.')
            return redirect('index')

        if HostelAllocation.objects.filter(student_id=student_id, status='Active').exists():
            messages.error(request, 'This student already has an active hostel seat allocation.')
            return redirect('index')

        HostelAllocation.objects.create(
            room=room,
            student_id=student_id,
            bed_no=request.POST.get('bed_no', ''),
            allocation_date=request.POST.get('allocation_date') or localdate(),
        )
        messages.success(request, 'Hostel seat allocated successfully!')
    return redirect('index')


def vacate_hostel_seat(request, pk):
    """Marks a hostel allocation as vacated (frees up the seat)."""
    allocation = get_object_or_404(HostelAllocation, pk=pk)
    if request.method == 'POST':
        if allocation.status == 'Vacated':
            messages.info(request, 'This seat has already been vacated.')
            return redirect('index')
        allocation.status = 'Vacated'
        allocation.vacate_date = request.POST.get('vacate_date') or localdate()
        allocation.save()
        messages.success(request, f'{allocation.student.roll} has vacated Room {allocation.room.room_no}.')
    return redirect('index')


def delete_hostel_allocation(request, pk):
    allocation = get_object_or_404(HostelAllocation, pk=pk)
    allocation.delete()
    messages.success(request, 'Hostel allocation record deleted.')
    return redirect('index')


# ===== Transport Management Views =====
# Fully additive: does not touch any existing view or feature.

def add_bus_route(request):
    if request.method == 'POST':
        BusRoute.objects.create(
            route_name=request.POST.get('route_name'),
            vehicle_no=request.POST.get('vehicle_no'),
            driver_name=request.POST.get('driver_name', ''),
            driver_phone=request.POST.get('driver_phone', ''),
            capacity=request.POST.get('capacity') or 40,
            monthly_fee=request.POST.get('monthly_fee') or 0,
        )
        messages.success(request, 'Bus route added successfully!')
    return redirect('index')


def edit_bus_route(request, pk):
    """Updates route details/capacity. Rendered via an in-page modal, so this
    only ever receives POST submissions; GET simply redirects back."""
    route = get_object_or_404(BusRoute, pk=pk)
    if request.method == 'POST':
        new_capacity = request.POST.get('capacity')
        if new_capacity is not None and int(new_capacity) < route.occupied_seats:
            messages.error(
                request,
                f'Cannot set capacity below {route.occupied_seats} — that many seats on '
                f'"{route.route_name}" are currently allocated.'
            )
            return redirect('index')

        route.route_name = request.POST.get('route_name')
        route.vehicle_no = request.POST.get('vehicle_no')
        route.driver_name = request.POST.get('driver_name', '')
        route.driver_phone = request.POST.get('driver_phone', '')
        route.capacity = new_capacity or route.capacity
        route.monthly_fee = request.POST.get('monthly_fee') or route.monthly_fee
        route.save()
        messages.success(request, 'Bus route updated successfully!')
    return redirect('index')


def delete_bus_route(request, pk):
    route = get_object_or_404(BusRoute, pk=pk)
    if route.transport_allocations.filter(status='Active').exists():
        messages.error(request, f'Cannot delete "{route.route_name}" — it has students currently allocated to it.')
        return redirect('index')
    route.delete()
    messages.success(request, 'Bus route removed successfully.')
    return redirect('index')


def add_bus_stop(request):
    if request.method == 'POST':
        BusStop.objects.create(
            route_id=request.POST.get('route'),
            stop_name=request.POST.get('stop_name'),
            stop_order=request.POST.get('stop_order') or 1,
            pickup_time=request.POST.get('pickup_time') or None,
        )
        messages.success(request, 'Bus stop added successfully!')
    return redirect('index')


def delete_bus_stop(request, pk):
    stop = get_object_or_404(BusStop, pk=pk)
    stop.delete()
    messages.success(request, 'Bus stop removed successfully.')
    return redirect('index')


def allocate_transport(request):
    """Allocates one seat on a bus route to a student."""
    if request.method == 'POST':
        route_id = request.POST.get('route')
        student_id = request.POST.get('student')
        stop_id = request.POST.get('stop') or None
        route = get_object_or_404(BusRoute, pk=route_id)

        if route.available_seats <= 0:
            messages.error(request, f'No available seats left on "{route.route_name}" right now.')
            return redirect('index')

        if TransportAllocation.objects.filter(student_id=student_id, status='Active').exists():
            messages.error(request, 'This student already has an active transport seat allocation.')
            return redirect('index')

        TransportAllocation.objects.create(
            student_id=student_id,
            route=route,
            stop_id=stop_id,
            allocation_date=request.POST.get('allocation_date') or localdate(),
        )
        messages.success(request, 'Transport seat allocated successfully!')
    return redirect('index')


def deactivate_transport(request, pk):
    """Marks a transport allocation as inactive (frees up the seat)."""
    allocation = get_object_or_404(TransportAllocation, pk=pk)
    if request.method == 'POST':
        if allocation.status == 'Inactive':
            messages.info(request, 'This transport allocation is already inactive.')
            return redirect('index')
        allocation.status = 'Inactive'
        allocation.save()
        messages.success(request, f'{allocation.student.roll} has been removed from "{allocation.route.route_name}".')
    return redirect('index')


def delete_transport_allocation(request, pk):
    allocation = get_object_or_404(TransportAllocation, pk=pk)
    allocation.delete()
    messages.success(request, 'Transport allocation record deleted.')
    return redirect('index')


def add_transport_fee(request):
    if request.method == 'POST':
        allocation_id = request.POST.get('allocation')
        month = request.POST.get('month')
        year = request.POST.get('year')

        if TransportFeePayment.objects.filter(allocation_id=allocation_id, month=month, year=year).exists():
            messages.error(request, f'Transport fee for {month} {year} has already been recorded for this student.')
            return redirect('index')

        TransportFeePayment.objects.create(
            allocation_id=allocation_id,
            amount=request.POST.get('amount'),
            month=month,
            year=year,
            note=request.POST.get('note', ''),
        )
        messages.success(request, 'Transport fee recorded successfully!')
    return redirect('index')

# ---------------------------------------------------------------------------
# Admin: Profile & Password Management (AJAX)
# ---------------------------------------------------------------------------

def admin_update_profile(request):
    """AJAX — Admin updates their own name, email, and optionally avatar."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Not authenticated.'})
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method.'})

    try:
        user = request.user
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        image      = request.FILES.get('profile_image')

        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        user.save()

        # If admin is linked to a Teacher record, sync there too
        profile = getattr(user, 'profile', None)
        if profile and getattr(profile, 'teacher', None):
            t = profile.teacher
            if first_name: t.first_name = first_name
            if last_name:  t.last_name  = last_name
            if email:      t.email      = email
            if image:      t.teacher_image = image
            t.save()

        initials = ((user.first_name[:1] + user.last_name[:1]) or user.username[:2]).upper()
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            'initials': initials,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


def update_site_branding(request):
    """AJAX — Update the college name & logo shown across the dashboard
    (sidebar brand box, sidebar title, and the top-right avatar button)."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Not authenticated.'})
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method.'})

    try:
        site = SiteSettings.load()
        college_name = request.POST.get('college_name', '').strip()
        logo = request.FILES.get('logo')

        if college_name:
            site.college_name = college_name
        if logo:
            site.logo = logo
        site.save()

        return JsonResponse({
            'success': True,
            'message': 'Branding updated successfully!',
            'college_name': site.college_name,
            'logo_url': site.logo.url if site.logo else '',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


def admin_change_password(request):
    """AJAX — Admin changes their own password."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Not authenticated.'})
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method.'})

    user             = request.user
    current_password = request.POST.get('current_password', '')
    new_password     = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not user.check_password(current_password):
        return JsonResponse({'success': False, 'message': 'Current password is incorrect.'})
    if len(new_password) < 8:
        return JsonResponse({'success': False, 'message': 'New password must be at least 8 characters.'})
    if new_password != confirm_password:
        return JsonResponse({'success': False, 'message': 'Passwords do not match.'})

    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    return JsonResponse({'success': True, 'message': 'Password changed successfully!'})