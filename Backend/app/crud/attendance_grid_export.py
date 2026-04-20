import io
import csv
from datetime import date
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from .attendance_crud import build_monthly_attendance_grid
from reportlab.platypus import Table
from reportlab.lib.styles import ParagraphStyle
from app.db.models.user import User
from app.db.models.attendance import Attendance
from app.db.models.leave import Leave
from datetime import datetime, timedelta, date as _date
from calendar import monthrange
from reportlab.lib.enums import TA_CENTER


def draw_page_border(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.lightgrey)
    canvas.setLineWidth(0.5)  # small/thin border

    # Page size (landscape A4)
    width, height = landscape(A4)

    margin = 10  # distance from edge
    canvas.rect(
        margin,
        margin,
        width - (2 * margin),
        height - (2 * margin),
        stroke=1,
        fill=0
    )
    canvas.restoreState()


def export_monthly_grid_csv(
    db,
    month,
    year,
    department=None,
    employee_id=None,
    status=None,
    current_user=None,
):
    """
    Export Monthly Attendance Grid to CSV (Excel-style layout exactly like image)
    Applies filters to the data after generation, not during.
    """
    data = build_monthly_attendance_grid(
        db,
        month,
        year,
        department,
        current_user=current_user,
    )
    
    # Apply additional filters to rows
    filtered_rows = []
    for row in data["rows"]:
        # Filter by employee_id
        if employee_id and row["employee_id"] != employee_id:
            continue
        
        # Filter attendance by date range and status
        filtered_attendance = {}
        for day_str, attendance_value in row["attendance"].items():
            # Check status filter
            if status:
                status_upper = status.upper()
                if status_upper == "PRESENT" and attendance_value != "P":
                    continue
                elif status_upper == "ABSENT" and attendance_value != "A":
                    continue
                elif status_upper == "LEAVE" and attendance_value != "L":
                    continue
                elif status_upper == "WFH" and attendance_value != "WFH":
                    continue
            
            filtered_attendance[day_str] = attendance_value
        
        filtered_rows.append({
            "employee_id": row["employee_id"],
            "name": row["name"],
            "attendance": filtered_attendance
        })
    
    # Update data with filtered rows
    data["rows"] = filtered_rows
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([data["title"]])
    writer.writerow([
        "Duration", data["duration"],
        "", "", "Printed", data["printed_on"]
    ])
    writer.writerow([])
    header_days = ["No.", "Employee ID", "Name"]
    header_weekdays = ["", "", ""]
    for day in data["days"]:
        header_days.append(day["day"])
        header_weekdays.append(day["weekday"])
    writer.writerow(header_days)
    writer.writerow(header_weekdays)
    for index, row in enumerate(data["rows"], start=1):
        record = [index, row["employee_id"], row["name"]]
        for day in data["days"]:
            record.append(row["attendance"].get(str(day["day"]), ""))
        writer.writerow(record)
    output.seek(0)
    return output

def export_monthly_grid_pdf(
    db,
    month,
    year,
    department=None,
    employee_id=None,
    status=None,
    current_user=None,
):
    """
    Export Monthly Attendance Grid to PDF (Excel-like layout, landscape)
    Applies filters to the data after generation, not during.
    """
    # Get base data without extra filters
    data = build_monthly_attendance_grid(
        db,
        month,
        year,
        department,
        current_user=current_user,
    )
    
    # Apply additional filters to rows
    filtered_rows = []
    for row in data["rows"]:
        # Filter by employee_id
        if employee_id and row["employee_id"] != employee_id:
            continue
        
        # Filter attendance by date range and status
        filtered_attendance = {}
        for day_str, attendance_value in row["attendance"].items():
            # Check status filter
            if status:
                status_upper = status.upper()
                if status_upper == "PRESENT" and attendance_value != "P":
                    continue
                elif status_upper == "ABSENT" and attendance_value != "A":
                    continue
                elif status_upper == "LEAVE" and attendance_value != "L":
                    continue
                elif status_upper == "WFH" and attendance_value != "WFH":
                    continue
            
            filtered_attendance[day_str] = attendance_value
        
        filtered_rows.append({
            "employee_id": row["employee_id"],
            "name": row["name"],
            "attendance": filtered_attendance
        })
    
    # Update data with filtered rows
    data["rows"] = filtered_rows
    buffer = io.BytesIO()

    # Page setup with proper margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    elements = []

    # -------------------------
    # Title
    # -------------------------
    elements.append(
        Paragraph(f"<b>{data['title']}</b>", styles["Title"])
    )

    # -------------------------
    # Duration & Printed (PROPER spacing using table)
    # -------------------------
    info_table = Table(
        [[
            f"Duration: {data['duration']}",
            f"Printed: {data['printed_on']}"
        ]],
        colWidths=[150, 150]   # spacing control
    )

    info_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(info_table)

    # -------------------------
    # Build table data
    # -------------------------
    table_data = []

    header_days = ["No.", "Employee ID", "Name"]
    header_weekdays = ["", "", ""]

    for day in data["days"]:
        header_days.append(str(day["day"]))
        header_weekdays.append(day["weekday"])

    table_data.append(header_days)
    table_data.append(header_weekdays)

    for index, row in enumerate(data["rows"], start=1):
        record = [str(index), row["employee_id"], row["name"]]
        for day in data["days"]:
            record.append(row["attendance"].get(str(day["day"]), ""))
        table_data.append(record)

    total_columns = len(header_days)
    page_width = A4[1]  # landscape width

    # Compute available width inside page margins
    available_width = page_width - doc.leftMargin - doc.rightMargin

    # Fixed widths for the first three columns
    fixed_cols = [35, 70, 120]
    fixed_total = sum(fixed_cols)

    remaining_columns = max(total_columns - len(fixed_cols), 1)
    remaining_width = available_width - fixed_total

    # Sensible min/max per-day column widths to avoid stretching
    per_day_min = 12
    per_day_max = 18
    if remaining_width <= remaining_columns * per_day_min:
        per_day = per_day_min
    else:
        per_day = min(per_day_max, float(remaining_width) / remaining_columns)

    col_widths = fixed_cols + [per_day] * remaining_columns

    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=2,
        hAlign="LEFT"
    )

    # -------------------------
    # Table styling (grid + padding)
    # -------------------------
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#d1d5db')),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor('#d1d5db')),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),

        # ✅ Correct padding for dense grid
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),

        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [colors.white, colors.HexColor("#e3fceb")]),
    ]))

    elements.append(table)

    # -------------------------
    # Build PDF (with border if needed)
    # -------------------------
    doc.build(
        elements,
        onFirstPage=draw_page_border,
        onLaterPages=draw_page_border
    )

    buffer.seek(0)
    return buffer


def export_monthly_detailed_pdf(
    db,
    month,
    year,
    department=None,
    employee_id=None,
    status=None,
    current_user=None,
):
    """
    Export Monthly Detailed Attendance Grid to PDF.
    Shows check-in/out times (multiple) and marks paid leaves (casual/sick) as Present + leave type.
    """
    # build days
    _, total_days = monthrange(year, month)
    days = [{"day": d, "weekday": _date(year, month, d).strftime("%a")[:2]} for d in range(1, total_days + 1)]

    # fetch users (respect role-based visibility and multi-department filtering)
    user_query = db.query(User).filter(User.is_active.is_(True))

    if current_user is not None:
        from app.enums import RoleEnum
        from app.utils.department_utils import department_tokens_lower

        user_role = current_user.role
        if user_role == RoleEnum.ADMIN:
            # Admin: exclude self and other admins
            user_query = user_query.filter(
                User.user_id != current_user.user_id,
                User.role != RoleEnum.ADMIN,
            )
        elif user_role == RoleEnum.HR:
            # HR: exclude self, admins, and other HRs
            user_query = user_query.filter(
                User.user_id != current_user.user_id,
                User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
            )

        users = user_query.all()

        # Apply comma-separated multi-department filter, if provided
        if department:
            dept_filter_tokens = set(department_tokens_lower(department))
            if dept_filter_tokens:
                users = [
                    u
                    for u in users
                    if dept_filter_tokens.intersection(
                        set(department_tokens_lower(getattr(u, "department", None)))
                    )
                ]
    else:
        # Fallback: no role scoping, legacy behaviour
        if department:
            user_query = user_query.filter(User.department == department)
        users = user_query.all()

    # small paragraph style for detailed cells (WO and times)
    d_style = ParagraphStyle('d', fontSize=9)
    rows = []
    for user in users:
        if employee_id and user.employee_id != employee_id:
            continue
        attendance_map = {}
        for d in range(1, total_days + 1):
            day_start = datetime(year, month, d, 0, 0, 0)
            day_end = day_start + timedelta(days=1)

            # leaves
            leave = (
                db.query(Leave)
                .filter(
                    Leave.user_id == user.user_id,
                    Leave.status == "Approved",
                    Leave.start_date <= day_end,
                    Leave.end_date >= day_start
                )
                .first()
            )
            if leave and leave.leave_type in ("casual", "sick"):
                lt = "CL" if leave.leave_type == "casual" else "SL"
                attendance_map[str(d)] = Paragraph(f"P<br/><b>{lt}</b>", d_style)
                continue

            # attendance records
            records = (
                db.query(Attendance)
                .filter(
                    Attendance.user_id == user.user_id,
                    Attendance.check_in >= day_start,
                    Attendance.check_in < day_end
                )
                .order_by(Attendance.check_in.asc())
                .all()
            )
            if not records:
                day_date = _date(year, month, d)
                if day_date.weekday() == 6:
                    attendance_map[str(d)] = "WO"
                else:
                    attendance_map[str(d)] = ""
                continue

            parts = []
            for r in records:
                in_t = r.check_in.strftime("%H:%M")
                out_t = r.check_out.strftime("%H:%M") if r.check_out else ""
                parts.append(f"{in_t}-{out_t}" if out_t else f"{in_t}")
            attendance_map[str(d)] = Paragraph("<br/>".join(parts), d_style)

        rows.append({"employee_id": user.employee_id, "name": user.name, "attendance": attendance_map})

    # build pdf (reuse layout from export_monthly_grid_pdf)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("<b>Monthly Detailed Attendance Report</b>", styles["Title"]))
    period_text = f"01/{month:02d}/{year} - {total_days}/{month:02d}/{year}"
    printed_on = _date.today().strftime("%d/%m/%Y")
    center_meta = ParagraphStyle('CenterMeta', parent=styles['Normal'], alignment=TA_CENTER)
    # Match the standard report: fixed two-column table for Duration and Printed
    info_table = Table(
        [[
            f"Duration: {period_text}",
            f"Printed: {printed_on}"
        ]],
        colWidths=[150, 150]   # same as standard report
    )
    info_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(info_table)

    header_days = ["No.", "Employee ID", "Name"]
    header_weekdays = ["", "", ""]
    for day in days:
        header_days.append(str(day["day"]))
        header_weekdays.append(day["weekday"])

    table_data = [header_days, header_weekdays]
    for index, row in enumerate(rows, start=1):
        record = [str(index), row["employee_id"], row["name"]]
        for day in days:
            record.append(row["attendance"].get(str(day["day"]), ""))
        table_data.append(record)

    total_columns = len(header_days)
    page_width = A4[1]
    fixed_cols = [20, 50, 70]
    fixed_total = sum(fixed_cols)
    remaining_columns = max(total_columns - len(fixed_cols), 1)
    remaining_width = (page_width - doc.leftMargin - doc.rightMargin) - fixed_total
    # Evenly distribute the remaining width across the per-day columns so the table
    # fills the available page width (keeps left/right margins equal)
    per_day = float(remaining_width) / remaining_columns
    col_widths = fixed_cols + [per_day] * remaining_columns

    table = Table(table_data, colWidths=col_widths, repeatRows=2, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#d1d5db')),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor('#d1d5db')),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [colors.white, colors.HexColor("#e3fceb")]),
    ]))
    elements.append(table)
    doc.build(elements, onFirstPage=draw_page_border, onLaterPages=draw_page_border)
    buffer.seek(0)
    return buffer
