from connection_utlis import create_distinguished_name
from ldap3 import MODIFY_REPLACE



def change_users_block_status(conn, name: str, domain: str, organizational_unit: str = "Users") -> bool:
    """
    Toggles the block status of a user in Active Directory. If the user is currently blocked,
    it will be unblocked. If the user is not blocked, it will be blocked.

    Args:
        conn (Connection): The connection object representing the connection to Active Directory.
        name (str): The name of the user whose block status is to be changed. For example: "Czeslaw Bialas"
        domain (str): The domain name of the Active Directory.
        organizational_unit (str, optional): The organizational unit (OU) where the user resides.
                                             Defaults to "Users".

    Returns:
        bool:
            - True if the block status change was successful.
            - False if the user was not found or an error occurred during the modification.
    """
    user_dn=create_distinguished_name(username=name, domain=domain, organizational_unit=organizational_unit)
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