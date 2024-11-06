# /app/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session

main_routes = Blueprint('main', __name__)

@main_routes.route('/')
def index():
    if 'username' in session:
        return f'Logged in as {session["username"]}'
    return redirect(url_for('main.login'))

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect(url_for('main.index'))
    return "Hello World" #render_template('login.html')

@main_routes.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('main.index'))

@main_routes.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404
