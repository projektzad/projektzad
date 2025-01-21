from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE
from connection_utlis import create_distinguished_name
import openpyxl, csv, json
# to do: testowanie tego + wgrywanie configu (dodawnie lub modyfikowanie grupy, moze usuwanie grupy)


def domain_to_dn(domain:str) -> str:
    parts = domain.split('.')
    dn = ','.join([f"dc={part}" for part in parts])
    return dn

def list_all_groups(conn, domain:str) -> list:
    group_list = []
    conn.search(domain_to_dn(domain=domain), '(objectClass=group)', attributes=['cn'])
    for entry in conn.entries:
        group_list.append(str(entry.cn).replace("cn: ", ""))

    return group_list

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

def remove_group(conn, group_DN) -> bool:
    return conn.delete(group_DN)

def add_new_group(conn, config) -> bool:

    objectClass = ['top', 'group']
    if "OU=" in config.get(group_DN):
        objectClass = ['top', 'group', 'organizationalUnit']
    """
    try:
        attributes = {
            'objectClass': objectClass,  
            'cn': config['General']['Group name (pre-Windows 2000)'],
            'description': config['General']['Notes'],
            'E-mail': config['General']['E-mail'],
            'sAMAccountName': group_samaccountname,
            'groupType': 0x80000002,
        }
        conn.add(group_dn, attributes=attributes)
    except Exception:
        return -1
    """


    for member in config['Members']:
        user = member['User, Service Account, Group, or Other Object DN']
        group = config['group_DN']
        if member['action'] == 'remove':
            conn.extend.microsoft.remove_members_from_groups(user,group)
        elif member['action'] == 'add':
            conn.extend.microsoft.add_members_to_groups(user, group)
        else: 
            return -1
            


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

def list_group_members(conn, group_dn: str) -> list:
    """
    Funkcja zwraca listę członków grupy na podstawie jej DN.
    :param conn: Połączenie LDAP
    :param group_dn: Distinguished Name grupy
    :return: Lista członków grupy (DN użytkowników)
    """
    try:
        # Szukanie grupy na podstawie jej DN
        conn.search(search_base=group_dn,
                    search_filter='(objectClass=group)',
                    attributes=['member'])
        if not conn.entries:
            print(f"Grupa {group_dn} nie została znaleziona.")
            return []
        # Pobranie atrybutu 'member'
        group = conn.entries[0]
        members = group.member.values if 'member' in group else []
        return members
    except Exception as e:
        print(f"Błąd podczas pobierania członków grupy: {e}")
        return []