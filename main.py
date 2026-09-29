import os
import re
import sys
import pandas as pd

from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Date,
    Numeric,
    UniqueConstraint,
    select
)
from sqlalchemy.dialects.postgresql import insert




# -----------------------------
# Configuration
# -
# ----------------------------
# checking if the file url is provided in command
if len(sys.argv)<2:
    print("Usage: python main.py <excel_file>")
    sys.exit(1)
EXCEL_FILE = sys.argv[1]

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")


# -----------------------------
# Read Excel
# -----------------------------





# -----------------------------
# Find attendance columns
# -----------------------------



course_df = pd.read_excel(
    EXCEL_FILE,
    sheet_name="Course wise",
    header=None
)

from_text = str(course_df.iloc[4, 0])
till_text = str(course_df.iloc[4, 18])

from_match = re.search(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    from_text
)

till_match = re.search(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    till_text
)

if not from_match or not till_match:
    raise ValueError("Could not find attendance period dates.")

print("Excel loaded successfully.")
print(f"Sheet size: {course_df.shape}")

from_date = datetime.strptime(
    " ".join(from_match.groups()),
    "%d %b %Y"
).date()

till_date = datetime.strptime(
    " ".join(till_match.groups()),
    "%d %b %Y"
).date()

print(f"Attendance period: {from_date} → {till_date}")



subject_row = 5
total_classes_row = 8
student_start_row = 9

subjects = []

for column in range(3, 18):
    subject = course_df.iloc[subject_row, column]

    if pd.isna(subject):
        continue

    total_classes = course_df.iloc[total_classes_row, column]

    if pd.isna(total_classes):
        continue

    subjects.append({
        "column": column,
        "subject": str(subject).strip(),
        "total_classes": total_classes
    })
    
    
    
    
records = []

for row in range(student_start_row, len(course_df)):

    gr_no = course_df.iloc[row, 1]
    student_name = course_df.iloc[row, 2]

    if pd.isna(gr_no) or pd.isna(student_name):
        continue

    for subject_info in subjects:

        attended = course_df.iloc[
            row,
            subject_info["column"]
        ]

        if pd.isna(attended):
            continue

        records.append({
            "gr_no": str(gr_no).strip(),
            "student_name": str(student_name).strip(),
            "subject": subject_info["subject"],

            "from_date": from_date,
            "till_date": till_date,

            "attended_classes": attended,
            "total_classes": subject_info["total_classes"]
        })


# -----------------------------
# Create DataFrame
# -----------------------------

attendance_df = pd.DataFrame(records)

print(f"Attendance records found: {len(attendance_df)}")

print("\nFirst 10 records:")
print(attendance_df.head(10))


# -----------------------------
# Validate statuses
# -----------------------------


# -----------------------------
# Connect to PostgreSQL
# -----------------------------

engine = create_engine(DATABASE_URL)

print("\nConnected to PostgreSQL.")


# -----------------------------
# Create table
# -----------------------------
metadata = MetaData()

attendance_table = Table(
    "student_attendance",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("gr_no", String(20), nullable=False),
    Column("student_name", String(100), nullable=False),
    Column("subject", String(100), nullable=False),

    Column("from_date", Date, nullable=False),
    Column("till_date", Date, nullable=False),

    Column("attended_classes", Numeric, nullable=False),
    Column("total_classes", Numeric, nullable=False),

    UniqueConstraint(
        "gr_no",
        "subject",
        "from_date",
        "till_date",
        name="unique_student_subject_period"
    )
)
metadata.create_all(engine)

print("Attendance table ready.")


# -----------------------------
# Insert data
# -----------------------------

# -----------------------------
# Insert data
# -----------------------------

records = attendance_df.to_dict(orient="records")

with engine.begin() as connection:

    # Get existing attendance keys
    existing_records = connection.execute(
        select(
            attendance_table.c.gr_no,
            attendance_table.c.subject,
            attendance_table.c.from_date,
            attendance_table.c.till_date
        )
    ).fetchall()

    existing_keys = {
        (
            row.gr_no,
            row.subject,
            row.from_date,
            row.till_date
        )
        for row in existing_records
    }

    # Find records that are not already in the database
    new_records = [
        record
        for record in records
        if (
            record["gr_no"],
            record["subject"],
            record["from_date"],
            record["till_date"]
        ) not in existing_keys
    ]

    skipped_records = len(records) - len(new_records)

    # Insert new records
    if new_records:

        stmt = insert(attendance_table).values(new_records)

        stmt = stmt.on_conflict_do_nothing(
            constraint="unique_student_subject_period"
        )

        connection.execute(stmt)


print("\nImport Summary")
print("------------------------")
print(f"Records found: {len(records)}")
print(f"New records:   {len(new_records)}")
print(f"Skipped:       {skipped_records}")
print("------------------------")
print("Import completed successfully!")