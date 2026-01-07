import io
import csv
from datetime import date
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from .attendance_crud import build_monthly_attendance_grid
from reportlab.platypus import Table


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


def export_monthly_grid_csv(db, month, year, department=None, employee_id=None, date_from=None, date_to=None, status=None):
    """
    Export Monthly Attendance Grid to CSV (Excel-style layout exactly like image)
    Applies filters to the data after generation, not during.
    """
    from datetime import datetime as dt
    
    data = build_monthly_attendance_grid(db, month, year, department)
    
    # Apply additional filters to rows
    filtered_rows = []
    filter_start = None
    filter_end = None
    
    if date_from:
        try:
            filter_start = dt.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            pass
    if date_to:
        try:
            filter_end = dt.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    for row in data["rows"]:
        # Filter by employee_id
        if employee_id and row["employee_id"] != employee_id:
            continue
        
        # Filter attendance by date range and status
        filtered_attendance = {}
        for day_str, attendance_value in row["attendance"].items():
            day_num = int(day_str)
            day_date = date(year, month, day_num)
            
            # Check date range
            if filter_start and day_date < filter_start:
                continue
            if filter_end and day_date > filter_end:
                continue
            
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

def export_monthly_grid_pdf(db, month, year, department=None, employee_id=None, date_from=None, date_to=None, status=None):
    """
    Export Monthly Attendance Grid to PDF (Excel-like layout, landscape)
    Applies filters to the data after generation, not during.
    """
    from datetime import datetime as dt
    
    # Get base data without extra filters
    data = build_monthly_attendance_grid(db, month, year, department)
    
    # Apply additional filters to rows
    filtered_rows = []
    filter_start = None
    filter_end = None
    
    if date_from:
        try:
            filter_start = dt.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            pass
    if date_to:
        try:
            filter_end = dt.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    for row in data["rows"]:
        # Filter by employee_id
        if employee_id and row["employee_id"] != employee_id:
            continue
        
        # Filter attendance by date range and status
        filtered_attendance = {}
        for day_str, attendance_value in row["attendance"].items():
            day_num = int(day_str)
            day_date = date(year, month, day_num)
            
            # Check date range
            if filter_start and day_date < filter_start:
                continue
            if filter_end and day_date > filter_end:
                continue
            
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

    col_widths = (
        [35, 70, 120] +
        [(page_width - 225) / (total_columns - 3)] * (total_columns - 3)
    )

    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=2
    )

    # -------------------------
    # Table styling (grid + padding)
    # -------------------------
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
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
         [colors.white, colors.HexColor("#f0fdf4")]),
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
