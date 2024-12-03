from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
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
from app.models.dodawanie import add_user_to_active_directory

main_routes = Blueprint('main', __name__)

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
    connection = session.get('connection', None)
    if not connection:
        flash_error("Brak aktywnego połączenia LDAP.")
        return None
    return connection

# Form validation
def validate_form(fields):
    return all(fields)

@main_routes.route('/')
def index():
    if 'login' in session:
        return render_template('index.html', login=session["login"])
    return redirect(url_for('main.login'))

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ldap_server = request.form['ldap_server']
        login = request.form['login']
        password = request.form['password']
        domain = request.form['domain']

        [is_connected, connection] = co.connect_to_active_directory(ldap_server, login, password, domain)
        #is_connected = True  #todo usun 
        if is_connected:
            session['ldap_server'] = ldap_server
            session['login'] = login
            session['domain'] = domain
            session['connection'] = connection
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error="Błąd logowania. Proszę sprawdzić dane.")

    return render_template('login.html')

@main_routes.route('/logout')
def logout():
    connection = session.get('connection', None)
    if connection:
        co.disconnect_from_active_directory(connection)

    session.pop('login', None)
    session.pop('ldap_server', None)
    session.pop('domain', None)
    session.pop('connection', None)

    return redirect(url_for('main.login'))

@main_routes.route('/delete_user',  methods=['GET', 'POST'])
def delete_user():
    if request.method == 'POST':
        username = request.form['username']
        domain = request.form['domain']
        connection = get_ldap_connection()

        if connection:
            try:
                success = delete_user_from_active_directory(connection, username, domain)
                if success:
                    flash(f"Użytkownik {username} został pomyślnie usunięty.", 'success')
                else:
                    flash_error(f"Wystąpił błąd podczas usuwania użytkownika {username}.")
            except Exception as e:
                flash_error(f"Wystąpił błąd: {str(e)}")
        return redirect(url_for('main.index'))  # Ensure this is returned after POST handling.

    # Ensure there's a return statement for the GET method, possibly returning a template
    return render_template('delete_user.html')  # If the request method is GET, show the delete user form.


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
            success = add_user_to_active_directory(connection, username, first_name, last_name, password, ou)
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

    # If the request is POST, process the form
    if request.method == 'POST':
        username = request.form.get('username')
        domain = session.get('domain')
        organizational_unit = request.form.get('organizational_unit', 'Users')

        # Get the LDAP connection
        connection = get_ldap_connection()

        if not connection or not domain:
            flash_error("Brak aktywnego połączenia LDAP lub nieznana domena.")
            return redirect(url_for('main.login'))

        try:
            # Attempt to change the block status of the user
            success = change_users_block_status(connection, username, domain, organizational_unit)
            if success:
                flash(f"Status blokady użytkownika {username} został zmieniony.", "success")
            else:
                flash_error(f"Nie udało się zmienić statusu blokady użytkownika {username}.")
        except Exception as e:
            flash_error(f"Wystąpił błąd: {str(e)}")

        return redirect(url_for('main.index'))

    # If the request is GET, show the block user form
    return render_template('block_user.html')


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
