from flask import Blueprint, render_template, request, redirect, url_for, session

main_routes = Blueprint('main', __name__)

@main_routes.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session["username"])
    return redirect(url_for('main.login'))

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        session['username'] = username
        return redirect(url_for('main.index'))
    return render_template('login.html')  # Wyświetla formularz logowania

@main_routes.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('main.login'))

# Obsługa błędu 404
@main_routes.app_errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404
