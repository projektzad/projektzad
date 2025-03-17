from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.utils import secure_filename
import sys
import os
from datetime import datetime


# Get the absolute path to the 'models' directory
models_path = os.path.join(os.path.dirname(__file__), 'models')

# Append the path to sys.path
sys.path.append(models_path)

# Import the necessary modules and functions
from app.models import connection as co
from app.models.block import change_users_block_status,get_blocked_users_count
from app.models.delete import delete_user_from_active_directory
from app.models.all_users import get_all_users,get_all_users_count
from app.models.batch_delete_users import delete_multiple_users
from app.models.block import block_multiple_users
from app.models.expire import expire_multiple_users,set_account_expiration,get_expiring_users_count
from app.models.add import create_user
from app.models.group_modify import add_user_to_group, remove_user_from_group,list_all_groups,list_group_members, remove_group, add_new_group, load_json_config
main_routes = Blueprint('main', __name__)

connection_global = None

def domain_to_search_base(domain):
    # Split the domain string by the period (.)
    domain_parts = domain.split('.')
    # Format the parts into the LDAP search base string
    search_base = ','.join(f"dc={part}" for part in domain_parts)
    return search_base


import re

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
    cn_parts =  re.findall(r"CN=[^,]+", user_data)
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
    user_list = get_all_users(conn, search_base)

    # Filter users with a matching 'cn'
    print(user_list)
    matched_users = [user for user in user_list if cn.lower() in user.get("cn", "").lower()]

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
        domain = session.get('domain', 'default.local')
        search_base = domain_to_search_base(domain)
        connection = get_ldap_connection()
        if not connection:
            flash("Brak aktywnego połączenia z LDAP. Zaloguj się ponownie.", "danger")
            return redirect(url_for('main.login'))
        try:
            stats = {
                'total_users': get_all_users_count(connection, search_base),
                'blocked_users': get_blocked_users_count(connection, search_base),
                'expiring_users': get_expiring_users_count(connection, search_base)
            }
            return render_template('index.html', login=session["login"], stats=stats)
        except Exception as e:
            flash(f"Wystąpił błąd: {str(e)}", "danger")
            return redirect(url_for('main.index'))
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


# @main_routes.route('/delete_user', methods=['GET', 'POST'])
# def delete_user():
#     if 'login' not in session:
#         return redirect(url_for('main.login'))
#     connection = get_ldap_connection()  # Use the global LDAP connection
    
#     if request.method == 'POST':
#         if not connection:
#             flash_error("Brak połączenia z Active Directory.")
#             return redirect(url_for('main.login'))

#         if 'selected_users' in request.form:  # For selected users (checkbox method)
#             selected_users = request.form.getlist('selected_users')
#             if not selected_users:
#                 flash_error("Nie wybrano żadnych użytkowników do usunięcia.")
#                 return redirect(url_for('main.delete_user'))  # Redirect back to the same page

#             errors = []
#             successes = []
#             for user_data in selected_users:
#                 #print("USER DATA FROM DELETE:",user_data)
#                 try:
#                     username, domain = user_data.split('|')
#                     ou, domain, cn = parse_user_data(domain)
#                     if ou:
#                         success = delete_user_from_active_directory(connection, username, domain, ou)
#                     else:
#                         success = delete_user_from_active_directory(connection, username, domain)

#                     if success:
#                         successes.append(username)
#                     else:
#                         errors.append(username)
#                 except ValueError:
#                     errors.append(f"Nieprawidłowy format danych użytkownika: {user_data}")

#             # Handle success and errors
#             if successes:
#                 flash(f"Użytkownicy {', '.join(successes)} zostali pomyślnie usunięci.", 'success')
#             if errors:
#                 flash_error(f"Wystąpiły błędy podczas usuwania użytkowników: {', '.join(errors)}.")

#         elif 'file' in request.files:  # Handle file upload
#             file = request.files['file']
#             if file.filename == '':
#                 flash_error("Nie wybrano pliku do przesłania.")
#                 return redirect(url_for('main.delete_user'))

#             file_path = os.path.join("uploads", file.filename)
#             file.save(file_path)

#             # Process file based on type (Excel or CSV)
#             try:
#                 if file.filename.endswith('.xlsx') or file.filename.endswith('.csv'):
#                     deleted_count = delete_multiple_users(connection, file_path)
#                 else:
#                     flash_error("Tylko pliki Excel (.xlsx) i CSV są obsługiwane.")
#                     return redirect(url_for('main.delete_user'))

#                 flash(f"Usunięto {deleted_count} użytkowników z pliku.", 'success')
#             except Exception as e:
#                 flash_error(f"Wystąpił błąd podczas przetwarzania pliku: {str(e)}")

#             return redirect(url_for('main.delete_user'))

#         return redirect(url_for('main.delete_user'))  # Always return a redirect after POST

#     elif request.method == 'GET':
#         if not connection:
#             flash_error("Brak połączenia z Active Directory.")
#             return redirect(url_for('main.login'))

#         try:
#             # Fetch user list for the form
#             domain = session.get('domain', 'default.local')
#             print("Domain:", domain)
#             search_base = domain_to_search_base(domain)
#             print("Search Base:", search_base)
#             #search_base = "dc=testad,dc=local"
#             selected = session.get('options')
#             if selected:
#                 users = get_all_users(connection, search_base,selected)
#                 print(users)
#             else:
#                 users = get_all_users(connection, search_base)
#             print(users)
#             print(session.get('options'))
#             return render_template('delete_user.html', users=users, options=session.get('options'))
#         except Exception as e:
            
#             flash_error(f"Nie można pobrać listy użytkowników: {str(e)}")
#             return redirect(url_for('main.index'))

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
        #print("Domain:", domain)
        search_base = domain_to_search_base(domain)
        #print("Search Base:", search_base)
        
        selected = session.get('options')
        if selected:
            users = get_all_users(connection, search_base, selected)
        else:
            users = get_all_users(connection, search_base)
        
        print(users)
        return render_template('delete_user.html', users=users, options=selected)
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
                    
                    ou, domain, cn = parse_user_data(domain)
           
                 
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
                users = get_all_users(connection, search_base, selected)
            else:
                users = get_all_users(connection, search_base)
            
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
        # Handle the form for selected users
        selected_users = request.form.getlist('selected_users') 
        if selected_users:
            errors = []
            successes = []
            for user_data in selected_users:
                try:
                    username, domain = user_data.split('|')
                    ou, domain, cn = parse_user_data(domain)
                    expiration_date = request.form.get('expiration_date')
                    formatted_date = datetime.strptime(expiration_date, '%Y-%m-%d').strftime('%d-%m-%Y')
                    print(expiration_date)
                    if ou:
                        success = set_account_expiration(connection, username, domain,formatted_date,ou)
                    else:
                        success = set_account_expiration(connection, username, domain, formatted_date)
                    if success:
                        successes.append(username)
                    else:
                        errors.append(username)
                except ValueError:
                    errors.append(f"Nieprawidłowy format danych użytkownika!!: {user_data}")

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

    connection = get_ldap_connection()  # Get the LDAP connection

    if request.method == 'POST':
        # Retrieve form data
        group_name = request.form.get('group_name')
        add_users = request.form.getlist('add_users')
        remove_users = request.form.getlist('remove_users')

        if not connection:
            flash_error("Brak połączenia z Active Directory.")
            return redirect(url_for('main.modify_group_members'))

        errors = []  # Track failed operations
        successes = []  # Track successful operations

        # Fetch the groups and corresponding OUs
        domain = session.get('domain', 'company.com')
        groups, oulist = list_all_groups(connection, domain)

        # Map the selected group name to its corresponding OU
        group_ou = None
        if group_name in groups:
            group_ou = oulist[groups.index(group_name)]  # Get the corresponding OU

        domain2, group_ou, group_cn = parse_user_data2(group_ou)
        # Add users to the group
        for username in add_users:
            try:
                if username: 
                    domain2, users_ou, cn = parse_user_data2(username)
                    print(cn, domain, users_ou, group_name, domain, domain)
                    success = add_user_to_group(connection,cn, domain, users_ou, group_name, domain, group_ou)
                    
                    if success:
                        successes.append(username)
                    else:
                        errors.append(username)
            except Exception as e:
                errors.append(f"Nie udało się dodać użytkownika {username}: {str(e)}")

        # Remove users from the group
        for username in remove_users:
            try:
                if username:  # Skip empty inputs
                    # Parse user data for domain and OU
                    domain2, users_ou, cn = parse_user_data2(username)
                    print(cn, users_ou, group_name, domain)
                    success = remove_user_from_group(connection,cn, domain, users_ou, group_name, domain, group_ou)
                    if success:
                        successes.append(username)
                    else:
                        errors.append(username)
            except Exception as e:
                errors.append(f"Nie udało się usunąć użytkownika {username}: {str(e)}")

        # Handle results
        if successes:
            flash(f"Zmodyfikowano członków grupy: {', '.join(successes)}.", "success")
        if errors:
            flash_error(f"Wystąpiły błędy podczas modyfikacji członków grupy: {', '.join(errors)}.")

        # Redirect after POST to avoid duplicate form submissions
        return redirect(url_for('main.modify_group_members'))

    elif request.method == 'GET':
        try:
            # Fetch domain and groups
            domain = session.get('domain', 'company.com')
            groups, oulist = list_all_groups(connection, domain)

            # Fetch selected group and its members
            selected_group = request.args.get('group_name')
            members = list_group_members(connection, domain, selected_group) if selected_group else []

            # Fetch all users for adding
            users = get_all_users(connection, domain_to_search_base(domain), session.get('options'))

            return render_template(
                'modify_group_members.html',
                groups=groups,
                members=members,
                selected_group=selected_group,
                users=users  # Pass the list of users to the template
            )
        except Exception as e:
            flash_error(f"Nie można pobrać listy grup: {str(e)}")
            return redirect(url_for('main.index'))

@main_routes.route('/groups_management', methods=['GET', 'POST'])
def groups_management():
    if 'login' not in session:
        return redirect(url_for('main.login'))

    connection = get_ldap_connection()  # Establish the LDAP connection
    if not connection:
        flash_error("Brak połączenia z Active Directory.")
        return redirect(url_for('main.index'))

    domain = session.get('domain', 'company.com')

    if request.method == 'POST':
        action = request.form.get('action')  # Determine if adding or deleting
        group_name = request.form.get('group_name')

        if not group_name:
            flash_error("Group name cannot be empty.")
            return redirect(url_for('main.groups_management'))

        if action == 'add':
            try:
                # Load configuration for the new group
                config_path = os.path.abspath('./app/templates/group-config.json')
                
                config = load_json_config(config_path)

                # Attempt to add the group
                success = add_new_group(connection, config)
                if success:
                    flash(f"Group '{group_name}' added successfully.", "success")
                else:
                    flash_error(f"Failed to add group '{group_name}'. Check the logs for more details.")
            except FileNotFoundError:
                flash_error(f"Configuration file not found at at at '{config_path}'.")
            except KeyError as ke:
                flash_error(f"Configuration is missing a required field: {str(ke)}")
            except Exception as e:
                flash_error(f"Error while adding group '{group_name}': {str(e)}")

        elif action == 'delete':
            try:
                print("Iam here")
                # Fetch group details to get the correct OU
                groups, oulist = list_all_groups(connection, domain)
                group_ou = oulist[groups.index(group_name)] if group_name in groups else None

                if not group_ou:
                    flash_error(f"Group '{group_name}' not found.")
                    return redirect(url_for('main.groups_management'))

                _, group_ou, _ = parse_user_data2(group_ou)

                # Attempt to delete the group
                print(group_name ,"+", domain , "+", group_ou, "+")
                success = remove_group(connection, group_name, domain, group_ou)  # Implement this function
                if success:
                    flash(f"Group '{group_name}' deleted successfully.", "success")
                else:
                    flash_error(f"Failed to delete group '{group_name}'.")
            except ValueError:
                flash_error(f"Group '{group_name}' not found in the domain.")
            except Exception as e:
                flash_error(f"Error while deleting group '{group_name}': {str(e)}")

        # Redirect to refresh the group list
        return redirect(url_for('main.groups_management'))

    # Handle GET request: Retrieve and display the list of groups
    try:
        groups, _ = list_all_groups(connection, domain)  # Fetch all groups
        return render_template('groups_management.html', groups=groups)
    except Exception as e:
        flash_error(f"Nie można pobrać listy grup: {str(e)}")
        return redirect(url_for('main.index'))




@main_routes.app_errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404