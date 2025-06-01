import csv
import openpyxl
import connection_utils as cu
from ldap3 import Connection, MODIFY_REPLACE


def delete_user_from_ad(conn: Connection, canonical_name: str, domain: str, organizational_unit: str = "Users") -> bool:
    """
    Delete a user from Active Directory.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        canonical_name (str): The canonical name of the user.
        domain (str): The domain of the Active Directory.
        organizational_unit (str): The organizational unit (OU) where the user resides.

    Returns:
        bool: True if the deletion was successful, False otherwise.
    """
    user_dn = cu.create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)

    # Attempt to delete the user
    conn.delete(user_dn)

    return conn.result['result'] == 0


def delete_multiple_users(conn: Connection, file_path: str) -> int:
    """
    Process a batch file (CSV or XLSX) and delete users listed in the file.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        file_path (str): The path to the CSV or XLSX file containing the user data.

    Returns:
        int: The number of users successfully processed.
    """
    processed_count = 0

    file_extension = file_path.split('.')[-1].lower()

    if file_extension == 'csv':
        processed_count = csv_deletion(file_path, conn)
    elif file_extension == 'xlsx':
        processed_count = excel_deletion(file_path, conn)

    return processed_count


def csv_deletion(file_path: str, conn: Connection) -> int:
    """
    Processes a CSV file to delete users listed in the file.

    Args:
        file_path (str): The path to the CSV file containing the user data.
        conn (Connection): The connection object representing the connection to Active Directory.

    Returns:
        int: The number of users successfully processed.
    """
    processed_count = 0
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row
        for row in reader:
            if row:
                canonical_name = row[0].strip()
                domain = row[1].strip()
                organizational_unit = row[2].strip()
                if delete_user_from_ad(conn, canonical_name, domain, organizational_unit):
                    processed_count += 1

    return processed_count


def excel_deletion(file_path: str, conn: Connection) -> int:
    """
    Processes an Excel (XLSX) file to delete users listed in the file.

    Args:
        file_path (str): The path to the Excel file containing the user data.
        conn (Connection): The connection object representing the connection to Active Directory.

    Returns:
        int: The number of users successfully processed.
    """
    processed_count = 0
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    for row in sheet.iter_rows(min_row=2):
        canonical_name = row[0].value.strip()
        domain = row[1].value.strip()
        organizational_unit = row[2].value.strip()
        if delete_user_from_ad(conn, canonical_name, domain, organizational_unit):
            processed_count += 1

    return processed_count
