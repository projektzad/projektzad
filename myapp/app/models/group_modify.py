from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE
from connection_utlis import create_distinguished_name
import openpyxl, csv, json


def domain_to_dn(domain:str) -> str:
    parts = domain.split('.')
    dn = ','.join([f"dc={part}" for part in parts])
    return dn

def create_group_dn(group_name, domain, container="CN=Users"):
    dn = domain_to_dn(domain).replace("dc=", "DC=")
    return f"CN={group_name},{container},{dn}"



def list_all_groups(conn, domain: str) -> tuple:
    group_list = []
    ou_list = []  # List to store corresponding OUs
    
    # Perform the LDAP search to get groups
    conn.search(domain_to_dn(domain=domain), '(objectClass=group)', attributes=['cn', 'distinguishedName'])
    
    for entry in conn.entries:
        # Extract the CN and OU from the distinguishedName (DN)
        cn = str(entry.cn).replace("cn: ", "")
        distinguished_name = str(entry.distinguishedName)  # Get the full DN
        ou = None
        
        # Parse the distinguishedName to find the OU
        if "OU=" in distinguished_name:
            # Extract the OU part from the distinguishedName
            ou = ', '.join([part for part in distinguished_name.split(',') if part.startswith("OU=")])
        if "CN=Users" in distinguished_name:
            ou = "CN=Users"
        # Add the group name and OU to their respective lists
        group_list.append(cn)
        ou_list.append(ou if ou else "")  # If no OU found, append an empty string
    
    return group_list, ou_list


def add_user_to_group(conn, username: str, users_domain :str, users_ou:str, group: str, group_domain:str, group_ou :str) -> bool:
    user = create_distinguished_name(username, users_domain, users_ou)
    
    group = create_distinguished_name(group, group_domain, group_ou, is_group=True)
    
    return conn.extend.microsoft.add_members_to_groups(user, group)

def remove_user_from_group(conn, username: str, users_domain :str, users_ou:str, group: str, group_domain:str, group_ou :str) -> bool:
    user = create_distinguished_name(username, users_domain, users_ou)
    
    group = create_distinguished_name(group, group_domain, group_ou, is_group=True)
    
    return conn.extend.microsoft.remove_members_from_groups(user, group)

def csv_adding_to_groups(conn, file_path: str) -> int:
    processed_count = 0
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if row:
                users_canonical_name = row[0].strip()
                users_domain = row[1].strip()
                users_ou = row[2].strip()
                group_canonical_name = row[3].strip()
                group_domain = row[4].strip()
                group_ou = row[5].strip()
                if add_user_to_group(conn,username=users_canonical_name,users_domain=users_domain,users_ou=users_ou,group=group_canonical_name,group_domain=group_domain, group_ou=group_ou):
                    processed_count += 1

    return processed_count

def csv_removing_from_groups(conn, file_path: str) -> int:
    processed_count = 0
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if row:
                users_canonical_name = row[0].strip()
                users_domain = row[1].strip()
                users_ou = row[2].strip()
                group_canonical_name = row[3].strip()
                group_domain = row[4].strip()
                group_ou = row[5].strip()
                if remove_user_from_group(conn,username=users_canonical_name,users_domain=users_domain,users_ou=users_ou,group=group_canonical_name,group_domain=group_domain, group_ou=group_ou):
                    processed_count += 1

    return processed_count

def excel_adding_to_groups(conn, file_path: str) -> int:
    processed_count = 0
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    for row in sheet.iter_rows(min_row=2):
        users_canonical_name = row[0].value.strip()
        users_domain = row[1].value.strip()
        users_ou = row[2].value.strip()
        group_canonical_name = row[3].value.strip()
        group_domain = row[4].value.strip()
        group_ou = row[5].value.strip()
        if add_user_to_group(conn,username=users_canonical_name,users_domain=users_domain,users_ou=users_ou,group=group_canonical_name,group_domain=group_domain, group_ou=group_ou):
            processed_count += 1

    return processed_count

def excel_removing_from_groups(conn, file_path: str) -> int:
    processed_count = 0
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    for row in sheet.iter_rows(min_row=2):
        users_canonical_name = row[0].value.strip()
        users_domain = row[1].value.strip()
        users_ou = row[2].value.strip()
        group_canonical_name = row[3].value.strip()
        group_domain = row[4].value.strip()
        group_ou = row[5].value.strip()
        if remove_user_from_group(conn,username=users_canonical_name,users_domain=users_domain,users_ou=users_ou,group=group_canonical_name,group_domain=group_domain, group_ou=group_ou):
            processed_count += 1

    return processed_count

def batch_group_adding(conn,file_path: str) -> int:
    processed_count = 0

    file_extension = file_path.split('.')[-1].lower()

    if file_extension == 'csv':
        processed_count = csv_adding_to_groups(conn, file_path=file_path)
    elif file_extension == 'xlsx':
        processed_count = excel_adding_to_groups(conn, file_path=file_path)
        
    return processed_count

def batch_group_removing(conn,file_path: str) -> int:
    processed_count = 0

    file_extension = file_path.split('.')[-1].lower()

    if file_extension == 'csv':
        processed_count = csv_removing_from_groups(conn, file_path=file_path)
    elif file_extension == 'xlsx':
        processed_count = excel_removing_from_groups(conn, file_path=file_path)


    return processed_count

def load_json_config(file_path: str) -> dict:
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def remove_group(conn,group, group_domain, group_ou) -> bool:
    group_DN = create_distinguished_name(group, group_domain, "CN=Users", is_group=True)
    print(group_DN)
    return conn.delete(group_DN)

def add_new_group(conn, config) -> bool:
    try:
        group_name = config['General']['Group name (pre-Windows 2000)']
        domain_dn = conn.server.info.other['defaultNamingContext'][0]
        group_dn = f"CN={group_name},CN=Users,{domain_dn}"

        attributes = {
            'objectClass': ['top', 'group'],
            'cn': group_name,
            'description': config['General'].get('Notes', ''),
            'mail': config['General'].get('E-mail', ''),
            'sAMAccountName': group_name,
            'groupType': 0x80000002
        }

        success = conn.add(group_dn, attributes=attributes)
        if not success:
            print("❌ LDAP error:", conn.result)  # <-- to tylko do debugowania
            return False

        return True

    except Exception:
        return False


def process_config_file(conn, file_path: str) -> bool:
    
    config = load_json_config(file_path=file_path)

    action = config.get('action')

    if action == "remove":
        return remove_group(conn, config.get('group_DN'))
    elif action == "modify":
        pass
    elif action == "add":
        pass
    else:
        return -1

def list_group_members(conn, domain: str, group_name: str) -> list:

    """

    Retrieves the members of a specific group in a given LDAP domain.
 
    Args:

        conn: LDAP connection object.

        domain (str): The LDAP domain to search in.

        group_name (str): The name of the group whose members should be retrieved.
 
    Returns:

        list: A list of members (as DN strings) in the specified group, or an empty list if no members are found.

    """

    try:

        # Convert domain to a Distinguished Name (DN)

        search_base = domain_to_dn(domain=domain)

        # Perform LDAP search for the specific group

        search_filter = f'(&(objectClass=group)(cn={group_name}))'

        conn.search(search_base, search_filter, attributes=['member'])

        # Check if the group is found

        if conn.entries:

            entry = conn.entries[0]

            # Extract members (if any)

            if 'member' in entry:

                return [str(member) for member in entry.member]

        # If group is not found or has no members

        print(f"No members found in group: {group_name}")

        return []

    except Exception as e:

        # Handle potential errors

        print(f"An error occurred while listing members of the group {group_name}: {e}")

        return []

def add_user_to_group_by_dn(conn, user_dn, group_dn):
    return conn.extend.microsoft.add_members_to_groups(user_dn, group_dn)

def remove_user_from_group_by_dn(conn, user_dn, group_dn):
    return conn.extend.microsoft.remove_members_from_groups(user_dn, group_dn)



 


 