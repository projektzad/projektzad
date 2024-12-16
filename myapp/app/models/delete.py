import connection_utlis as cu


def delete_user_from_active_directory(conn, username: str, domain: str) -> bool:
    """
    Deletes a user from Active Directory (AD) using an existing connection.

    args:
        conn (Connection): An established LDAP connection object.
        username (str): The username of the AD user to be deleted.
        domain (str): The domain of the AD user.

    Returns:
        bool: Returns True if the user was successfully deleted, False otherwise.
    """
    user_dn = cu.create_distinguished_name(username, domain)
    print("User DNNN:",user_dn)
    try:
        conn.delete(user_dn)
        return conn.result['result'] == 0  # Returns True if successful, False otherwise
    except Exception as e:
        return False

