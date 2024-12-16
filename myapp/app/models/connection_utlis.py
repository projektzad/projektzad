import re, os

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

def create_distinguished_name(username: str, domain: str, organizational_unit: str = "Users") -> str:
    """
    Combines arguments into a distinguished name (necessary to authenticate to Active Directory).
    Supports nested Organizational Units (OUs) separated by '/'.

    Args:
        username (str): The username of the user.
        domain (str): The domain in the format: subdomain.domain.local (e.g., "example.domain.local").
        organizational_unit (str): The organizational unit (OU) where the user is located.
                                   Can be a single OU (e.g., "Users") or multiple nested OUs separated by '/' 
                                   (e.g., "OU=testOU/nestedOU1/nestedOU2").
                                   Default is "Users".

    Returns:
        str: The distinguished name (DN) in the format:
             "CN=username,OU=organizational_unit1,OU=organizational_unit2,...,DC=subdomain,DC=domain,DC=local".
    """
    domain_parts = domain.split(".")
    
    if "/" in organizational_unit:
        ou_parts = organizational_unit.split("/")
        ou_parts.reverse()
        ou_dn = ",".join([f"OU={ou}" for ou in ou_parts])
        dn = f"CN={username},{ou_dn}," + ",".join([f"DC={part}" for part in domain_parts])
    else:
        if organizational_unit == "Users":
            dn = f"CN={username},CN={organizational_unit}," + ",".join([f"DC={part}" for part in domain_parts])
        else:
            dn = f"CN={username},OU={organizational_unit}," + ",".join([f"DC={part}" for part in domain_parts])
    
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
