from ldap3 import Server, Connection, ALL, MODIFY_ADD, MODIFY_REPLACE
import ldap3
import os
import connection_utlis as cu


def add_user_to_active_directory(conn: Connection, username: str, first_name: str, last_name: str, password: str, ou: str) -> bool:
    """
    Dodaje nowego użytkownika do Active Directory.

    Args:
        conn (Connection): Połączenie z Active Directory.
        username (str): Login użytkownika.
        first_name (str): Imię użytkownika.
        last_name (str): Nazwisko użytkownika.
        password (str): Hasło użytkownika.
        ou (str): Ścieżka do jednostki organizacyjnej, np. 'OU=Users,DC=example,DC=com'.
    
    Returns:
        bool: True, jeśli użytkownik został pomyślnie dodany, False w przeciwnym razie.
    """
    # Tworzymy Distinguished Name (DN) użytkownika
    dn = f"CN={username},{ou}"
    
    # Atrybuty użytkownika
    attributes = {
        'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
        'sAMAccountName': username,
        'userPrincipalName': f'{username}@example.com',
        'givenName': first_name,
        'sn': last_name,
        'unicodePwd': password.encode('utf-16-le'),  # Hasło musi być zakodowane w UTF-16 (Active Directory)
        'displayName': f"{first_name} {last_name}",
        'mail': f"{username}@example.com",
        'accountExpires': '0',  # 0 oznacza brak daty wygaśnięcia
        'userAccountControl': 512  # Domyślnie konto aktywne
    }
    
    # Dodawanie użytkownika do Active Directory
    try:
        conn.add(dn, attributes=attributes)
        return conn.result['result'] == 0  # Jeśli wynik to 0, dodanie było udane
    except ldap3.LDAPException as e:
        print(f"Error adding user: {e}")
        return False


def enable_user_account(conn: Connection, username: str) -> bool:
    """
    Aktywuje konto użytkownika w Active Directory (zmiana atrybutu `userAccountControl`).

    Args:
        conn (Connection): Połączenie z Active Directory.
        username (str): Login użytkownika.
    
    Returns:
        bool: True, jeśli konto zostało aktywowane, False w przeciwnym razie.
    """
    search_filter = f"(sAMAccountName={username})"
    conn.search('DC=example,DC=com', search_filter, attributes=['distinguishedName'])
    
    if conn.entries:
        dn = conn.entries[0].distinguishedName.value
        user_account_control = 512  # Wartość 512 oznacza aktywne konto
        conn.modify(dn, {'userAccountControl': [(MODIFY_REPLACE, [user_account_control])]})
        return conn.result['result'] == 0
    return False


def reset_user_password(conn: Connection, username: str, new_password: str) -> bool:
    """
    Resetuje hasło użytkownika w Active Directory.

    Args:
        conn (Connection): Połączenie z Active Directory.
        username (str): Login użytkownika.
        new_password (str): Nowe hasło.
    
    Returns:
        bool: True, jeśli hasło zostało zresetowane, False w przeciwnym razie.
    """
    search_filter = f"(sAMAccountName={username})"
    conn.search('DC=example,DC=com', search_filter, attributes=['distinguishedName'])

    if conn.entries:
        dn = conn.entries[0].distinguishedName.value
        conn.modify(dn, {'unicodePwd': [(MODIFY_REPLACE, [new_password.encode('utf-16-le')])]})
        return conn.result['result'] == 0
    return False
