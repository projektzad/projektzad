from connection_utils import create_distinguished_name
from ldap3 import MODIFY_REPLACE
import csv, openpyxl

def change_users_block_status(conn, canonical_name: str, domain: str, organizational_unit: str = "CN=Users") -> bool:
    """
    Toggles a user's block status in Active Directory.
    If currently disabled, it will be enabled. If enabled, it will be disabled.
    """
    user_dn = create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)
    print(f"🔄 Processing user: {user_dn}")

    conn.search(user_dn, '(objectClass=person)', attributes=['userAccountControl', 'pwdLastSet'])
    if conn.entries:
        try:
            user_account_control = int(conn.entries[0].userAccountControl.value)
            pwd_last_set = conn.entries[0].pwdLastSet.value
        except Exception as e:
            print(f" Failed to parse userAccountControl or pwdLastSet: {e}")
            return False


        if user_account_control & 2 == 2:
            # Currently disabled → enable
            new_account_control = user_account_control & ~2
            print("Attempting to enable the account...")

            if pwd_last_set in [None, '0', 0]:
                print(" Cannot enable account: pwdLastSet is 0 (user must change password at next login).")
                return False
        else:
            # Currently enabled → disable
            new_account_control = user_account_control | 2
            print(" Attempting to disable the account...")


        success = conn.modify(user_dn, {'userAccountControl': [(MODIFY_REPLACE, [str(new_account_control)])]})
        if not success:
            print(f"Modify failed: {conn.result}")
        return success

    print(f"User not found: {user_dn}")
    return False


def block_user_account(conn, canonical_name: str, domain: str, organizational_unit: str = "CN=Users") -> bool:
    """
    Forcefully disables a user account in Active Directory by setting ACCOUNTDISABLE flag.
    """
    user_dn = create_distinguished_name(username=canonical_name, domain=domain, organizational_unit=organizational_unit)

    conn.search(user_dn, '(objectClass=person)', attributes=['userAccountControl'])
    if conn.entries:
        try:
            user_account_control = int(conn.entries[0].userAccountControl.value)
        except Exception as e:
            print(f"Failed to parse userAccountControl: {e}")
            return False


        if user_account_control & 2 != 2:
            new_account_control = user_account_control | 2
            print(f"Setting userAccountControl to {new_account_control} ({bin(new_account_control)})")

            success = conn.modify(user_dn, {'userAccountControl': [(MODIFY_REPLACE, [str(new_account_control)])]})
            if not success:
                print(f"Failed to disable account '{canonical_name}': {conn.result}")
            return success
        else:
            print(f"ℹAccount '{canonical_name}' is already disabled.")
            return True
    else:
        print(f"User not found: {user_dn}")
    return False


def block_multiple_users(conn, file_path: str) -> int:
    """
    Processes a CSV or XLSX file and blocks listed users by disabling their accounts.
    """
    processed_count = 0
    try:
        file_extension = file_path.split('.')[-1].lower()

        if file_extension == 'csv':
            processed_count = csv_blocking(conn, file_path)
        elif file_extension == 'xlsx':
            processed_count = excel_blocking(conn, file_path)
        else:
            print(f"Unsupported file extension: {file_extension}")
    except Exception as e:
        print(f"Exception while processing file: {e}")

    return processed_count


def csv_blocking(conn, file_path: str) -> int:
    """
    Reads a CSV file and disables each user listed.
    """
    processed_count = 0
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            header = next(reader)
            for row in reader:
                if len(row) < 3:
                    print(f"Skipping incomplete row: {row}")
                    continue

                canonical_name = row[0].strip()
                domain = row[1].strip()
                organizational_unit = row[2].strip()

                print(f"Processing: {canonical_name}, {domain}, {organizational_unit}")

                if block_user_account(conn, canonical_name, domain, organizational_unit):
                    processed_count += 1
                else:
                    print(f"Failed to block user: {canonical_name}")
    except Exception as e:
        print(f"Error reading CSV: {e}")

    return processed_count


def excel_blocking(conn, file_path: str) -> int:
    """
    Reads an Excel file and disables each user listed.
    """
    processed_count = 0
    try:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        for row in sheet.iter_rows(min_row=2):
            canonical_name = row[0].value.strip()
            domain = row[1].value.strip()
            organizational_unit = row[2].value.strip()
            print(f"Processing from Excel: {canonical_name}, {domain}, {organizational_unit}")

            if block_user_account(conn, canonical_name, domain, organizational_unit):
                processed_count += 1
            else:
                print(f"Failed to block user: {canonical_name}")
    except Exception as e:
        print(f"Error reading Excel file: {e}")

    return processed_count


def get_blocked_users_count(conn, search_base: str) -> int:
    """
    Returns the number of currently disabled user accounts in the directory.
    """
    conn.search(search_base, '(&(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=2))')
    return len(conn.entries)
