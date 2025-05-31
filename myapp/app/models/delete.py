import connection_utlis as cu


def delete_user_from_active_directory(conn, username: str, domain: str, organizational_unit: str = "CN=Users") -> bool:
    """
    Deletes a user from Active Directory (AD) using an existing connection.
    Args:
        conn (Connection): An established LDAP connection object.
        username (str): The username of the AD user to be deleted.
        domain (str): The domain of the AD user.
        organizational_unit (str, optional): The organizational unit (OU) where the user resides. Defaults to "Users".
    Returns:
        bool: Returns True if the user was successfully deleted, False otherwise.
    """
    # Generate the distinguished name (DN) for the user
    user_dn = cu.create_distinguished_name(username=username, domain=domain, organizational_unit=organizational_unit)

    try:
        # Attempt to delete the user from Active Directory
        conn.delete(user_dn)
        return conn.result['result'] == 0  # Returns True if successful, False otherwise
    except Exception as e:
        print(f"An error occurred while deleting user: {e}")
        return False