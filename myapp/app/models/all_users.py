from ldap3 import Connection

def get_all_users(conn: Connection, search_base: str, attributes: list = None):
    """
    Retrieves a list of users from Active Directory with dynamically defined attributes.

    Args:
        conn (Connection): An active LDAP connection.
        search_base (str): The base from which to perform the search in Active Directory.
        attributes (list): A list of attributes to fetch (optional).

    Returns:
        list: A list of dictionaries containing user data.
    """
    if attributes is None or not isinstance(attributes, list):
        # Set default attributes if the list is not provided
        attributes = ['cn', 'distinguishedName', 'mail']

    try:
        search_filter = "(objectClass=user)"

        # Perform the search with dynamically provided attributes
        conn.search(search_base, search_filter, attributes=attributes)

        users = []
        for entry in conn.entries:
            # Dynamically construct the result dictionary based on attributes
            user_data = {}
            for attr in attributes:
                value = getattr(entry, attr, None)  # Retrieve the attribute if it exists
                user_data[attr] = value.value if value else None

            users.append(user_data)

        return users

    except Exception as e:
        # Return an empty list if any exception occurs
        return []



