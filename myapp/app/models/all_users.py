from ldap3 import Connection

# Mapowanie wartości userAccountControl na flagi
userAccountControlFlags = {
    16777216: "TRUSTED_TO_AUTH_FOR_DELEGATION",
    8388608: "PASSWORD_EXPIRED",
    4194304: "DONT_REQ_PREAUTH",
    2097152: "USE_DES_KEY_ONLY",
    1048576: "NOT_DELEGATED",
    524288: "TRUSTED_FOR_DELEGATION",
    262144: "SMARTCARD_REQUIRED",
    131072: "MNS_LOGON_ACCOUNT",
    65536: "DONT_EXPIRE_PASSWORD",
    8192: "SERVER_TRUST_ACCOUNT",
    4096: "WORKSTATION_TRUST_ACCOUNT",
    2048: "INTERDOMAIN_TRUST_ACCOUNT",
    512: "NORMAL_ACCOUNT",
    256: "TEMP_DUPLICATE_ACCOUNT",
    128: "ENCRYPTED_TEXT_PWD_ALLOWED",
    64: "PASSWD_CANT_CHANGE",
    32: "PASSWD_NOTREQD",
    16: "LOCKOUT",
    8: "HOMEDIR_REQUIRED",
    2: "ACCOUNTDISABLE",
    1: "SCRIPT"
}

def get_all_users(conn: Connection, search_base: str, attributes: list = None):
    """
    Retrieves a list of users from Active Directory with dynamically defined attributes.
    Maps userAccountControl values to corresponding flags if present.

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
                # Special handling for userAccountControl
                if attr == "userAccountControl" and value:
                    uac_value = int(value.value)  # Convert the value to an integer
                    flags = [flag for flag_val, flag in userAccountControlFlags.items() if uac_value & flag_val]
                    user_data[attr] = ", ".join(flags) if flags else "UNKNOWN"
                else:
                    user_data[attr] = value.value if value else None

            users.append(user_data)

        return users

    except Exception as e:
        # Return an empty list if any exception occurs
        return []


def get_all_users_count(conn, search_base: str) -> int:
    users = get_all_users(conn, search_base)
    return len(users)



