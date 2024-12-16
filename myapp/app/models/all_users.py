from ldap3 import Connection


def get_all_users(conn: Connection, search_base: str):
    """
    Retrieves a list of all users from Active Directory using an existing connection.

    Args:
        conn (Connection): An active LDAP connection.
        search_base (str): The base from which to perform the search in Active Directory.

    Returns:
        list: A list of users with common names (CN) and distinguished names (DN).
    """
    try:
        # Ensure the connection is active
        if not conn.bound:
            print("The connection to Active Directory is not active.")
            return []

        print("The connection to Active Directory is active.")

        # Define the search filter and attributes
        search_filter = "(objectClass=user)"
        attributes = ['cn', 'distinguishedName']

        # Perform the search
        conn.search(search_base, search_filter, attributes=attributes)

        # Process the results
        users = []

        for entry in conn.entries:
            user_info = {
                "cn": entry.cn.value,
                "dn": entry.distinguishedName.value
            }
            users.append(user_info)

        return users

    except Exception as e:
        print(f"An error occurred: {e}")
        return []