import csv
import os
import openpyxl
from app.models.add import create_user
from app.config_utils import get_default_ou

def import_users_from_file(connection, filepath, dc, search_base):
    success = 0
    fail = 0
    errors = []

    ext = os.path.splitext(filepath)[1].lower()
    rows = []

    if ext == ".csv":
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)

    elif ext in [".xlsx", ".xls"]:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active
        headers = [cell.value for cell in sheet[1]]

        for row in sheet.iter_rows(min_row=2, values_only=True):
            row_data = dict(zip(headers, row))
            rows.append(row_data)

    else:
        return {"error": "Unsupported file type. Use CSV or XLSX."}

    default_ou = get_default_ou()

    for row in rows:
        try:
            ok = create_user(
                connection,
                row['username'],
                row['first_name'],
                row['last_name'],
                row['password'],
                default_ou,    # ✅ dodany OU
                dc,
                search_base
            )
            if ok:
                success += 1
            else:
                fail += 1
                errors.append(f"❌ {row['username']}")
        except Exception as e:
            fail += 1
            errors.append(f"❌ {row.get('username', 'unknown')}: {str(e)}")

    return {"added": success, "failed": fail, "errors": errors}
