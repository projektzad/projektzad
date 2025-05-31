from connection_utlis import create_distinguished_name
from datetime import datetime
from ldap3 import MODIFY_REPLACE
import openpyxl, csv

def set_account_expiration(conn, canonical_name: str, domain: str, expiration_date: str, organizational_unit: str = "CN=Users") -> bool:
    """
    Set the 'accountExpires' attribute for a user account in Active Directory.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        canonical_name (str): The canonical name of the user.
        domain (str): The domain of the Active Directory.
        expiration_date (str): The expiration date in the format 'DD-MM-YYYY'.
        organizational_unit (str): The organizational unit (OU) where the user resides. Default is "Users".

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    user_dn = create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)

    expiration_time = datetime.strptime(expiration_date, '%d-%m-%Y')
    
    expiration_timestamp = int(expiration_time.timestamp() * 10000000 + 116444736000000000)

    conn.modify(user_dn, {'accountExpires': [(MODIFY_REPLACE, [expiration_timestamp])]})
    
    return conn.result['result'] == 0


def expire_multiple_users(conn, file_path: str) -> int:
    """
    Process a batch file (CSV or XLSX) and set the 'accountExpires' attribute for users listed in the file.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        file_path (str): The path to the CSV or XLSX file containing the user data. The file should contain
                         user information including canonical name and the expiration date for each user.
        
    Returns:
        int: The number of users successfully processed (i.e., whose 'accountExpires' attribute was set).
    """
    processed_count = 0

    file_extension = file_path.split('.')[-1].lower()

    if file_extension == 'csv':
        processed_count = csv_expiring(conn,file_path=file_path)

    elif file_extension == 'xlsx':
        processed_count = excel_expiring(conn,file_path=file_path)
        
    return processed_count


def csv_expiring(conn, file_path: str) -> int:
    """
    Processes a CSV file to set the 'accountExpires' attribute for users listed in the file.

    Args:
        file_path (str): The path to the CSV file containing the user data. The file should include the following columns:
                         - Canonical Name
                         - Domain
                         - Organizational Unit
                         - Expiration Date (in format 'DD-MM-YYYY')

    Returns:
        int: The number of users successfully processed (i.e., whose 'accountExpires' attribute was set).
    """
    processed_count = 0
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if row:
                canonical_name = row[0].strip()
                domain = row[1].strip()
                organizational_unit = row[2].strip()
                expiration_date = row[3].strip()
                if set_account_expiration(conn=conn, canonical_name=canonical_name, domain=domain,expiration_date=expiration_date, organizational_unit=organizational_unit):
                    processed_count += 1

    return processed_count

def excel_expiring(conn, file_path: str)-> int:
    """
    Processes an Excel (XLSX) file to change the block status of users listed in the file.

    Args:
        file_path (str): The path to the Excel file containing the user data.

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
        expiration_date=row[3].value.strip()
        if set_account_expiration(conn=conn, canonical_name=canonical_name, domain=domain,expiration_date=expiration_date, organizational_unit=organizational_unit):
            processed_count += 1

    return processed_count

def get_expiring_users_count(conn, search_base: str) -> int:
    conn.search(search_base, '(&(objectClass=user)(accountExpires>=1))')
    return len(conn.entries)

