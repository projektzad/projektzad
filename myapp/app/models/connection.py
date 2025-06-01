# myapp/app/models/connection.py
from ldap3 import Server, Connection, ALL, Tls, LDAPException
import ssl  # For Tls configuration if needed for specific CA certs
import logging  # For logging connection attempts and errors

# Assuming connection_utils.py is in the same directory (models)
# and that the 'models' directory is in sys.path.
# If connection_utils is one level up (in 'app'), it might be:
# from ..connection_utils import validate_ldap_server, correct_username
# For now, assuming it's in the same 'models' package:
from . import connection_utils as cu  # Relative import for modules within the same package

# Get a logger for this module
logger = logging.getLogger(__name__)


def connect_to_active_directory(ldap_server_form_input: str, username: str, password: str, domain: str) -> tuple[
    bool, Connection | None]:
    """
    Creates a secure connection (LDAPS) with Active Directory.

    Args:
        ldap_server_form_input (str): Server's IP or name (e.g., "ad.example.com").
                                      Can also be a full URL like "ldaps://ad.example.com:636".
        username (str): User's login name.
        password (str): User's password in plain text.
        domain (str): User's domain name (e.g., "example.com" or "sub.example.com").

    Returns:
        Tuple (bool, Connection | None):
            - (True, Connection object) if the connection was established successfully.
            - (False, None) otherwise.
    """

    # Validate the server string format (optional, but good practice)
    # cu.validate_ldap_server might need adjustment if it doesn't expect "ldaps://"
    # For now, we'll proceed assuming basic validation or handle it in server_url construction.

    # Prepare the server URL for LDAPS
    server_url = ldap_server_form_input
    if "://" not in ldap_server_form_input:
        # If no scheme, assume LDAPS and default port 636
        server_url = f"ldaps://{ldap_server_form_input}"
        logger.info(f"No scheme in ldap_server input, defaulting to LDAPS: {server_url}")
    elif ldap_server_form_input.startswith("ldap://"):
        # If ldap:// was explicitly given, attempt to upgrade to ldaps://
        server_url = ldap_server_form_input.replace("ldap://", "ldaps://")
        logger.warning(
            f"Original server URL was ldap://, attempting to use ldaps:// ({server_url}) for security and stability.")

    # Ensure the username is in the 'DOMAIN\user' or 'user@domain.com' format
    # cu.correct_username might need to be reviewed if it only produces 'DOMAIN\user'
    # For ldap3, 'user@domain.com' (User Principal Name) is often more robust.
    # However, sticking to your existing cu.correct_username for now.
    corrected_ldap_username = cu.correct_username(username=username, domain=domain)

    try:
        # For production with an internal CA, you might need to configure Tls object:
        # tls_config = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file='/path/to/your/ca_bundle.pem')
        # server = Server(server_url, get_info=ALL, use_ssl=True, tls=tls_config)

        # Simpler SSL/TLS enabling (relies on system's trust store for CA certs):
        server = Server(server_url, get_info=ALL, use_ssl=True)

        # auto_bind=True attempts to bind when the Connection object is created.
        # raise_exceptions=True will make it raise an LDAPException on failure.
        conn = Connection(server,
                          user=corrected_ldap_username,
                          password=password,
                          auto_bind=True,
                          raise_exceptions=True,
                          receive_timeout=15)  # Optional: timeout for receiving responses

        logger.info(
            f"Successfully connected and bound to LDAPS server: {server_url} as user: {corrected_ldap_username}")
        return (True, conn)

    except LDAPException as e:  # Catch specific LDAP exceptions
        logger.error(f"LDAP connection/bind error to {server_url} as {corrected_ldap_username}: {e}",
                     exc_info=False)  # exc_info=False to avoid logging full traceback for common auth errors
        return (False, None)
    except Exception as e:  # Catch other potential errors (e.g., network issues before LDAP bind)
        logger.error(f"Generic error during LDAP connection attempt to {server_url}: {e}", exc_info=True)
        return (False, None)


def disconnect_from_active_directory(conn: Connection | None) -> bool:
    """
    Disconnects from the Active Directory server by unbinding the connection.

    Args:
        conn (Connection | None): The connection object or None.

    Returns:
        bool: True if the disconnection was successful or if no connection was provided.
              False if an error occurred while trying to unbind.
    """
    if conn:
        try:
            conn.unbind()
            logger.info("LDAP connection unbound successfully.")
            return True
        except LDAPException as e:  # Catch specific LDAP exceptions
            logger.error(f"Error unbinding LDAP connection: {e}", exc_info=True)
            return False
        except Exception as e:  # Catch other potential errors
            logger.error(f"Generic error during LDAP unbind: {e}", exc_info=True)
            return False
    return True  # No connection object provided, so considered "successful"
