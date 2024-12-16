from connection_utlis import create_distinguished_name
from ldap3 import MODIFY_REPLACE
import csv, openpyxl


def change_users_block_status(conn, canonical_name: str, domain: str, organizational_unit: str = "Users") -> bool:
    """
    Toggles the block status of a user in Active Directory. If the user is currently blocked,
    it will be unblocked. If the user is not blocked, it will be blocked.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        canonical_name (str): The name of the user whose block status is to be changed. For example: "Czeslaw Bialas"
        domain (str): The domain name of the Active Directory.
        organizational_unit (str, optional): The organizational unit (OU) where the user resides.
                                             Defaults to "Users".

    Returns:
        bool:
            - True if the block status change was successful.
            - False if the user was not found or an error occurred during the modification.
    """
    user_dn=create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)
    conn.search(user_dn, '(objectClass=person)', attributes=['userAccountControl'])
    if conn.entries:
        user_account_control = conn.entries[0].userAccountControl.value
        if user_account_control & 2 == 2:
            new_account_control = user_account_control & ~2
        else:
            new_account_control = user_account_control | 2

        conn.modify(user_dn, {'userAccountControl': [(MODIFY_REPLACE, [new_account_control])]})
    
        return conn.result['result'] == 0
    
    return False

def block_user_account(conn, canonical_name: str, domain: str, organizational_unit: str = "Users") -> bool:
    """
    Block the user account by setting the 'userAccountControl' attribute to disable the account.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        canonical_name (str): The canonical name of the user.
        domain (str): The domain of the Active Directory.
        organizational_unit (str): The organizational unit (OU) where the user resides.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """

    user_dn=create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)
    
    conn.search(user_dn, '(objectClass=person)', attributes=['userAccountControl'])
    
    if conn.entries:
        user_account_control = conn.entries[0].userAccountControl.value
        
        if user_account_control & 2 != 2:
            new_account_control = user_account_control | 2
            
            conn.modify(user_dn, {'userAccountControl': [(MODIFY_REPLACE, [new_account_control])]})
            
            return conn.result['result'] == 0
    
    return False

def block_multiple_users(conn, file_path: str) -> int:
    """
    Process a batch file (CSV or XLSX) and change the block status of users listed in the file.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        file_path (str): The path to the CSV or XLSX file containing the user data.
        domain (str): The domain name of the Active Directory.
        organizational_unit (str, optional): The organizational unit (OU) where the user resides. Defaults to "Users".

    Returns:
        int: The number of users successfully processed.
    """
    processed_count = 0

    file_extension = file_path.split('.')[-1].lower()

    if file_extension == 'csv':
        processed_count = csv_blocking(file_path=file_path)

    elif file_extension == 'xlsx':
        processed_count = excel_blocking(file_path=file_path)
        
    return processed_count


def csv_blocking(file_path: str) -> int:
    """
    Processes a CSV file to change the block status of users listed in the file.

    Args:
        file_path (str): The path to the CSV file containing the user data.

    Returns:
        int: The number of users successfully processed.
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
                if block_user_account(conn, canonical_name, domain, organizational_unit):
                    processed_count += 1

    return processed_count

def excel_blocking(file_path: str)-> int:
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
        if block_user_account(conn, canonical_name, domain, organizational_unit):
            processed_count += 1

    return processed_count
