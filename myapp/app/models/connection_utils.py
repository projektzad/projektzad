# myapp/app/models/connection_utils.py
import re
import os


# from ldap3.utils.conv import escape_filter_chars # Uncomment if needed elsewhere

def validate_ldap_server(ldap_server: str) -> bool:
    """
    Checks if ldap server format was provided correctly.
    Args:
        ldap_server (str): server's IP or name
    Returns:
        bool:
            - True if format is correct
            - False otherwise
    """
    pattern = r"^ldap(s)?://((?:[a-zA-Z0-9.-]+)|(?:\d{1,3}\.){3}\d{1,3})(:[0-9]+)?$"
    if re.match(pattern, ldap_server):
        return True
    else:
        return False


def set_users_password_from_env_variable(password: str, env_variable_name: str = "users_password") -> bool:
    """
    Sets the user's password in the specified environment variable.
    (Note: Storing sensitive info in env variables can be risky.)
    Args:
        password (str): The password to be stored.
        env_variable_name (str): The name of the environment variable.
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        os.environ[env_variable_name] = password
        return True
    except Exception:
        return False


def get_users_password_from_env_variable(env_variable_name: str) -> tuple[bool, str]:
    """
    Retrieves the user's password from the specified environment variable.
    Args:
        env_variable_name (str): The name of the environment variable.
    Returns:
        tuple: (bool, str) - True and password if exists, False and empty string otherwise.
    """
    try:
        return (True, os.environ[env_variable_name])
    except Exception:
        return (False, "")


def domain_to_dn(domain_str: str) -> str:
    """
    Converts a domain string (e.g., "testad.local") to an LDAP Distinguished Name base
    (e.g., "DC=testad,DC=local").
    Args:
        domain_str (str): The domain string.
    Returns:
        str: The LDAP DN base string.
    """
    if not domain_str:
        raise ValueError("Domain string cannot be empty for domain_to_dn conversion.")
    parts = domain_str.split('.')
    # LDAP DN components are typically case-insensitive but often written in uppercase for DC.
    dn = ','.join([f"DC={part}" for part in parts])
    return dn


def create_distinguished_name(username: str, domain: str, organizational_unit: str = None,
                              is_group: bool = False) -> str:
    """
    Creates a distinguished name (DN) for a user or group.
    Args:
        username (str): The username or group name (CN).
        domain (str): The domain (e.g., "sub.domain.local").
        organizational_unit (str, optional): The organizational unit (OU) or container string.
                             Can be "OU=Sales/OU=HR", "CN=Users", "Users" (will convert to CN=Users).
                             If None, defaults to "CN=Users".
        is_group (bool): True if the DN is for a group, False for a user.
    Returns:
        str: The distinguished name (DN).
    Raises:
        ValueError: If username or domain is empty.
    """
    if not username or not domain:
        raise ValueError("Username and domain cannot be empty for create_distinguished_name.")

    domain_dn_suffix = domain_to_dn(domain)  # Use the new function here
    dn = f"CN={username},"

    if not organizational_unit:
        dn += "CN=Users,"
    elif "/" in organizational_unit:
        ou_path_components = organizational_unit.split("/")
        processed_components = []
        for part in reversed(ou_path_components):
            if not (part.upper().startswith("OU=") or part.upper().startswith("CN=")):
                processed_components.append(f"OU={part}")
            else:
                processed_components.append(part)
        dn += ",".join(processed_components) + ","
    else:
        standard_containers_map = {"USERS": "CN=Users", "BUILTIN": "CN=Builtin"}
        normalized_ou_str = organizational_unit.upper()

        if normalized_ou_str in standard_containers_map and not organizational_unit.upper().startswith("CN="):
            dn += f"{standard_containers_map[normalized_ou_str]},"
        elif not (organizational_unit.upper().startswith("OU=") or organizational_unit.upper().startswith("CN=")):
            dn += f"OU={organizational_unit},"
        else:
            dn += f"{organizational_unit},"

    dn += domain_dn_suffix
    return dn


def correct_username(username: str, domain: str) -> str:
    """
    Ensures the username is in the correct format for Active Directory authentication.
    Args:
        username (str): Can be provided as either 'username' or 'DOMAIN\\username' (e.g., "EXAMPLE\\user1").
        domain (str): Full domain name in the format 'subdomain.domain.local'.
    Returns:
        str: Correctly formatted username as 'DOMAIN\\username'.
    """
    if '\\' in username:
        return username

    domain_prefix = domain.split('.')[0].upper()
    return f"{domain_prefix}\\{username}"