from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE
import connection as co

def get_list(base_dn, usernames_input):
    """
    Funkcja generująca listę DN użytkowników na podstawie wejściowych nazw użytkowników.
    
    Args:
    base_dn (str): Podstawowy DN, np. 'ou=users,o=company'.
    usernames_input (str): Ciąg nazw użytkowników oddzielonych przecinkami.
    
    Returns:
    list: Lista DN użytkowników w formacie LDAP, np. ['cn=user1,ou=users,o=company'].
    """
    # Rozdzielamy nazwy użytkowników i usuwamy ewentualne spacje
    usernames = [username.strip() for username in usernames_input.split(",")]
    
    # Tworzymy listę DN dla każdego użytkownika
    dn_list = [f"cn={username},{base_dn}" for username in usernames]
    return dn_list

def modify_members(group_dn, conn, addList=None, deleteList=None) -> bool:
    """
    Modyfikuje członków grupy w Active Directory: dodaje lub usuwa użytkowników.
    
    Args:
    group_dn (str): Distinguished Name grupy w formacie LDAP.
    conn (Connection): Połączenie z Active Directory.
    addList (list, optional): Lista DN użytkowników do dodania do grupy.
    deleteList (list, optional): Lista DN użytkowników do usunięcia z grupy.
    
    Returns:
    bool: True, jeśli operacja zakończyła się sukcesem, False w przeciwnym razie.
    """
    modifications = {}

    # Dodaj członków do grupy
    if addList:
        modifications['member'] = [(MODIFY_ADD, addList)]

    # Usuń członków z grupy
    if deleteList:
        modifications['member'] = modifications.get('member', []) + [(MODIFY_DELETE, deleteList)]

    # Przeprowadź modyfikację tylko jeśli są jakieś zmiany
    if modifications:
        try:
            # Wykonanie modyfikacji
            conn.modify(group_dn, modifications)
            
            # Jeśli wynik to 0, modyfikacja zakończona sukcesem
            if conn.result['result'] == 0:
                return True
            else:
                print(f"Error: {conn.result['description']}")
                return False
        except Exception as e:
            # Obsługuje błędy połączenia i operacji LDAP
            print(f"Error modifying group members: {e}")
            return False
    else:
        # Jeśli nie ma zmian do wprowadzenia, zwróć False
        return False
