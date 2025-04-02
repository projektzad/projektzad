from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.utils import secure_filename
import sys
import os
from datetime import datetime
import re
import uuid

# Get the absolute path to the 'models' directory
models_path = os.path.join(os.path.dirname(__file__), 'models')

# Append the path to sys.path
sys.path.append(models_path)

# Import the necessary modules and functions
from app.models.batch_add import import_users_from_file
from werkzeug.utils import secure_filename
from app.models import connection as co
from app.models.block import change_users_block_status, get_blocked_users_count
from app.models.all_users import get_all_users, get_all_users_count
from app.config_utils import save_user_defaults, get_default_attributes, load_config
from app.models.block import block_multiple_users
from app.models.expire import expire_multiple_users, set_account_expiration, get_expiring_users_count
from app.models.add import create_user
from app.models.group_modify import add_user_to_group, remove_user_from_group, list_all_groups, list_group_members, \
    remove_group, add_new_group, load_json_config
from app.models.delete import *
from app.models.batch_delete_users import *

main_routes = Blueprint('main', __name__)

connection_global = None


def flash_error(message):
    flash(message, 'danger')


def domain_to_search_base(domain):
    # Split the domain string by the period (.)
    domain_parts = domain.split('.')
    # Format the parts into the LDAP search base string
    search_base = ','.join(f"dc={part}" for part in domain_parts)
    return search_base


def parse_user_data2(user_data):
    # Wydzielenie domeny (wszystkie DC=...) oraz OU=...
    domain_parts = re.findall(r"DC=[^,]+", user_data)
    ou_parts = re.findall(r"OU=[^,]+", user_data)
    cn_parts = re.findall(r"CN=[^,]+", user_data)

    # Dodanie 'Users' do ou_parts, jeśli CN=Users znajduje się w cn_parts
    if any("CN=Users" in part for part in cn_parts):
        ou_parts.insert(0, "OU=Users")  # Dodaj 'Users' na początek ou_parts

    # Join the organizational units with a slash
    ou = "/".join(part.split('=')[1] for part in reversed(ou_parts)) if ou_parts else None
    # Join the domain parts with a dot
    domain = ".".join(part.split('=')[1] for part in domain_parts) if domain_parts else None

    # Usuwamy CN=Users z cn_parts, jeżeli znajduje się w cn_parts
    cn_parts = [part for part in cn_parts if "CN=Users" not in part]  # Usuwamy CN=Users z cn_parts
    cn = ".".join(part.split('=')[1] for part in cn_parts) if cn_parts else None

    return domain, ou, cn


def parse_user_data(user_data):
    # Wydzielenie domeny (wszystkie DC=...) oraz OU=...
    domain_parts = re.findall(r"DC=[^,]+", user_data)
    ou_parts = re.findall(r"OU=[^,]+", user_data)
    cn_parts = re.findall(r"CN=[^,]+", user_data)
    # Join the domain parts with a dot
    domain = ".".join(part.split('=')[1] for part in domain_parts) if domain_parts else None

    # Join the organizational units with a dot
    ou = "/".join(part.split('=')[1] for part in reversed(ou_parts)) if ou_parts else None
    cn = ".".join(part.split('=')[1] for part in cn_parts) if cn_parts else None

    return ou, domain, cn


@main_routes.route('/search_user', methods=['POST'])
def search_user():
    user_data = request.form.get('user_data', '').strip()
    cn = user_data
    conn = get_ldap_connection()
    search_base = domain_to_search_base(domain=session.get('domain', 'default.local'))
    user_list = get_all_users(conn, search_base, session.get('options'))

    # Filter users with a matching 'cn'
    print(user_list)
    matched_users = [user for user in user_list if cn.lower() in user.get("cn", "").lower()]
    print("MatcherUsers")
    print(matched_users)
    # Render the results in a template
    return render_template('search_user.html', matched_users=matched_users)


# Decorator requiring admin privileges
def requires_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Brak uprawnień do wykonania tej akcji', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function


# Helper function to get LDAP connection
def get_ldap_connection():
    return connection_global


# Form validation
def validate_form(fields):
    return all(fields)


@main_routes.route('/')
def index():
    # Check if the user is logged in
    if 'login' not in session:
        return redirect(url_for('main.login'))

    domain = session.get('domain', 'default.local')
    search_base = domain_to_search_base(domain)
    connection = get_ldap_connection()

    # If there is no active LDAP connection, redirect to login
    if not connection:
        flash("No active LDAP connection. Please log in again.", "danger")
        return redirect(url_for('main.login'))

    try:
        # Fetch user statistics
        stats = {
            'total_users': get_all_users_count(connection, search_base),
            'blocked_users': get_blocked_users_count(connection, search_base),
            'expiring_users': get_expiring_users_count(connection, search_base)
        }

        # Retrieve the list of all users
        selected = session.get('options', [])
        columns = session.get('columns', [])
        all_columns = selected + columns

        users = get_all_users(connection, search_base, all_columns)

        # Render the index page with user data
        return render_template('index.html', login=session["login"], stats=stats, users=users, cols=columns,
                               options=selected)

    except Exception as e:
        # Handle errors and redirect to the index page with an error message
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('main.index'))


from flask import request, session, redirect, url_for, flash, render_template


@main_routes.route('/checkbox_form', methods=['GET', 'POST'])
def checkbox_form():
    options = [
        'objectClass',
        'cn',
        'sAMAccountName',
        'userPrincipalName',
        'givenName',
        'sn',
        'displayName',
        'uid',
        'uidNumber',
        'gidNumber',
        'unixHomeDirectory',
        'loginShell',
        'homeDirectory',
        'homeDrive',
        'mail',
        'whenChanged',
        'whenCreated',
        'uSNChanged',
        'uSNCreated',
        'userAccountControl',
        'sAMAccountType',
        'pwdLastSet',
        'primaryGroupID',
        'objectCategory',
        'objectGUID',
        'objectSid',
        'logonCount',
        'instanceType',
        'dSCorePropagationData',
        'countryCode',
        'codePage',
        'badPwdCount',
        'badPasswordTime',
        'accountExpires'
    ]

    if request.method == 'POST':
        selected_filters = request.form.getlist('filter_options')
        selected_columns = request.form.getlist('column_options')

        # Domyślne wartości, które zawsze powinny być wybrane
        selected_columns.extend(["name", "distinguishedName"])

        # Zapisz wybory użytkownika w sesji
        session['options'] = selected_filters
        session['columns'] = selected_columns

        flash(f'Selected columns: {", ".join(selected_columns)}', 'success')
        flash(f'Selected filters: {", ".join(selected_filters)}', 'info')

        # Pobierz poprzedni adres URL lub domyślnie przekieruj na stronę główną
        previous_url = request.form.get('previous_url', url_for('main.index'))
        return redirect(previous_url)

    # Pobieramy wcześniejsze wybory z sesji (jeśli istnieją)
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
    global connection_global  # Declare connection_global as global
    if request.method == 'POST':
        ldap_server = request.form['ldap_server']
        login = request.form['login']
        password = request.form['password']
        domain = request.form['domain']
        [is_connected, connection] = co.connect_to_active_directory(ldap_server, login, password, domain)

        if is_connected:
            session['ldap_server'] = ldap_server
            session['login'] = login
            session['domain'] = domain
            session['columns'] = ["name", "distinguishedName"]
            session['options'] = []

            connection_global = connection  # Assign to the global variable
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error="Błąd logowania. Proszę sprawdzić dane.")

    return render_template('login.html')


@main_routes.route('/logout')
def logout():
    global connection_global  # Declare connection_global as global
    if connection_global:
        co.disconnect_from_active_directory(connection_global)
        connection_global = None  # Reset the global variable

    session.pop('login', None)
    session.pop('ldap_server', None)
    session.pop('domain', None)
    return redirect(url_for('main.login'))


@main_routes.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()  # Use the global LDAP connection

    if request.method == 'POST':
        if 'selected_users' in request.form:
            return delete_user_post(connection)
        elif 'file' in request.files:
            return delete_user_file(connection)

    return delete_user_get(connection)


def delete_user_get(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))
    try:
        # Fetch user list for the form
        domain = session.get('domain', 'default.local')
        # print("Domain:", domain)
        search_base = domain_to_search_base(domain)
        # print("Search Base:", search_base)

        selected = session.get('options')
        columns = session.get('columns')
        all = selected + columns

        users = get_all_users(connection, search_base, all)

        return render_template('delete_user.html', users=users, cols=columns, options=selected)
    except Exception as e:
        flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
        return redirect(url_for('main.index'))


def delete_user_post(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    selected_users = request.form.getlist('selected_users')
    if not selected_users:
        flash_error("Nie wybrano żadnych użytkowników do usunięcia.")
        return redirect(url_for('main.delete_user'))

    errors = []
    successes = []

    for user_data in selected_users:
        try:
            username, domain = user_data.split('|')
            ou, domain, _ = parse_user_data(domain)
            if ou:
                success = delete_user_from_active_directory(connection, username, domain, ou)
            else:
                success = delete_user_from_active_directory(connection, username, domain)

            if success:
                successes.append(username)
            else:
                errors.append(username)
        except ValueError:
            errors.append(f"Nieprawidłowy format danych użytkownika: {user_data}")

    # Handle success and errors
    if successes:
        flash(f"Użytkownicy {', '.join(successes)} zostali pomyślnie usunięci.", 'success')
    if errors:
        flash_error(f"Wystąpiły błędy podczas usuwania użytkowników: {', '.join(errors)}.")

    return redirect(url_for('main.delete_user'))


def delete_user_file(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    file = request.files['file']
    if file.filename == '':
        flash_error("Nie wybrano pliku do przesłania.")
        return redirect(url_for('main.delete_user'))

    file_path = os.path.join("uploads", file.filename)
    file.save(file_path)

    try:
        if file.filename.endswith('.xlsx') or file.filename.endswith('.csv'):
            deleted_count = delete_multiple_users(connection, file_path)
        else:
            flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
            return redirect(url_for('main.delete_user'))

        flash(f"Usunięto {deleted_count} użytkowników z pliku.", 'success')
    except Exception as e:
        flash_error(f"Wystąpił błąd podczas przetwarzania pliku: {str(e)}")

    return redirect(url_for('main.delete_user'))


@main_routes.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                flash("No file selected.", "danger")
                return redirect(url_for('main.add_user'))

            ext = os.path.splitext(file.filename)[1].lower()
            unique_name = f"import_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join('app/static', unique_name)
            file.save(filepath)

            preview_data = []
            try:
                if ext == ".csv":
                    with open(filepath, newline='', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            preview_data.append(row)
                elif ext in [".xlsx", ".xls"]:
                    wb = openpyxl.load_workbook(filepath)
                    sheet = wb.active
                    headers = [cell.value for cell in sheet[1]]
                    for row in sheet.iter_rows(min_row=2, values_only=True):
                        row_data = dict(zip(headers, row))
                        preview_data.append(row_data)
                else:
                    flash("Unsupported file format.", "danger")
                    return redirect(url_for('main.add_user'))

                session['import_file'] = filepath
                return render_template("preview_import.html", users=preview_data)

            except Exception as e:
                flash(f"Error processing file: {str(e)}", "danger")
                return redirect(url_for('main.add_user'))

        if 'confirm_import' in request.form:
            filepath = session.get('import_file')
            if not filepath or not os.path.exists(filepath):
                flash("No file to import.", "danger")
                return redirect(url_for('main.add_user'))

            domain = session.get('domain')
            dc = ','.join([f"DC={x}" for x in domain.split('.')])
            search_base = dc
            connection = get_ldap_connection()
            result = import_users_from_file(connection, filepath, dc, search_base)
            if 'error' in result:
                flash(result['error'], 'danger')
            else:
                flash(f"✅ Added: {result['added']}, ❌ Failed: {result['failed']}", 'info')
                if result['errors']:
                    flash("Errors:\n" + "\n".join(result['errors']), 'warning')

            os.remove(filepath)
            session.pop('import_file', None)

            return redirect(url_for('main.add_user'))

        # Jeśli zwykły formularz z dodawaniem 1 użytkownika
        return add_user_post()

    return add_user_get()


def add_user_get():
    return render_template('add_user.html')


def add_user_post():
    username = request.form.get('username')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')

    # Walidacja danych
    if not validate_form([username, first_name, last_name, password]):
        flash_error("All fields are required.")
        return render_template('add_user.html')

    # Połączenie z LDAP
    connection = get_ldap_connection()
    if not connection:
        flash_error("No connection to Active Directory.")
        return redirect(url_for('main.login'))

    try:
        # Get DC and search_base from domain
        domain = session.get('domain')  # e.g. "testad.local"
        dc = ','.join([f"DC={part}" for part in domain.split('.')])
        search_base = dc

        # Call create_user
        success = create_user(connection, username, first_name, last_name, password, dc, search_base, search_base)

        if success:
            flash(f"User {username} created successfully.", "success")
        else:
            flash_error(f"Failed to create user {username}.")
    except Exception as e:
        flash_error(f"An error occurred: {str(e)}")
        return redirect(url_for('main.index'))

    return redirect(url_for('main.index'))


@main_routes.route('/toggle_block_user', methods=['GET', 'POST'])
def toggle_block_user():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()

    if request.method == 'POST':
        if 'selected_users' in request.form:
            return toggle_block_user_post(connection)
        elif 'file' in request.files:
            return toggle_block_user_file(connection)

    return toggle_block_user_get(connection)


def toggle_block_user_get(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    try:
        domain = session.get('domain', 'default.local')
        search_base = domain_to_search_base(domain)
        selected = session.get('options')
        columns = session.get('columns')
        all = selected + columns

        users = get_all_users(connection, search_base, all)

        return render_template('block_user.html', users=users, cols=columns, options=selected)
    except Exception as e:
        flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
        return redirect(url_for('main.index'))


def toggle_block_user_post(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    selected_users = request.form.getlist('selected_users')
    if not selected_users:
        flash_error("Nie wybrano żadnych użytkowników.")
        return redirect(url_for('main.toggle_block_user'))

    errors = []
    successes = []

    for user_data in selected_users:
        try:
            username, domain = user_data.split('|')
            ou, domain, cn = parse_user_data(domain)

            if ou:
                success = change_users_block_status(connection, username, domain, ou)
            else:
                success = change_users_block_status(connection, username, domain)

            if success:
                successes.append(username)
            else:
                errors.append(username)
        except ValueError:
            errors.append(f"Nieprawidłowy format danych użytkownika: {user_data}")

    # Komunikaty o sukcesie i błędach
    if successes:
        flash(f"Status blokady użytkowników {', '.join(successes)} został zmieniony.", "success")
    if errors:
        flash_error(f"Wystąpiły błędy podczas zmiany statusu blokady: {', '.join(errors)}.")

    return redirect(url_for('main.toggle_block_user'))


def toggle_block_user_file(connection):
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    file = request.files['file']
    if file.filename == '':
        flash_error("Nie wybrano pliku do przesłania.")
        return redirect(url_for('main.toggle_block_user'))

    file_path = os.path.join("uploads", secure_filename(file.filename))
    file.save(file_path)

    try:
        if file.filename.endswith('.xlsx') or file.filename.endswith('.csv'):
            blocked_count = block_multiple_users(connection, file_path)
        else:
            flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
            return redirect(url_for('main.toggle_block_user'))

        if blocked_count:
            flash(f"{blocked_count} użytkowników zostało pomyślnie zablokowanych/odblokowanych z pliku.", 'success')
        else:
            flash_error("Wystąpił błąd podczas przetwarzania pliku.")
    except Exception as e:
        flash_error(f"Nie udało się przetworzyć pliku: {str(e)}")

    return redirect(url_for('main.toggle_block_user'))


@main_routes.route('/expire_user', methods=['GET', 'POST'])
def expire_user():
    # Check if the user is logged in
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()  # Get the LDAP connection
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        return handle_post_request(connection)
    elif request.method == 'GET':
        return handle_get_request(connection)


def handle_post_request(connection):
    """Handle POST requests for expiring users."""
    # Handle form submissions
    if request.form.getlist('selected_users'):
        return handle_selected_users(connection)

    # Handle file upload
    if 'file' in request.files:
        return handle_file_upload(connection)

    return redirect(url_for('main.expire_user'))  # Redirect after processing POST


def handle_selected_users(connection):
    """Process the form for selected users."""
    selected_users = request.form.getlist('selected_users')
    errors = []
    successes = []

    for user_data in selected_users:
        try:
            username, domain = user_data.split('|')
            ou, domain, cn = parse_user_data(domain)
            expiration_date = request.form.get('expiration_date')
            formatted_date = datetime.strptime(expiration_date, '%Y-%m-%d').strftime('%d-%m-%Y')
            print(expiration_date)

            # Set account expiration
            if ou:
                success = set_account_expiration(connection, username, domain, formatted_date, ou)
            else:
                success = set_account_expiration(connection, username, domain, formatted_date)

            if success:
                successes.append(username)
            else:
                errors.append(username)
        except ValueError:
            errors.append(f"Nieprawidłowy format danych użytkownika!!: {user_data}")

    # Flash success and error messages
    if successes:
        flash(f"Status expire użytkowników {', '.join(successes)} został zmieniony.", "success")
    if errors:
        flash_error(f"Wystąpiły błędy podczas zmiany statusu expire użytkowników: {', '.join(errors)}.")

    return redirect(url_for('main.expire_user'))


def handle_file_upload(connection):
    """Handle file upload for expiring multiple users."""
    file = request.files['file']
    if file.filename == '':
        flash_error("Nie wybrano pliku do przesłania.")
        return redirect(url_for('main.expire_user'))

    # Save the file to a temporary location
    file_path = os.path.join("uploads", secure_filename(file.filename))
    file.save(file_path)

    # Process file based on type (Excel or CSV)
    try:
        if file.filename.endswith('.xlsx') or file.filename.endswith('.csv'):
            blocked_count = expire_multiple_users(connection, file_path)
        else:
            flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
            return redirect(url_for('main.expire_user'))

        if blocked_count:
            flash(f"{blocked_count} użytkowników zostało pomyślnie zablokowanych/odblokowanych z pliku.", 'success')
        else:
            flash_error("Wystąpił błąd podczas przetwarzania pliku.")

    except Exception as e:
        flash_error(f"Nie udało się przetworzyć pliku: {str(e)}")

    return redirect(url_for('main.expire_user'))


def handle_get_request(connection):
    """Handle GET requests for displaying the expire user form."""
    try:
        # Fetch user list for the form
        domain = session.get('domain', 'testad.local')
        search_base = domain_to_search_base(domain)

        selected = session.get('options')
        columns = session.get('columns')
        all = selected + columns

        users = get_all_users(connection, search_base, all)

        return render_template('expire_user.html', users=users, cols=columns, options=selected)
    except Exception as e:
        flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
        return redirect(url_for('main.index'))


@main_routes.route('/modify_group_members', methods=['GET', 'POST'])
def modify_group_members():
    """Main route to modify group members."""
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        return handle_post_group_modification(connection)
    elif request.method == 'GET':
        return handle_get_group_modification(connection)


def handle_post_group_modification(connection):
    """Handle POST request for modifying group members."""
    group_name = request.form.get('group_name')
    add_users = request.form.getlist('add_users')
    remove_users = request.form.getlist('remove_users')

    print(add_users)

    domain = session.get('domain', 'company.com')
    groups, oulist = list_all_groups(connection, domain)
    group_ou = get_group_ou(group_name, groups, oulist)

    errors, successes = [], []

    # Process adding users
    process_user_addition(connection, add_users, domain, group_name, group_ou, successes, errors)

    # Process removing users
    process_user_removal(connection, remove_users, domain, group_name, group_ou, successes, errors)

    # Display results
    display_results(successes, errors)
    return redirect(url_for('main.modify_group_members'))


def get_group_ou(group_name, groups, oulist):
    """Get the corresponding OU for the selected group."""
    if group_name in groups:
        return oulist[groups.index(group_name)]
    return None


def process_user_addition(connection, add_users, domain, group_name, group_ou, successes, errors):
    """Process adding users to a group."""
    for username in add_users:
        try:
            if username:
                # print(username)
                _, users_ou, cn = parse_user_data2(username)
                group_ou_parsed, _, _ = parse_user_data(group_ou)
                # print(cn, domain, users_ou, group_name, domain, group_ou)
                if group_ou_parsed:
                    success = add_user_to_group(connection, cn, domain, users_ou, group_name, domain, group_ou_parsed)
                else:
                    success = add_user_to_group(connection, cn, domain, users_ou, group_name, domain, group_ou)
                if success:
                    successes.append(username)
                else:
                    errors.append(username)
        except Exception as e:
            errors.append(f"Nie udało się dodać użytkownika {username}: {str(e)}")


def process_user_removal(connection, remove_users, domain, group_name, group_ou, successes, errors):
    """Process removing users from a group."""
    for username in remove_users:
        try:
            if username:
                _, users_ou, cn = parse_user_data2(username)
                group_ou_parsed, _, _ = parse_user_data(group_ou)
                if group_ou_parsed:
                    success = remove_user_from_group(connection, cn, domain, users_ou, group_name, domain,
                                                     group_ou_parsed)
                else:
                    success = remove_user_from_group(connection, cn, domain, users_ou, group_name, domain, group_ou)

                if success:
                    successes.append(username)
                else:
                    errors.append(username)
        except Exception as e:
            errors.append(f"Nie udało się usunąć użytkownika {username}: {str(e)}")


def display_results(successes, errors):
    """Display flash messages for successes and errors."""
    if successes:
        flash(f"Zmodyfikowano członków grupy: {', '.join(successes)}.", "success")
    if errors:
        flash_error(f"Wystąpiły błędy podczas modyfikacji członków grupy: {', '.join(errors)}.")


def handle_get_group_modification(connection):
    """Handle GET request for displaying group modification form."""
    try:
        domain = session.get('domain', 'company.com')
        groups, _ = list_all_groups(connection, domain)
        selected_group = request.args.get('group_name')
        members = list_group_members(connection, domain, selected_group) if selected_group else []

        selected = session.get('options')
        columns = session.get('columns')
        all = selected + columns

        users = get_all_users(connection, domain_to_search_base(domain), all)

        return render_template(
            'modify_group_members.html',
            groups=groups,
            members=members,
            selected_group=selected_group,
            cols=columns,
            users=users,
            options=session.get('options')
        )
    except Exception as e:
        flash_error(f"Nie można pobrać listy grup: {str(e)}")
        return redirect(url_for('main.index'))


@main_routes.route('/groups_management', methods=['GET', 'POST'])
def groups_management():
    """Main route for group management."""
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.index'))

    domain = session.get('domain', 'company.com')

    if request.method == 'POST':
        return handle_post_group_management(connection, domain)
    else:
        return handle_get_group_management(connection, domain)


def handle_post_group_management(connection, domain):
    """Handle POST requests for group management."""
    action = request.form.get('action')
    group_name = request.form.get('group_name')

    if not group_name:
        flash_error("Group name cannot be empty.")
        return redirect(url_for('main.groups_management'))

    if action == 'add':
        return add_group(connection, group_name)
    elif action == 'delete':
        return delete_group(connection, domain, group_name)

    flash_error("Nieznana akcja.")
    return redirect(url_for('main.groups_management'))


def add_group(connection, group_name):
    """Handle adding a new group."""
    try:
        config_path = os.path.abspath('./app/templates/group-config.json')
        config = load_json_config(config_path)

        success = add_new_group(connection, config)
        if success:
            flash(f"Group '{group_name}' added successfully.", "success")
        else:
            flash_error(f"Failed to add group '{group_name}'. Check the logs for more details.")
    except FileNotFoundError:
        flash_error(f"Configuration file not found at '{config_path}'.")
    except KeyError as ke:
        flash_error(f"Configuration is missing a required field: {str(ke)}")
    except Exception as e:
        flash_error(f"Error while adding group '{group_name}': {str(e)}")

    return redirect(url_for('main.groups_management'))


def delete_group(connection, domain, group_name):
    """Handle deleting a group."""
    try:
        groups, oulist = list_all_groups(connection, domain)
        group_ou = oulist[groups.index(group_name)] if group_name in groups else None

        if not group_ou:
            flash_error(f"Group '{group_name}' not found.")
            return redirect(url_for('main.groups_management'))

        _, group_ou, _ = parse_user_data2(group_ou)

        success = remove_group(connection, group_name, domain, group_ou)
        if success:
            flash(f"Group '{group_name}' deleted successfully.", "success")
        else:
            flash_error(f"Failed to delete group '{group_name}'.")
    except ValueError:
        flash_error(f"Group '{group_name}' not found in the domain.")
    except Exception as e:
        flash_error(f"Error while deleting group '{group_name}': {str(e)}")

    return redirect(url_for('main.groups_management'))


def handle_get_group_management(connection, domain):
    """Handle GET request for displaying groups list."""
    try:
        groups, _ = list_all_groups(connection, domain)
        return render_template('groups_management.html', groups=groups)
    except Exception as e:
        flash_error(f"Nie można pobrać listy grup: {str(e)}")
        return redirect(url_for('main.index'))


@main_routes.app_errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404


@main_routes.route('/settings', methods=['GET', 'POST'])
def settings():
    available_attrs = [
        'gidNumber', 'unixHomeDirectory', 'loginShell',
        'homeDirectory', 'homeDrive', 'mail',
        'userAccountControl', 'mSFU30Domain', 'mSFU30Name'
    ]

    if request.method == 'POST':
        user_defaults = {}
        for attr in available_attrs:
            value = request.form.get(attr)
            if attr == "userAccountControl":
                flags = request.form.getlist('uac_flags')
                uac_sum = sum(int(f) for f in flags)
                user_defaults[attr] = uac_sum
            else:
                value = request.form.get(attr)
                if value:
                    user_defaults[attr] = value

        default_ou = request.form.get('default_ou') or "CN=Users"

        # ⬇️ WAŻNE: pakujemy do dicta z kluczami "attributes" i "default_ou"
        config_data = {
            "default_ou": default_ou,
            "attributes": user_defaults
        }

        save_user_defaults(config_data)
        flash("Settings saved successfully.", "success")
        return redirect(url_for('main.settings'))

    config = load_config()
    current_defaults = config.get("attributes", {})
    default_ou = config.get("default_ou", "CN=Users")

    return render_template('settings.html', available=available_attrs, defaults=current_defaults, default_ou=default_ou)


