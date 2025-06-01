import re
from ldap3 import MODIFY_REPLACE
from app.config_utils import get_default_attributes, get_default_ou

def get_next_uid_number(conn, search_base):
    conn.search(search_base, "(uidNumber=*)", attributes=["uidNumber"])
    uid_numbers = [int(entry.uidNumber.value) for entry in conn.entries if entry.uidNumber.value]
    return max(uid_numbers) + 1 if uid_numbers else 1000


def create_user(conn, username, firstname, lastname, password, ou, dc, search_base):
    if not all([username, firstname, lastname, password]):
        print("All fields are required.")
        return False

    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        print("Invalid username format.")
        return False

    if len(password) < 8:
        print("Password must be at least 8 characters long.")
        return False

    default_ou = get_default_ou()
    default_attrs = get_default_attributes()
    uid_number = get_next_uid_number(conn, search_base)
    user_dn = f'CN={firstname} {lastname},{default_ou},{dc}'

    try:
        default_uac = int(default_attrs.get("userAccountControl", 544))
    except Exception:
        default_uac = 544
    if default_uac == 0 or default_uac == 512 :
        default_uac = 544

    attributes = {
        'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
        'cn': f'{firstname} {lastname}',
        'sAMAccountName': username,
        'userPrincipalName': f'{username}@{dc.replace("DC=", "").replace(",", ".")}',
        'givenName': firstname,
        'sn': lastname,
        'displayName': f'{firstname} {lastname}',
        'uid': username,
        'uidNumber': str(uid_number),
        'userAccountControl': str(default_uac)
    }

    for key, value in default_attrs.items():
        if key in ["default_ou", "userAccountControl"]:
            continue
        attributes[key] = value.replace("{username}", username) if isinstance(value, str) else value

    if conn.add(user_dn, attributes=attributes):
        print(f"User {username} created successfully.")

        try:
            conn.extend.microsoft.modify_password(user_dn, password)
            print(f"Password set for {username}.")
        except Exception as e:
            print(f"Error setting password: {str(e)}")
            return False

        try:
            success = conn.modify(user_dn, {'pwdLastSet': [(MODIFY_REPLACE, ['-1'])]})
            if success:
                print("pwdLastSet set to -1 successfully.")
            else:
                print(f"pwdLastSet modification failed: {conn.result}")
                return False
        except Exception as e:
            print(f"Error setting pwdLastSet: {e}")
            return False

        return True
    else:
        print(f"Error creating user: {conn.result}")
        return False
