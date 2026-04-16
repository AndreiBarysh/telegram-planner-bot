"""Export tasks to CSV and PDF."""

import csv
import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from database.models import Priority, Task, TaskStatus

logger = logging.getLogger(__name__)

PRIORITY_LABELS = {
    Priority.HIGH: "HIGH",
    Priority.MEDIUM: "MEDIUM",
    Priority.LOW: "LOW",
}

STATUS_LABELS = {
    TaskStatus.ACTIVE: "Активная",
    TaskStatus.COMPLETED: "Выполнена",
    TaskStatus.CANCELLED: "Отменена",
}


def export_tasks_csv(tasks: list[Task]) -> io.BytesIO:
    """Export tasks to CSV file. Returns BytesIO buffer."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Название", "Описание", "Приоритет", "Статус",
        "Проект", "Дедлайн", "Создано", "Завершено", "Теги",
    ])

    for task in tasks:
        writer.writerow([
            task.task_id,
            task.title,
            task.description or "",
            PRIORITY_LABELS.get(task.priority, ""),
            STATUS_LABELS.get(task.status, ""),
            task.project.name if task.project else "",
            task.due_date.strftime("%d.%m.%Y %H:%M") if task.due_date else "",
            task.created_at.strftime("%d.%m.%Y %H:%M") if task.created_at else "",
            task.completed_at.strftime("%d.%m.%Y %H:%M") if task.completed_at else "",
            ", ".join(t.tag_name for t in task.tags) if task.tags else "",
        ])

    # Convert to bytes
    buf = io.BytesIO()
    buf.write(output.getvalue().encode("utf-8-sig"))  # BOM for Excel compatibility
    buf.seek(0)
    return buf


def export_tasks_pdf(tasks: list[Task], title: str = "Список задач") -> io.BytesIO:
    """Export tasks to PDF file. Returns BytesIO buffer."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)

    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=12,
    )
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(
        f"Exported: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 10 * mm))

    # Table data
    header = ["#", "Task", "Priority", "Status", "Deadline", "Project"]
    data = [header]

    for task in tasks:
        data.append([
            str(task.task_id),
            task.title[:50],
            PRIORITY_LABELS.get(task.priority, ""),
            STATUS_LABELS.get(task.status, ""),
            task.due_date.strftime("%d.%m.%Y") if task.due_date else "-",
            (task.project.name if task.project else "-")[:20],
        ])

    if len(data) == 1:
        elements.append(Paragraph("No tasks found.", styles["Normal"]))
    else:
        col_widths = [30, 180, 60, 70, 70, 80]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A90D9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

    # Summary
    elements.append(Spacer(1, 10 * mm))
    total = len(tasks)
    active = sum(1 for t in tasks if t.status == TaskStatus.ACTIVE)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    summary = f"Total: {total} | Active: {active} | Completed: {completed}"
    elements.append(Paragraph(summary, styles["Normal"]))

    doc.build(elements)
    buf.seek(0)
    return buf
