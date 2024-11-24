from ldap3 import Server, Connection, ALL
import connection_utlis as cu


def connect_to_active_directory(ldap_server: str, username: str, password: str, domain: str) -> (bool, Connection):
    """
        Creates connection with Active Directory, user's password is saved to enviromental variable

        Args:
            ldap_server (str): servers IP or name
            username (str): user's name in format of 'EXAMPLE-AD\\username' or just 'username'
            password (str): password in plain text
            domain (str): domain name provided as ad.example.test.local

        Returns:
            Tuple (bool, Connection):
                - if connection was established returns True
                - otherwise returns False
                + Connection object or None

    """
    if cu.validate_ldap_server(ldap_server):
        server = Server(ldap_server, get_info=ALL)
        cu.set_users_password_from_env_variable(password=password)

        username = cu.correct_username(username=username, domain=domain)
        conn = Connection(server, user=username, password=password)

        if conn.bind():
            return (True, conn)
        
        return (False, conn)

    return (False, None)

def disconnect_from_active_directory(conn: Connection) -> bool:
    """
        Disconnects from the Active Directory server by unbinding the connection.

        Args:
            conn (Connection): The connection object representing the connection to Active Directory.

        Returns:
            bool:
                - True if the disconnection was successful.
                - False if an error occurred while trying to disconnect (unbind).
    """

    try:
        conn.unbind()
    except Exception:
        return False

    return True

