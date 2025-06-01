# myapp/app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, current_app
from functools import wraps
from werkzeug.utils import secure_filename
import sys
import os
from datetime import datetime
import re
import uuid
from threading import Lock
import csv  # Added import for csv
import openpyxl  # Added import for openpyxl

# Get the absolute path to the 'models' directory
models_path = os.path.join(os.path.dirname(__file__), 'models')

# Append the path to sys.path
sys.path.append(models_path)

# Import the necessary modules and functions
from app.models.batch_add import import_users_from_file
from app.models import connection as co
from app.models.block import change_users_block_status, get_blocked_users_count, block_multiple_users
from app.models.all_users import get_all_users, get_all_users_count, get_user_groups
from app.config_utils import save_user_defaults, get_default_attributes, load_config
from app.models.expire import expire_multiple_users, set_account_expiration, get_expiring_users_count
from app.models.add import create_user
from app.models.group_modify import (
    list_all_groups,
    add_user_to_group,  # Keep for old usage, or remove if not needed
    remove_user_from_group,  # Keep for old usage, or remove if not needed
    list_group_members,  # Now expects group_dn
    remove_group,
    add_new_group,
    load_json_config,
    # create_group_dn, # No longer needed if list_all_groups provides full DNs
    add_user_to_group_by_dn,
    remove_user_from_group_by_dn
)
from app.models.delete import delete_user_from_active_directory
from app.models.batch_delete_users import delete_multiple_users as batch_delete_users_from_file
from connection_utils import create_distinguished_name  # Renamed import to connection_utils

main_routes = Blueprint('main', __name__)

# --- LDAP Connection Management ---
_ldap_connections = {}
_lock = Lock()


def set_ldap_connection(session_id, connection):
    with _lock:
        _ldap_connections[session_id] = connection


def get_ldap_connection(session_id):
    with _lock:
        return _ldap_connections.get(session_id)


def remove_ldap_connection(session_id):
    with _lock:
        conn = _ldap_connections.pop(session_id, None)
        if conn:
            try:
                conn.unbind()
            except Exception as e:
                logger = getattr(current_app, 'logger', None)
                if logger:
                    logger.error(f"Error unbinding LDAP connection for session {session_id}: {e}", exc_info=True)
                else:
                    print(f"Error unbinding LDAP connection for session {session_id}: {e}")


# --- Decorator for LDAP Connection ---
def ldap_connection_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = session.get('session_id')
        if not session_id:
            flash("No active session. Please log in again.", "danger")
            return redirect(url_for('main.login'))

        connection = get_ldap_connection(session_id)

        if not connection:
            flash("No active LDAP connection. Please log in again.", "danger")
            return redirect(url_for('main.login'))

        if not connection.bound:
            flash("LDAP connection was lost. Please log in again.", "warning")
            remove_ldap_connection(session_id)
            return redirect(url_for('main.login'))

        g.ldap_conn = connection  # Store the active connection in Flask's request context 'g'
        return f(*args, **kwargs)

    return decorated_function


# --- Helper Functions ---
def flash_error(message):
    flash(message, 'danger')


def domain_to_search_base(domain):
    """
    Converts a domain string (e.g., "testad.local") to an LDAP search base (e.g., "dc=testad,dc=local").
    """
    domain_parts = domain.split('.')
    search_base = ','.join(f"dc={part}" for part in domain_parts)
    return search_base


def parse_distinguished_name(dn_string: str):
    """
    Parses a Distinguished Name (DN) string to extract object CN, domain string, and
    the organizational unit/container path string suitable for create_distinguished_name.
    Example: From "CN=John Doe,OU=Sales,CN=Users,DC=example,DC=com"
    Returns: ("John Doe", "example.com", "OU=Sales/CN=Users")
    Or: ("John Doe", "example.com", "CN=Users") if no OUs.
    Or: ("John Doe", "example.com", "Sales") if just "OU=Sales".
    """
    if not dn_string:
        return None, None, None

    object_cn_match = re.match(r"CN=([^,]+)", dn_string, re.IGNORECASE)
    object_cn = object_cn_match.group(1) if object_cn_match else None

    domain_parts_dc = re.findall(r"DC=([^,]+)", dn_string, re.IGNORECASE)
    domain_str = ".".join(domain_parts_dc) if domain_parts_dc else None

    # Extract the part between the first CN and the first DC
    # CN=object_cn , THIS_IS_THE_OU_PATH_STRING , DC=domain,DC=com
    # Match the part after the first CN=... and before the first DC=...
    ou_path_string_for_create_dn = None
    match_ou_part = re.match(r"CN=[^,]+,(.*?),DC=", dn_string, re.IGNORECASE)
    if match_ou_part:
        raw_ou_part = match_ou_part.group(1).strip()
        if raw_ou_part:
            # Split by comma, reverse, and then format correctly
            # Example: "OU=Sales,OU=IT,CN=Users" -> ["CN=Users", "OU=IT", "OU=Sales"]
            # We want to join them with '/' in the order expected by create_distinguished_name's parser
            # (which is reverse, i.e., child/parent)
            components = [part.strip() for part in raw_ou_part.split(',')]

            formatted_components = []
            for comp in reversed(components):  # Iterate from child to parent
                if comp.upper().startswith("OU="):
                    formatted_components.append(comp[3:])  # Just the name (e.g., "Sales")
                elif comp.upper().startswith("CN="):
                    formatted_components.append(comp)  # Keep as "CN=Users" or "CN=Builtin"
                else:
                    formatted_components.append(comp)  # Keep as is if unknown prefix, might be error

            ou_path_string_for_create_dn = "/".join(formatted_components)

    return object_cn, domain_str, ou_path_string_for_create_dn


# Decorator requiring admin privileges (definition was missing, adding a placeholder)
def requires_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Placeholder: Implement actual role check from session
        if session.get('role') != 'admin':
            flash('Admin privileges required for this action.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function


# Helper function to get domain_to_dn from connection_utils.py if it exists, or define locally
def _domain_to_dn_local(domain_str: str) -> str:
    """Converts a domain string (e.g., "testad.local") to an LDAP DN (e.g., "DC=testad,DC=local")."""
    parts = domain_str.split('.')
    dn = ','.join([f"DC={part}" for part in parts])  # Ensure DC is uppercase as often standard
    return dn


# Attempt to import domain_to_dn from connection_utils
try:
    from connection_utils import domain_to_dn
except ImportError:
    # If not found (e.g., old version or different structure), use local fallback
    domain_to_dn = _domain_to_dn_local


# --- Routes ---

@main_routes.route('/')
@ldap_connection_required
def index():
    domain = session.get('domain', 'default.local')
    search_base = domain_to_search_base(domain)

    try:
        stats = {
            'total_users': get_all_users_count(g.ldap_conn, search_base),
            'blocked_users': get_blocked_users_count(g.ldap_conn, search_base),
            'expiring_users': get_expiring_users_count(g.ldap_conn, search_base)
        }
        return render_template('index.html', login=session.get("login"), stats=stats)
    except Exception as e:
        current_app.logger.error(f"Error in index endpoint: {e}", exc_info=True)
        flash(f"An error occurred while fetching statistics: {str(e)}", "danger")
        return render_template('index.html', login=session.get("login"),
                               stats={'total_users': 'N/A', 'blocked_users': 'N/A', 'expiring_users': 'N/A'})


@main_routes.route('/checkbox_form', methods=['GET', 'POST'])
def checkbox_form():
    # This route does not directly use LDAP connection but relies on session
    options = [
        'objectClass', 'cn', 'sAMAccountName', 'userPrincipalName', 'givenName', 'sn',
        'displayName', 'uid', 'uidNumber', 'gidNumber', 'unixHomeDirectory', 'loginShell',
        'homeDirectory', 'homeDrive', 'mail', 'whenChanged', 'whenCreated', 'uSNChanged',
        'uSNCreated', 'userAccountControl', 'sAMAccountType', 'pwdLastSet', 'primaryGroupID',
        'objectCategory', 'objectGUID', 'objectSid', 'logonCount', 'instanceType',
        'dSCorePropagationData', 'countryCode', 'codePage', 'badPwdCount',
        'badPasswordTime', 'accountExpires'
    ]

    if request.method == 'POST':
        selected_filters = request.form.getlist('filter_options')
        selected_columns = request.form.getlist('column_options')

        default_cols = ["name", "distinguishedName"]
        for col in default_cols:
            if col not in selected_columns:
                selected_columns.append(col)

        session['options'] = selected_filters
        session['columns'] = selected_columns

        flash(f'Selected columns updated: {", ".join(selected_columns)}', 'success')
        flash(f'Selected filters updated: {", ".join(selected_filters)}', 'info')

        previous_url = request.form.get('previous_url', url_for('main.index'))
        return redirect(previous_url)

    preselected_columns = session.get('columns', ["name", "distinguishedName"])
    preselected_filters = session.get('options', [])

    return render_template(
        'checkbox.html',
        options=options,
        preselected_columns=preselected_columns,
        preselected_filters=preselected_filters
    )


@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ldap_server_form = request.form['ldap_server']
        login_form = request.form['login']
        password_form = request.form['password']
        domain_form = request.form['domain']

        is_connected, connection_obj = co.connect_to_active_directory(ldap_server_form, login_form, password_form,
                                                                      domain_form)
        if is_connected:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            session['login'] = login_form
            session['ldap_server'] = ldap_server_form
            session['domain'] = domain_form
            session.setdefault('columns', ["name", "distinguishedName"])
            session.setdefault('options', [])

            set_ldap_connection(session_id, connection_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash_error("Login failed. Please check your credentials and server details.")
            return render_template('login.html')
    return render_template('login.html')


@main_routes.route('/logout')
def logout():
    session_id = session.pop('session_id', None)
    if session_id:
        remove_ldap_connection(session_id)

    keys_to_pop = ['login', 'ldap_server', 'domain', 'columns', 'options', 'import_file', 'role']
    for key in keys_to_pop:
        session.pop(key, None)

    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@main_routes.route('/delete_user', methods=['GET', 'POST'])
@ldap_connection_required
def delete_user():
    if request.method == 'POST':
        if 'selected_users' in request.form:
            return delete_user_post_selected(g.ldap_conn)
        elif 'file' in request.files and request.files['file'].filename != '':
            return delete_user_file_upload(g.ldap_conn)
        else:
            flash_error("No users selected or no file uploaded.")
            return redirect(url_for('main.delete_user'))

    return delete_user_get_form(g.ldap_conn)


# Helper for GET request part of delete_user
def delete_user_get_form(conn):
    try:
        domain = session.get('domain', 'default.local')
        search_base = domain_to_search_base(domain)

        selected_filters = session.get('options', [])
        display_columns = session.get('columns', ["name", "distinguishedName"])
        attributes_to_fetch = list(set(selected_filters + display_columns + ['name', 'distinguishedName']))

        users = get_all_users(conn, search_base, attributes_to_fetch)
        return render_template('delete_user.html', users=users, cols=display_columns, options=selected_filters)
    except Exception as e:
        current_app.logger.error(f"Error fetching users for deletion form: {e}", exc_info=True)
        flash_error(f"Could not retrieve user list: {str(e)}")
        return redirect(url_for('main.index'))


# Helper for POST request (selected users) part of delete_user
def delete_user_post_selected(conn):
    selected_users_data = request.form.getlist('selected_users')
    if not selected_users_data:
        flash_error("No users selected for deletion.")
        return redirect(url_for('main.delete_user'))

    errors = []
    successes = []

    for user_dn_data in selected_users_data:
        try:
            # Expecting value in "name|distinguishedName" format
            user_cn_display, user_dn = user_dn_data.split('|', 1)

            # parse_distinguished_name returns object_cn, domain_str, ou_path_string_for_create_dn
            object_cn_parsed, domain_str_parsed, ou_path_str_parsed = parse_distinguished_name(user_dn)

            if not object_cn_parsed or not domain_str_parsed:
                errors.append(f"Invalid DN format for deletion: {user_dn}")
                current_app.logger.warning(
                    f"Could not parse DN for deletion: {user_dn}. Parsed: cn={object_cn_parsed}, domain={domain_str_parsed}, ou_path={ou_path_str_parsed}")
                continue

            # delete_user_from_active_directory expects conn, username (CN), domain, organizational_unit string
            # The ou_path_str_parsed is the string like "OU=Sales/CN=Users" or "CN=Users" or "Sales"
            # It should be directly compatible with create_distinguished_name's organizational_unit parameter

            if delete_user_from_active_directory(conn, object_cn_parsed, domain_str_parsed, ou_path_str_parsed):
                successes.append(user_cn_display)
            else:
                errors.append(user_cn_display)
                current_app.logger.error(
                    f"Failed to delete user {user_cn_display} (DN: {user_dn}). LDAP Result: {conn.result}")

        except ValueError:
            errors.append(f"Invalid user data format (missing '|'): {user_dn_data}")
            current_app.logger.error(f"ValueError parsing user data for deletion: {user_dn_data}", exc_info=True)
        except Exception as e:
            errors.append(f"Error deleting user from DN {user_dn_data}: {str(e)}")
            current_app.logger.error(f"Exception during user deletion (DN: {user_dn_data}): {e}", exc_info=True)

    if successes:
        flash(f"Users {', '.join(successes)} were successfully deleted.", 'success')
    if errors:
        flash_error(f"Errors occurred while deleting users: {', '.join(errors)}.")

    return redirect(url_for('main.delete_user'))


# Helper for POST request (file upload) part of delete_user
def delete_user_file_upload(conn):
    file = request.files['file']
    filename = secure_filename(file.filename)
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)

    try:
        file.save(file_path)
        deleted_count = batch_delete_users_from_file(conn, file_path)
        flash(f"{deleted_count} users were processed for deletion from the file.", 'success')
    except Exception as e:
        current_app.logger.error(f"Error processing user deletion file {filename}: {e}", exc_info=True)
        flash_error(f"An error occurred while processing the file: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e_remove:
                current_app.logger.error(f"Error removing uploaded file {file_path}: {e_remove}", exc_info=True)

    return redirect(url_for('main.delete_user'))


@main_routes.route('/add_user', methods=['GET', 'POST'])
@ldap_connection_required
def add_user():
    if request.method == 'POST':
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']

            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in [".csv", ".xlsx", ".xls"]:
                flash("Unsupported file format. Please use CSV or XLSX.", "danger")
                return redirect(url_for('main.add_user'))

            unique_name = f"import_{uuid.uuid4().hex}{ext}"

            upload_folder = current_app.config.get('UPLOAD_FOLDER_STATIC', os.path.join('app', 'static'))
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            filepath = os.path.join(upload_folder, unique_name)

            try:
                file.save(filepath)
                preview_data = []
                if ext == ".csv":
                    with open(filepath, newline='', encoding='utf-8-sig') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            preview_data.append(row)
                elif ext in [".xlsx", ".xls"]:
                    wb = openpyxl.load_workbook(filepath)
                    sheet = wb.active
                    headers = [cell.value for cell in sheet[1]]
                    for row_idx in range(2, sheet.max_row + 1):
                        row_values = [cell.value for cell in sheet[row_idx]]
                        row_data = dict(zip(headers, row_values))
                        preview_data.append(row_data)

                session['import_file'] = filepath
                return render_template("preview_import.html", users=preview_data)

            except Exception as e:
                current_app.logger.error(f"Error processing file for preview {file.filename}: {e}", exc_info=True)
                flash(f"Error processing file: {str(e)}", "danger")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(url_for('main.add_user'))

        elif 'confirm_import' in request.form:
            filepath = session.get('import_file')
            if not filepath or not os.path.exists(filepath):
                flash("No file to import or file not found. Please try uploading again.", "danger")
                return redirect(url_for('main.add_user'))

            domain = session.get('domain')
            dc_parts = [f"DC={part}" for part in domain.split('.')]
            search_base_domain = ','.join(dc_parts)

            result = import_users_from_file(g.ldap_conn, filepath, search_base_domain, search_base_domain)

            if 'error' in result:
                flash(result['error'], 'danger')
            else:
                flash_message = f"Import complete. Added: {result.get('added', 0)}, Failed: {result.get('failed', 0)}."
                if result.get('errors'):
                    flash_message += " See logs for details on failures."
                flash(flash_message, 'info')

            if os.path.exists(filepath):
                os.remove(filepath)
            session.pop('import_file', None)

            return redirect(url_for('main.add_user'))

        else:
            return add_single_user_post(g.ldap_conn)

    return render_template('add_user.html')


# Helper for single user addition POST
def add_single_user_post(conn):
    username = request.form.get('username')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')

    if not all([username, first_name, last_name, password]):
        flash_error("All fields for single user addition are required.")
        return render_template('add_user.html')

    try:
        domain = session.get('domain')
        dc_parts = [f"DC={part}" for part in domain.split('.')]
        dc_string = ','.join(dc_parts)
        search_base_domain = dc_string

        # create_user expects: conn, username, firstname, lastname, password, ou_for_dn, dc_for_dn_and_upn, search_base_for_uid
        # The OU is now fetched from config inside create_user by get_default_ou()

        success = create_user(conn, username, first_name, last_name, password,
                              None,  # Passing None, create_user will use default_ou from config
                              dc_string,
                              search_base_domain)
        if success:
            flash(f"User {username} created successfully.", "success")
        else:
            flash_error(f"Failed to create user {username}. Check server logs for details.")
    except Exception as e:
        current_app.logger.error(f"Error creating single user {username}: {e}", exc_info=True)
        flash_error(f"An error occurred: {str(e)}")

    return redirect(url_for('main.add_user'))


@main_routes.route('/toggle_block_user', methods=['GET', 'POST'])
@ldap_connection_required
def toggle_block_user():
    if request.method == 'POST':
        if 'selected_users' in request.form:
            return toggle_block_user_post_selected(g.ldap_conn)
        elif 'file' in request.files and request.files['file'].filename != '':
            return toggle_block_user_file_upload(g.ldap_conn)
        else:
            flash_error("No users selected or no file uploaded.")
            return redirect(url_for('main.toggle_block_user'))

    return toggle_block_user_get_form(g.ldap_conn)


# Helper for GET request part of toggle_block_user
def toggle_block_user_get_form(conn):
    try:
        domain = session.get('domain', 'default.local')
        search_base = domain_to_search_base(domain)

        selected_filters = session.get('options', [])
        display_columns = session.get('columns', ["name", "distinguishedName"])

        attributes_to_fetch = list(
            set(selected_filters + display_columns + ['userAccountControl', 'name', 'distinguishedName']))

        users = get_all_users(conn, search_base, attributes_to_fetch)

        for user in users:
            uac_flags_str = str(user.get("userAccountControl", "")).lower()
            user["is_disabled"] = "accountdisable" in uac_flags_str

        return render_template('block_user.html', users=users, cols=display_columns, options=selected_filters)
    except Exception as e:
        current_app.logger.error(f"Error fetching users for block/unblock form: {e}", exc_info=True)
        flash_error(f"Could not retrieve user list: {str(e)}")
        return redirect(url_for('main.index'))


# Helper for POST (selected users) part of toggle_block_user
def toggle_block_user_post_selected(conn):
    selected_users_data = request.form.getlist('selected_users')
    if not selected_users_data:
        flash_error("No users selected.")
        return redirect(url_for('main.toggle_block_user'))

    errors = []
    successes = []
    for user_dn_data in selected_users_data:
        try:
            user_cn_display, user_dn = user_dn_data.split('|', 1)
            # parse_distinguished_name returns object_cn, domain_str, ou_path_string_for_create_dn
            object_cn_parsed, domain_str_parsed, ou_path_str_parsed = parse_distinguished_name(user_dn)

            if not object_cn_parsed or not domain_str_parsed:
                errors.append(f"Invalid DN: {user_dn} (could not parse)")
                current_app.logger.warning(
                    f"Could not parse DN for toggle block status: {user_dn}. Parsed: cn={object_cn_parsed}, domain={domain_str_parsed}, ou_path={ou_path_str_parsed}")
                continue

            # The ou_path_str_parsed is the string like "OU=Sales/CN=Users" or "CN=Users" or "Sales".
            # It's directly compatible with create_distinguished_name's organizational_unit parameter.
            # change_users_block_status expects conn, canonical_name (CN), domain, organizational_unit string
            if change_users_block_status(conn, object_cn_parsed, domain_str_parsed, ou_path_str_parsed):
                successes.append(user_cn_display)
            else:
                errors.append(user_cn_display)
                current_app.logger.error(
                    f"Failed to toggle block status for {user_cn_display} (DN: {user_dn}). LDAP Result: {conn.result}")

        except ValueError:
            errors.append(f"Invalid data format for: {user_dn_data}")
            current_app.logger.error(f"ValueError parsing user data for toggle block: {user_dn_data}", exc_info=True)
        except Exception as e:
            errors.append(f"Error processing {user_dn_data}: {str(e)}")
            current_app.logger.error(f"Exception toggling block status (DN: {user_dn_data}): {e}", exc_info=True)

    if successes:
        flash(f"Block status toggled for users: {', '.join(successes)}.", "success")
    if errors:
        flash_error(f"Errors occurred for users: {', '.join(errors)}.")
    return redirect(url_for('main.toggle_block_user'))


# Helper for POST (file upload) part of toggle_block_user
def toggle_block_user_file_upload(conn):
    file = request.files['file']
    filename = secure_filename(file.filename)
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)

    try:
        file.save(file_path)
        processed_count = block_multiple_users(conn,
                                               file_path)  # block_multiple_users will use create_distinguished_name
        flash(f"{processed_count} users from file were processed (attempted to block/unblock).", 'info')
    except Exception as e:
        current_app.logger.error(f"Error processing block/unblock file {filename}: {e}", exc_info=True)
        flash_error(f"An error occurred while processing the file: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e_remove:
                current_app.logger.error(f"Error removing block/unblock file {file_path}: {e_remove}", exc_info=True)
    return redirect(url_for('main.toggle_block_user'))


@main_routes.route('/expire_user', methods=['GET', 'POST'])
@ldap_connection_required
def expire_user():
    if request.method == 'POST':
        if 'file' in request.files and request.files['file'].filename != '':
            return expire_user_file_upload(g.ldap_conn)
        elif request.form.getlist('selected_users'):
            return expire_user_post_selected(g.ldap_conn)
        else:
            flash_error("No users selected or no file provided for expiration.")
            return redirect(url_for('main.expire_user'))

    return expire_user_get_form(g.ldap_conn)


# Helper for GET request part of expire_user
def expire_user_get_form(conn):
    try:
        domain = session.get('domain', 'default.local')
        search_base = domain_to_search_base(domain)

        selected_filters = session.get('options', [])
        display_columns = session.get('columns', ["name", "distinguishedName"])
        attributes_to_fetch = list(
            set(selected_filters + display_columns + ['accountExpires', 'name', 'distinguishedName']))

        users = get_all_users(conn, search_base, attributes_to_fetch)
        return render_template('expire_user.html', users=users, cols=display_columns, options=selected_filters)
    except Exception as e:
        current_app.logger.error(f"Error fetching users for expiration form: {e}", exc_info=True)
        flash_error(f"Could not retrieve user list: {str(e)}")
        return redirect(url_for('main.index'))


# Helper for POST (selected users) part of expire_user
def expire_user_post_selected(conn):
    selected_users_data = request.form.getlist('selected_users')
    expiration_date_str = request.form.get('expiration_date')  # YYYY-MM-DD from <input type="date">

    if not selected_users_data:
        flash_error("No users selected.")
        return redirect(url_for('main.expire_user'))
    if not expiration_date_str:
        flash_error("Expiration date not provided.")
        return redirect(url_for('main.expire_user'))

    try:
        # Convert YYYY-MM-DD to DD-MM-YYYY for set_account_expiration function
        formatted_date_for_ldap = datetime.strptime(expiration_date_str, '%Y-%m-%d').strftime('%d-%m-%Y')
    except ValueError:
        flash_error("Invalid date format provided.")
        return redirect(url_for('main.expire_user'))

    errors = []
    successes = []
    for user_dn_data in selected_users_data:
        try:
            user_cn_display, user_dn = user_dn_data.split('|', 1)
            object_cn_parsed, domain_str_parsed, ou_path_str_parsed = parse_distinguished_name(user_dn)

            if not object_cn_parsed or not domain_str_parsed:
                errors.append(f"Invalid DN: {user_dn} (could not parse)")
                current_app.logger.warning(
                    f"Could not parse DN for expiration: {user_dn}. Parsed: cn={object_cn_parsed}, domain={domain_str_parsed}, ou_path={ou_path_str_parsed}")
                continue

            # set_account_expiration expects conn, canonical_name (CN), domain, expiration_date (DD-MM-YYYY), organizational_unit string
            if set_account_expiration(conn, object_cn_parsed, domain_str_parsed, formatted_date_for_ldap,
                                      ou_path_str_parsed):
                successes.append(user_cn_display)
            else:
                errors.append(user_cn_display)
                current_app.logger.error(
                    f"Failed to set expiration for {user_cn_display} (DN: {user_dn}). LDAP Result: {conn.result}")
        except ValueError:
            errors.append(f"Invalid data format for: {user_dn_data}")
            current_app.logger.error(f"ValueError parsing user data for expiration: {user_dn_data}", exc_info=True)
        except Exception as e:
            errors.append(f"Error processing {user_dn_data}: {str(e)}")
            current_app.logger.error(f"Exception setting expiration (DN: {user_dn_data}): {e}", exc_info=True)

    if successes:
        flash(f"Expiration date set for users: {', '.join(successes)}.", "success")
    if errors:
        flash_error(f"Errors occurred for users: {', '.join(errors)}.")
    return redirect(url_for('main.expire_user'))


# Helper for POST (file upload) part of expire_user
def expire_user_file_upload(conn):
    file = request.files['file']
    filename = secure_filename(file.filename)
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)

    try:
        file.save(file_path)
        expired_count = expire_multiple_users(conn,
                                              file_path)  # expire_multiple_users will use create_distinguished_name
        flash(f"{expired_count} users from file had their expiration date processed.", 'info')
    except Exception as e:
        current_app.logger.error(f"Error processing expiration file {filename}: {e}", exc_info=True)
        flash_error(f"An error occurred while processing the file: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e_remove:
                current_app.logger.error(f"Error removing expiration file {file_path}: {e_remove}", exc_info=True)
    return redirect(url_for('main.expire_user'))

@main_routes.route('/groups_management', methods=['GET', 'POST'])
@ldap_connection_required
def groups_management():
    domain_session = session.get('domain', 'company.com')

    if request.method == 'POST':
        return handle_post_group_management_actions(g.ldap_conn, domain_session)

    return handle_get_group_management_form(g.ldap_conn, domain_session)


# Helper for POST group management actions
def handle_post_group_management_actions(conn, domain):
    action = request.form.get('action')
    group_name_cn = request.form.get('group_name')

    if not group_name_cn:
        flash_error("Group name (CN) cannot be empty.")
        return redirect(url_for('main.groups_management'))

    if action == 'add':
        try:
            config_template_path = os.path.join(current_app.root_path, 'templates', 'group-config.json')

            if not os.path.exists(config_template_path):
                flash_error(f"Group configuration template not found at '{config_template_path}'.")
                return redirect(url_for('main.groups_management'))

            group_config = load_json_config(config_template_path)

            group_config['General']['Group name (pre-Windows 2000)'] = group_name_cn
            group_config['General']['Description'] = f"Group '{group_name_cn}' created via web app."

            domain_components = [part.split('=')[1] for part in domain.split(',') if part.lower().startswith('dc=')]
            actual_email_domain = '.'.join(domain_components)
            if actual_email_domain:
                group_config['General'][
                    'E-mail'] = f"{group_name_cn.lower().replace(' ', '.').replace('/', '')}@{actual_email_domain}"
            else:
                group_config['General']['E-mail'] = None

            if add_new_group(conn, group_config):
                flash(f"Group '{group_name_cn}' added successfully.", "success")
            else:
                flash_error(
                    f"Failed to add group '{group_name_cn}'. LDAP Error: {conn.result.get('description', 'Unknown error')}")
        except FileNotFoundError:
            flash_error(f"Configuration file not found at path: {config_template_path}")
        except KeyError as ke:
            flash_error(f"Configuration is missing a required field: {str(ke)}")
        except Exception as e:
            current_app.logger.error(f"Error adding group '{group_name_cn}': {e}", exc_info=True)
            flash_error(f"Error while adding group '{group_name_cn}': {str(e)}")

    elif action == 'delete':
        try:
            all_groups_data = list_all_groups(conn, domain)  # Returns list of {'cn': ..., 'dn': ...}

            group_dn_to_delete = None
            for g_data in all_groups_data:
                if g_data['cn'] == group_name_cn:
                    group_dn_to_delete = g_data['dn']
                    break

            if not group_dn_to_delete:
                flash_error(f"Group '{group_name_cn}' not found for deletion.")
                return redirect(url_for('main.groups_management'))  # Exit early if not found

            # Extract components for remove_group or simplify remove_group to take full DN
            # The remove_group function in group_modify.py already takes group_cn, domain, and group_container_ou
            # We need to parse group_dn_to_delete to get the group_container_ou part.
            object_cn_parsed, domain_str_parsed, ou_path_str_parsed = parse_distinguished_name(group_dn_to_delete)

            if not object_cn_parsed or not domain_str_parsed:  # Should not happen if DN is valid
                flash_error(f"Could not parse DN for group '{group_name_cn}' for deletion.")
                return redirect(url_for('main.groups_management'))

            # remove_group expects group_cn, domain, and group_container_ou_string
            if remove_group(conn, object_cn_parsed, domain_str_parsed, ou_path_str_parsed):
                flash(f"Group '{group_name_cn}' deleted successfully.", "success")
            else:
                flash_error(
                    f"Failed to delete group '{group_name_cn}'. LDAP Error: {conn.result.get('description', 'Unknown error')}")

        except Exception as e_delete:
            current_app.logger.error(f"Error deleting group '{group_name_cn}': {e_delete}", exc_info=True)
            flash_error(f"Error while deleting group '{group_name_cn}': {str(e_delete)}")

    else:
        flash_error("Unknown action specified.")

    return redirect(url_for('main.groups_management'))


# Helper for GET group management form
def handle_get_group_management_form(conn, domain):
    try:
        all_groups_data = list_all_groups(conn, domain)  # Returns list of {'cn': ..., 'dn': ...}
        # For this template, we just need the CNs for display in the table
        group_cns_for_display = [g_data['cn'] for g_data in all_groups_data]
        return render_template('groups_management.html', groups=group_cns_for_display)
    except Exception as e:
        current_app.logger.error(f"Error fetching groups list for management: {e}", exc_info=True)
        flash_error(f"Could not retrieve group list: {str(e)}")
        return redirect(url_for('main.index'))


@main_routes.app_errorhandler(404)
def page_not_found_error(error):
    return render_template('page_not_found.html'), 404


@main_routes.route('/settings', methods=['GET', 'POST'])
@ldap_connection_required
def settings():
    available_attrs = [
        'gidNumber', 'unixHomeDirectory', 'loginShell',
        'homeDirectory', 'homeDrive', 'mail',
        'userAccountControl', 'mSFU30Domain', 'mSFU30Name'
    ]

    if request.method == 'POST':
        user_defaults = {}
        for attr in available_attrs:
            if attr == "userAccountControl":
                flags = request.form.getlist('uac_flags')
                uac_sum = sum(int(f_val) for f_val in flags if f_val)
                user_defaults[attr] = uac_sum
            else:
                value = request.form.get(attr)
                if value:
                    user_defaults[attr] = value

        default_ou_form = request.form.get('default_ou') or "CN=Users"

        config_data_to_save = {
            "default_ou": default_ou_form,
            "attributes": user_defaults
        }
        try:
            save_user_defaults(config_data_to_save)
            flash("Settings saved successfully.", "success")
        except Exception as e:
            current_app.logger.error(f"Error saving user defaults: {e}", exc_info=True)
            flash_error(f"Failed to save settings: {str(e)}")

        return redirect(url_for('main.settings'))

    try:
        config = load_config()
        current_defaults = config.get("attributes", {})
        default_ou_config = config.get("default_ou", "CN=Users")
    except Exception as e:
        current_app.logger.error(f"Error loading user defaults for settings page: {e}", exc_info=True)
        flash_error(f"Failed to load current settings: {str(e)}")
        current_defaults = {}
        default_ou_config = "CN=Users"

    return render_template('settings.html', available=available_attrs, defaults=current_defaults,
                           default_ou=default_ou_config)


@main_routes.route('/show_all')
@ldap_connection_required
def show_all_users():
    domain = session.get('domain')
    search_base_domain = domain_to_dn(domain)  # Ensure domain_to_dn is correctly imported/available

    selected_filters = session.get('options', [])
    display_columns = session.get('columns', ["name", "distinguishedName"])

    # Attributes to fetch for each user.
    # Crucially, add 'memberOf' to get group memberships directly.
    # Also ensure 'cn' and 'name' (if different and used) are fetched for display.
    user_attributes_to_fetch = list(set(selected_filters + display_columns +
                                        ['distinguishedName', 'cn', 'name', 'memberOf']))

    try:
        # Get all users with their attributes, including 'memberOf'
        users_list = get_all_users(g.ldap_conn, search_base_domain, user_attributes_to_fetch)

        # Get all group CNs for the dropdown/checkboxes in the template
        # list_all_groups should return list of {'cn': ..., 'dn': ...}
        all_groups_data = list_all_groups(g.ldap_conn, domain)
        all_groups_cns_for_template = [g_data['cn'] for g_data in all_groups_data]

        for user_entry in users_list:
            member_of_dns_raw = user_entry.get('memberOf')  # This is from get_all_users

            member_of_cns = []
            if member_of_dns_raw:
                # Ensure member_of_dns_raw is a list of strings
                # ldap3 might return a ValuesView object or a single string if only one group
                processed_dns_list = []
                if hasattr(member_of_dns_raw, 'values') and callable(getattr(member_of_dns_raw, 'values')):
                    processed_dns_list = list(member_of_dns_raw.values)  # For ldap3 ValuesView
                elif isinstance(member_of_dns_raw, list):
                    processed_dns_list = member_of_dns_raw
                elif isinstance(member_of_dns_raw, str):
                    processed_dns_list = [member_of_dns_raw]
                else:
                    # Log unexpected type if necessary
                    pass  # Or current_app.logger.warning(f"Unexpected type for memberOf for user {user_entry.get('dn')}: {type(member_of_dns_raw)}")

                for group_dn_str in processed_dns_list:
                    # Extract CN from Group DN (e.g., "CN=GroupName,OU=Groups,DC=example,DC=com")
                    match = re.match(r"CN=([^,]+)", str(group_dn_str), re.IGNORECASE)
                    if match:
                        member_of_cns.append(match.group(1))
                    else:
                        # Fallback to full DN if CN parsing fails, or log a warning
                        # current_app.logger.warning(f"Could not parse CN from group DN '{str(group_dn_str)}' for user {user_entry.get('distinguishedName')}")
                        member_of_cns.append(str(group_dn_str))

            user_entry['memberOfList'] = sorted(list(set(member_of_cns)))  # Store unique, sorted group CNs

        return render_template('show_all_users.html',
                               users=users_list,
                               cols=display_columns,
                               groups=all_groups_cns_for_template)  # Pass group CNs for the checkboxes

    except Exception as e:
        current_app.logger.error(f"Error in show_all_users endpoint: {e}", exc_info=True)
        flash(f"An error occurred while fetching user data: {str(e)}", "danger")
        return redirect(url_for('main.index'))


@main_routes.route('/update_user_groups', methods=['POST'])
@ldap_connection_required
def update_user_groups():
    user_dn_form = request.form.get('user_dn')
    selected_groups_cns = request.form.getlist('group_list')

    domain_session = session.get('domain')

    if not user_dn_form:
        flash("User DN not provided.", "danger")
        return redirect(url_for('main.show_all_users'))

    try:
        current_user_groups_cns = get_user_groups(g.ldap_conn, user_dn_form)  # Returns list of CNs

        all_groups_data = list_all_groups(g.ldap_conn, domain_session)  # Returns list of {'cn': ..., 'dn': ...}

        # Create a mapping from CN to DN for all available groups for quick lookup
        all_groups_cn_to_dn_map = {g_data['cn']: g_data['dn'] for g_data in all_groups_data}

        selected_group_dns_to_set = []
        for cn_selected in selected_groups_cns:
            if cn_selected in all_groups_cn_to_dn_map:
                selected_group_dns_to_set.append(all_groups_cn_to_dn_map[cn_selected])
            else:
                flash(f"Warning: Group CN '{cn_selected}' selected in form but not found in directory. Skipping add.",
                      "warning")
                current_app.logger.warning(
                    f"Group CN '{cn_selected}' for user {user_dn_form} not found in all_groups_cn_to_dn_map")

        current_group_dns_user_is_member_of = []
        for cn_current in current_user_groups_cns:
            if cn_current in all_groups_cn_to_dn_map:
                current_group_dns_user_is_member_of.append(all_groups_cn_to_dn_map[cn_current])
            else:
                flash(
                    f"Warning: User is member of '{cn_current}' not found in directory. Skipping remove if unchecked.",
                    "warning")
                current_app.logger.warning(
                    f"User {user_dn_form} is member of group CN '{cn_current}' which was not found in all_groups_cn_to_dn_map. Will not attempt to remove via form if unchecked.")
                # If a user is member of a group not returned by list_all_groups,
                # it might indicate a hidden/special group or a stale membership.
                # For safety, if this group is NOT in selected_group_dns_to_set, we still want to try to remove it.
                # So we add its (potentially unresolvable via CN) DN to the list to check.
                # This makes the "remove" logic more robust.
                # If the current group cannot be found by CN, it means it's not in the map.
                # It *might* be in a default container like CN=Users, but the most robust is to add its full DN.
                # However, this current loop just adds its full DN if found in map.
                # We need the full DN of the group from get_user_groups ideally.
                # get_user_groups returns CNs only, which is why we map.
                # For now, let's keep it as is, relying on current_group_dns_user_is_member_of only containing resolvable groups.

        groups_to_add_user_to = [dn for dn in selected_group_dns_to_set if
                                 dn not in current_group_dns_user_is_member_of]
        groups_to_remove_user_from = [dn for dn in current_group_dns_user_is_member_of if
                                      dn not in selected_group_dns_to_set]

        for group_dn_to_add in groups_to_add_user_to:
            if not add_user_to_group_by_dn(g.ldap_conn, user_dn_form, group_dn_to_add):
                flash(
                    f"Failed to add user to group (DN: {group_dn_to_add}). Error: {g.ldap_conn.result.get('description', 'Unknown')}",
                    "danger")
                current_app.logger.error(f"LDAP Error adding {user_dn_form} to {group_dn_to_add}: {g.ldap_conn.result}")

        for group_dn_to_remove in groups_to_remove_user_from:
            if not remove_user_from_group_by_dn(g.ldap_conn, user_dn_form, group_dn_to_remove):
                flash(
                    f"Failed to remove user from group (DN: {group_dn_to_remove}). Error: {g.ldap_conn.result.get('description', 'Unknown')}",
                    "danger")
                current_app.logger.error(
                    f"LDAP Error removing {user_dn_form} from {group_dn_to_remove}: {g.ldap_conn.result}")

        flash("User group memberships updated successfully.", "success")
    except Exception as e:
        current_app.logger.error(f"Error updating user groups for {user_dn_form}: {e}", exc_info=True)
        flash(f"An error occurred while updating user groups: {str(e)}", "danger")

    return redirect(url_for('main.show_all_users'))