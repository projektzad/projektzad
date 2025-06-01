# myapp/app/models/connection.py
from ldap3 import Server, Connection, ALL, Tls
from ldap3.core.exceptions import LDAPException
import ssl  # For Tls configuration if needed for specific CA certs
import logging  # For logging connection attempts and errors

# Assuming connection_utils.py is in the same directory (models)
# and that the 'models' directory is in sys.path.
# If connection_utils is one level up (in 'app'), it might be:
# from ..connection_utils import validate_ldap_server, correct_username
# For now, assuming it's in the same 'models' package:
import connection_utils as cu  # Relative import for modules within the same package

# Get a logger for this module
logger = logging.getLogger(__name__)


def connect_to_active_directory(ldap_server_form_input: str, username: str, password: str, domain: str) -> tuple[bool, Connection | None]:
    """
    Creates a connection (plain LDAP) with Active Directory.

    Args:
        ldap_server_form_input (str): Server's IP or name (e.g., "ad.example.com" or "ldap://ad.example.com:389").
        username (str): User's login name.
        password (str): User's password.
        domain (str): User's domain name (e.g., "example.com").

    Returns:
        Tuple (bool, Connection | None): Success flag and connection object (or None).
    """

    # Default to ldap:// if no scheme is provided
    if "://" not in ldap_server_form_input:
        server_url = f"ldap://{ldap_server_form_input}"
        logger.info(f"No scheme provided, defaulting to ldap://: {server_url}")
    else:
        server_url = ldap_server_form_input
        if server_url.startswith("ldaps://"):
            logger.warning(f"LDAPS requested but not supported by server. Forcing downgrade to ldap://")
            server_url = server_url.replace("ldaps://", "ldap://")

    corrected_ldap_username = cu.correct_username(username=username, domain=domain)

    try:
        server = Server(server_url, get_info=ALL, use_ssl=False)

        conn = Connection(
            server,
            user=corrected_ldap_username,
            password=password,
            auto_bind=True,
            raise_exceptions=True,
            receive_timeout=15
        )

        logger.info(f"Connected to LDAP server {server_url} as {corrected_ldap_username}")
        return True, conn

    except LDAPException as e:
        logger.error(f"LDAP connection/bind error to {server_url} as {corrected_ldap_username}: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Generic error during LDAP connection attempt to {server_url}: {e}", exc_info=True)
        return False, None


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
