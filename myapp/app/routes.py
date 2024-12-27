from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.utils import secure_filename
import sys
import os


# Get the absolute path to the 'models' directory
models_path = os.path.join(os.path.dirname(__file__), 'models')

# Append the path to sys.path
sys.path.append(models_path)

# Import the necessary modules and functions
from app.models import connection as co
from app.models.block import change_users_block_status
from app.models.delete import delete_user_from_active_directory
from app.models.group_modify import modify_members, get_list
from app.models.all_users import get_all_users
from app.models.batch_delete_users import delete_multiple_users
from app.models.block import block_multiple_users
from app.models.expire import expire_multiple_users,set_account_expiration
from app.models.add import create_user
main_routes = Blueprint('main', __name__)

connection_global = None

def domain_to_search_base(domain):
    # Split the domain string by the period (.)
    domain_parts = domain.split('.')
    # Format the parts into the LDAP search base string
    search_base = ','.join(f"dc={part}" for part in domain_parts)
    return search_base


import re
def parse_user_data(user_data):
    # Wydzielenie domeny (wszystkie DC=...) oraz OU=...
    domain_parts = re.findall(r"DC=[^,]+", user_data)
    ou_parts = re.findall(r"OU=[^,]+", user_data)
    cn_parts =  re.findall(r"CN=[^,]+", user_data)
    # Join the domain parts with a dot
    domain = ".".join(part.split('=')[1] for part in domain_parts) if domain_parts else None
    
    # Join the organizational units with a dot
    ou = "/".join(part.split('=')[1] for part in reversed(ou_parts)) if ou_parts else None
    cn = ".".join(part.split('=')[1] for part in cn_parts) if cn_parts else None

    return ou, domain, cn

# Decorator requiring admin privileges
def requires_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Brak uprawnień do wykonania tej akcji', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to manage errors
def flash_error(message):
    flash(message, 'danger')

# Helper function to get LDAP connection
def get_ldap_connection():
    return connection_global

# Form validation
def validate_form(fields):
    return all(fields)

@main_routes.route('/')
def index():
    if 'login' in session:
        return render_template('index.html', login=session["login"])
    return redirect(url_for('main.login'))

@main_routes.route('/checkbox_form', methods=['GET', 'POST'])
def checkbox_form():
    options = [
    'whenChanged',
    'whenCreated',
    'uSNChanged',
    'uSNCreated',
    'userPrincipalName',
    'userAccountControl',
    'sAMAccountType',
    'pwdLastSet',
    'primaryGroupID',
    'objectCategory',
    'objectClass',
    'objectGUID',
    'objectSid',
    'cn',
    'logonCount',
    'instanceType',
    'givenName',
    'dSCorePropagationData',
    'displayName',
    'countryCode',
    'codePage',
    'sn',
    'badPwdCount',
    'badPasswordTime',
    'accountExpires'
] 
  # All options
    if request.method == 'POST':
        selected = request.form.getlist('selected_options')
        selected.append("name")
        selected.append("distinguishedName")
        flash(f'You selected: {", ".join(selected)}', 'success')
        # Save selected options in session
        session['options'] = selected
        return redirect(url_for('main.checkbox_form'))
    else:
        # Retrieve selected options from session if available
        preselected_options = session.get('options',  ['name', 'distinguishedName'])
    return render_template('checkbox.html', options=options, preselected_options=preselected_options)

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    global connection_global  # Declare connection_global as global
    if request.method == 'POST':
        ldap_server = request.form['ldap_server']
        login = request.form['login']
        password = request.form['password']
        domain = request.form['domain']
        [is_connected, connection] = co.connect_to_active_directory(ldap_server, login, password, domain)
        #print("Czy połaczaony:" , is_connected)
        if is_connected:
            session['ldap_server'] = ldap_server
            session['login'] = login
            session['domain'] = domain
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
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))

        if 'selected_users' in request.form:  # For selected users (checkbox method)
            selected_users = request.form.getlist('selected_users')
            if not selected_users:
                flash_error("Nie wybrano żadnych użytkowników do usunięcia.")
                return redirect(url_for('main.delete_user'))  # Redirect back to the same page

            errors = []
            successes = []
            for user_data in selected_users:
                try:
                    username, domain = user_data.split('|')
                    ou, domain, cn = parse_user_data(domain)
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

        elif 'file' in request.files:  # Handle file upload
            file = request.files['file']
            if file.filename == '':
                flash_error("Nie wybrano pliku do przesłania.")
                return redirect(url_for('main.delete_user'))

            file_path = os.path.join("uploads", file.filename)
            file.save(file_path)

            # Process file based on type (Excel or CSV)
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

        return redirect(url_for('main.delete_user'))  # Always return a redirect after POST

    elif request.method == 'GET':
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))

        try:
            # Fetch user list for the form
            domain = session.get('domain', 'default.local')
            print("Domain:", domain)
            search_base = domain_to_search_base(domain)
            print("Search Base:", search_base)
            #search_base = "dc=testad,dc=local"
            selected = session.get('options')
            if selected:
                users = get_all_users(connection, search_base,selected)
                print(users)
            else:
                users = get_all_users(connection, search_base)
            print(users)
            print(session.get('options'))
            return render_template('delete_user.html', users=users, options=session.get('options'))
        except Exception as e:
            
            flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
            return redirect(url_for('main.index'))


@main_routes.route('/add_user', methods=['GET', 'POST'])
#@requires_admin
def add_user():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        ou = request.form.get('ou')

        if not validate_form([username, first_name, last_name, password, ou]):
            flash_error("Wszystkie pola są wymagane.")
            return render_template('add_user.html')

        connection = get_ldap_connection()
        if not connection:
            return redirect(url_for('main.login'))

        try:
            print(domain_to_search_base(session.get('domain')))
            success = create_user(connection, username, first_name, last_name, password, ou, domain_to_search_base(session.get('domain')))
            if success:
                flash(f"Użytkownik {username} został pomyślnie dodany.", "success")
            else:
                flash_error(f"Nie udało się dodać użytkownika {username}.")
        except Exception as e:
            flash_error(f"Wystąpił błąd: {str(e)}")
            return redirect(url_for('main.index'))

        return redirect(url_for('main.index'))

    return render_template('add_user.html')


@main_routes.route('/toggle_block_user', methods=['GET', 'POST'])
def toggle_block_user():
    # Check if the user is logged in
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()  # Get the LDAP connection

    # If the request is POST, process the form
    if request.method == 'POST':
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))

        # Handle the form for selected users
        selected_users = request.form.getlist('selected_users')  # List of selected users
        if selected_users:
            errors = []
            successes = []
            for user_data in selected_users:
                try:
                    username, domain = user_data.split('|')
                    ou, domain,cn = parse_user_data(domain)
                    print(ou)
                    if ou:
                        success = change_users_block_status(connection, username, domain, ou)
                    else:
                        # Jeśli OU jest puste, przekazujemy tylko username i domain
                        success = change_users_block_status(connection, username, domain)
                    if success:
                        successes.append(username)
                    else:
                        errors.append(username)
                except ValueError:
                    errors.append(f"Nieprawidłowy format danych użytkownika: {user_data}")

            # Handle success and errors
            if successes:
                flash(f"Status blokady użytkowników {', '.join(successes)} został zmieniony.", "success")
            if errors:
                flash_error(f"Wystąpiły błędy podczas zmiany statusu blokady użytkowników: {', '.join(errors)}.")
        
        # Handle the file upload section
        if 'file' in request.files:  # Handle file upload
            file = request.files['file']
            if file.filename == '':
                flash_error("Nie wybrano pliku do przesłania.")
                return redirect(url_for('main.toggle_block_user'))
            
            # Save the file to a temporary location
            file_path = os.path.join("uploads", secure_filename(file.filename))
            file.save(file_path)

            # Process file based on type (Excel or CSV)
            try:
                if (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')) :
                    blocked_count = block_multiple_users(connection,file_path)
                else:
                    flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
                    return redirect(url_for('main.toggle_block_user'))
                
                if blocked_count:
                    flash(f"{blocked_count} użytkowników zostało pomyślnie zablokowanych/odblokowanych z pliku.", 'success')
                else:
                    flash_error("Wystąpił błąd podczas przetwarzania pliku.")

            except Exception as e:
                flash_error(f"Nie udało się przetworzyć pliku: {str(e)}")

        return redirect(url_for('main.toggle_block_user'))  # Always return a redirect after POST

    # If the request is GET, show the block user form
    elif request.method == 'GET':
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))
        try:
            # Fetch user list for the form
            domain = session.get('domain', 'default.local')
            search_base = domain_to_search_base(domain)
            selected = session.get('options')
            if selected:
                users = get_all_users(connection, search_base,selected)
            else:
                users = get_all_users(connection, search_base)
            print(users)
            return render_template('block_user.html', users=users,options=session.get('options'))
        except Exception as e:
            
            flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
            return redirect(url_for('main.index'))


@main_routes.route('/expire_user', methods=['GET', 'POST'])
def expire_user():
    # Check if the user is logged in
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()  # Get the LDAP connection

    # If the request is POST, process the form
    if request.method == 'POST':
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))

        # Handle the form for selected users
        selected_users = request.form.getlist('selected_users')  # List of selected users
        if selected_users:
            errors = []
            successes = []
            for user_data in selected_users:
                try:
                    username, domain = user_data.split('|')
                    ou, domain,cn = parse_user_data(domain)
                    expiration_date = request.form('expiration_date')
                    #print(ou)
                    if ou:
                        success = set_account_expiration(connection, username, domain,expiration_date,ou)
                    else:
                        # Jeśli OU jest puste, przekazujemy tylko username i domain
                        success = set_account_expiration(connection, username, domain,expiration_date)
                    if success:
                        successes.append(username)
                    else:
                        errors.append(username)
                except ValueError:
                    errors.append(f"Nieprawidłowy format danych użytkownika: {user_data}")

            # Handle success and errors
            if successes:
                flash(f"Status expire użytkowników {', '.join(successes)} został zmieniony.", "success")
            if errors:
                flash_error(f"Wystąpiły błędy podczas zmiany statusu expire użytkowników: {', '.join(errors)}.")
        
        # Handle the file upload section
        if 'file' in request.files:  # Handle file upload
            file = request.files['file']
            if file.filename == '':
                flash_error("Nie wybrano pliku do przesłania.")
                return redirect(url_for('main.expire_user'))
            
            # Save the file to a temporary location
            file_path = os.path.join("uploads", secure_filename(file.filename))
            file.save(file_path)

            # Process file based on type (Excel or CSV)
            try:
                if (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')) :
                    blocked_count = expire_multiple_users(connection,file_path)
                else:
                    flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
                    return redirect(url_for('main.toggle_expire'))
                
                if blocked_count:
                    flash(f"{blocked_count} użytkowników zostało pomyślnie zablokowanych/odblokowanych z pliku.", 'success')
                else:
                    flash_error("Wystąpił błąd podczas przetwarzania pliku.")

            except Exception as e:
                flash_error(f"Nie udało się przetworzyć pliku: {str(e)}")

        return redirect(url_for('main.expire_user'))  # Always return a redirect after POST

    # If the request is GET, show the block user form
    elif request.method == 'GET':
        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.login'))

        try:
            # Fetch user list for the form
            #search_base = "dc=testad,dc=local"
            domain = session.get('domain', 'testad.local')
            search_base = domain_to_search_base(domain)
            selected = session.get('options')
            if selected:
                users = get_all_users(connection, search_base,selected)
            else:
                users = get_all_users(connection, search_base)
            return render_template('expire_user.html', users=users,options=session.get('options'))
        except Exception as e:
            flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
            return redirect(url_for('main.index'))


@main_routes.route('/modify_group_members', methods=['GET', 'POST'])
def modify_group_members():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        group_dn = request.form['group_dn']
        add_users = request.form.get('add_users', '')
        remove_users = request.form.get('remove_users', '')

        connection = get_ldap_connection()
        if connection:
            base_dn = 'ou=users,o=company'
            add_list = get_list(base_dn, add_users)
            remove_list = get_list(base_dn, remove_users)

            try:
                success = modify_members(group_dn, connection, addList=add_list, deleteList=remove_list)
                if success:
                    flash('Członkowie grupy zostali pomyślnie zmodyfikowani.', 'success')
                else:
                    flash_error('Wystąpił błąd podczas modyfikacji członków grupy.')
            except Exception as e:
                flash_error(f"Wystąpił błąd: {str(e)}")
        else:
            flash_error('Brak połączenia z Active Directory.')

        return redirect(url_for('main.index'))

    return render_template('modify_group_members.html')

@main_routes.app_errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404
