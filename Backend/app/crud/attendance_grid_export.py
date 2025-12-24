import io
import csv
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from .attendance_crud import build_monthly_attendance_grid

def export_monthly_grid_csv(db, month, year, department=None):
    """
    Export Monthly Attendance Grid to CSV (Excel-style layout exactly like image)
    """
    data = build_monthly_attendance_grid(db, month, year, department)
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

def export_monthly_grid_pdf(db, month, year, department=None):
    """
    Export Monthly Attendance Grid to PDF (Excel-like layout, landscape)
    """
    data = build_monthly_attendance_grid(db, month, year, department)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    styles = getSampleStyleSheet()
    elements = []
    elements.append(
        Paragraph(f"<b>{data['title']}</b>", styles["Title"])
    )
    elements.append(
        Paragraph(
            f"Duration: {data['duration']}    Printed: {data['printed_on']}",
            styles["Normal"]
        )
    )
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
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

