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

def create_distinguished_name(username: str, domain: str, organizational_unit:str ="Users") -> str:
    """
        Combines arguments into distinguished name (necessery to authenticate to Actve Directory)

        Args:
            username (str): 
            domain (str): provided as:         subdomain.domain.local
            organizational_unit (str): OU where the User is located. Default = Users
        Returns:
            bool:
                - if format is correct returns: True
                - otherwise: False
    """
    domain_parts = domain.split(".")
    dn = f"CN={username},CN={organizational_unit}," + ",".join([f"DC={part}" for part in domain_parts])

    return dn