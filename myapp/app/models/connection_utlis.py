import re, os
from ldap3.utils.conv import escape_filter_chars

def validate_ldap_server(ldap_server: str) -> bool:
    """
        Checks if ldap server format was provided corrrectly

        Args:
            ldap_server (str): servers IP or name

        Returns:
            bool:
                - if format is correct returns: True
                - otherwise: False

    """

    pattern = r"^ldap://((?:[a-zA-Z0-9.-]+)|(?:\d{1,3}\.){3}\d{1,3})(:[0-9]+)?$"
    
    if re.match(pattern, ldap_server):
        return True
    else:
        return False

def set_users_password_from_env_variable(password: str, env_variable_name: str = "users_password") -> bool:
    """
        Sets the user's password in the specified environment variable.

        Args:
            password (str): The password to be stored in the environment variable.
            env_variable_name (str): The name of the environment variable where the password will be stored. Default is "users_password".

        Returns:    
            bool:
                - True if the environment variable was successfully set.
                - False if there was an error while setting the environment variable.
    """
    
        
    try:
        os.environ[env_variable_name] = password
        return True
    except Exception:
        return False

def get_users_password_from_env_variable(env_variable_name: str) -> (bool, str):
    """
        Retrieves the user's password from the specified environment variable.

        Args:
            env_variable_name (str): The name of the environment variable from which the password will be retrieved.

        Returns:
            tuple:
                - (bool, str):
                    - True and the password if the environment variable exists.
                    - False and an empty string if the environment variable does not exist or an error occurs.
    """


    try:
        return (True, os.environ[env_variable_name])
    except Exception:
        return (False, "")

def create_distinguished_name(username: str, domain: str, organizational_unit: str, is_group: bool = False) -> str:
    """
    Creates a distinguished name (DN) for a user or group.

    Args:
        username: The username or group name.
        domain: The domain (e.g., "sub.domain.local").
        organizational_unit: The organizational unit (OU) or container.
                           If the object is in the Users container, this should be "CN=Users".
        is_group:  True if the DN is for a group, False for a user.

    Returns:
        The distinguished name (DN).

    Raises:
        ValueError: If organizational_unit is empty and is_group is True.
    """
    domain_parts = domain.split(".")
    dn = f"CN={username},"

    if not organizational_unit:
        if is_group:
            raise ValueError("organizational_unit cannot be empty for a group")
        else:
            dn += "CN=Users,"  # Default for users.
    elif "/" in organizational_unit:
        ou_parts = organizational_unit.split("/")
        ou_parts.reverse()
        dn += ",".join([f"OU={ou}" for ou in 
                        ou_parts]) + ","
    else:
        dn += f"{organizational_unit},"

    dn += ",".join([f"DC={part}" for part in domain_parts])
    return dn

def correct_username(username: str, domain: str) -> str:
    """
        Ensures the username is in the correct format for Active Directory authentication.

        Args:
            username (str): - Can be provided as either 'username' or 'DOMAIN\\username'.
            domain (str): - Full domain name in the format 'subdomain.domain.local'.

        Returns:
            str:
                - If the username is already in the format 'DOMAIN\\username', it is returned unchanged.
                - Otherwise, the domain prefix (derived from the domain) is added as 'DOMAIN\\username'.
    """

    if '\\' in username:
        return username
    domain_prefix = domain.split('.')[0].upper()
    return f"{domain_prefix}\\{username}"