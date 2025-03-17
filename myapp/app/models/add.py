import re
from ldap3 import MODIFY_REPLACE


def get_next_uid_number(conn, search_base):
    """
    Retrieves the highest uidNumber from the LDAP directory and returns a new unique identifier.

    Args:
        conn (Connection): Active LDAP connection.
        search_base (str): The base DN from which to perform the search.

    Returns:
        int: The next available uidNumber.
    """
    conn.search(search_base, "(uidNumber=*)", attributes=["uidNumber"])
    uid_numbers = [int(entry.uidNumber.value) for entry in conn.entries if entry.uidNumber.value]

    return max(uid_numbers) + 1 if uid_numbers else 1000  # Default starting uidNumber if none exist


def create_user(conn, username, firstname, lastname, password, ou, dc, search_base):
    """
    Creates a new user in Active Directory with a dynamically assigned uidNumber.

    Args:
        conn (Connection): Active LDAP connection.
        username (str): The user's login name.
        firstname (str): The user's first name.
        lastname (str): The user's last name.
        password (str): The user's initial password.
        ou (str): Organizational Unit where the user will be created.
        dc (str): Domain Component (e.g., "DC=example,DC=com").
        search_base (str): The base DN used to search for the highest uidNumber.

    Returns:
        bool: True if the user was created successfully, False otherwise.
    """
    # Validate inputs
    if not all([username, firstname, lastname, password]):
        print("All fields are required.")
        return False

    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        print("Invalid username format.")
        return False

    if len(password) < 8:
        print("Password must be at least 8 characters long.")
        return False

    # Generate a unique uidNumber
    uid_number = get_next_uid_number(conn, search_base)
    # Construct Distinguished Name (DN) dynamically using ou and dc
    user_dn = f'CN={firstname} {lastname},{ou},{dc}'
    print(user_dn)
    # Define user attributes
    attributes = {
        'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
        'cn': f'{firstname} {lastname}',
        'sAMAccountName': username,
        'userPrincipalName': f'{username}@{dc}',  # Adjusted for domain login
        'givenName': firstname,
        'sn': lastname,
        'displayName': f'{firstname} {lastname}',
        'uid': username,
        'uidNumber': str(uid_number),  # Assigning unique uidNumber
        # 'userAccountControl': '512'  # Normal account
        'gidNumber': '100',  # Default UNIX group
        'unixHomeDirectory': f"/home/{username}",  # UNIX home directory
        'loginShell': "/bin/bash",  # Default shell
        'homeDirectory': f"\\\\server\\users$\\{username}",  # Windows home directory
        'homeDrive': "I:",
        'mail': f"{username}@zut.edu.pl"  # Email address
    }

    # Add user to LDAP
    if conn.add(user_dn, attributes=attributes):
        print(f"User {username} created successfully.")

        # Set password
        try:
            conn.extend.microsoft.modify_password(user_dn, password)
            print(f"Password set for {username}.")
        except Exception as e:
            print(f"Error setting password: {str(e)}")
            return False

        # Enable account
        try:
            conn.modify(user_dn, {'userAccountControl': [(MODIFY_REPLACE, ['512'])]})
            print(f"Account for {username} enabled.")
        except Exception as e:
            print(f"Error enabling account: {str(e)}")
            return False

        return True
    else:
        print(f"Error creating user: {conn.result}")
        return False
