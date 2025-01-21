import re
from ldap3 import MODIFY_REPLACE

def create_user(conn, username, firstname, lastname, password, ou, dc):
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

    # Construct Distinguished Name (DN) dynamically using ou and dc
    
    user_dn = f'CN={firstname} {lastname},{ou},{dc}'
    print(user_dn)
    # Define user attributes
    attributes = {
        'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
        'cn': f'{firstname} {lastname}',
        'sAMAccountName': username,
        'userPrincipalName': f'{username}@{dc}',  # Adjusted to use domain component
        'givenName': firstname,
        'sn': lastname,
        'displayName': f'{firstname} {lastname}',
        #'userAccountControl': '512'  # Normal account
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
