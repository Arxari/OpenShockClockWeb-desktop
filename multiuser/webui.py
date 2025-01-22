from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import os
import configparser
import threading
import time
import requests
import logging
import bcrypt

app = Flask(__name__)
app.secret_key = 'arxdeari'
USER_DIR = os.path.join(os.path.dirname(__file__), 'users')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True

user_alarm_threads = {}

def load_user_config(username):
    """Loads saved alarms for the user from their config.txt file."""
    alarms = {}
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(user_config_file):
        config.read(user_config_file)
        for section in config.sections():
            alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
            intensity = int(config[section]['intensity'])
            duration = int(config[section]['duration'])
            vibrate_before = config[section].getboolean('vibrate_before', fallback=False)
            alarms[section] = (alarm_time, intensity, duration, vibrate_before)
    logging.debug(f"Loaded alarms for user {username}: {alarms}")
    return alarms

def save_alarm_to_user_config(username, alarm_name, alarm_time, intensity, duration, vibrate_before):
    """Saves an alarm to the user's config.txt file."""
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(user_config_file):
        config.read(user_config_file)

    if alarm_name in config.sections():
        config.remove_section(alarm_name)

    config[alarm_name] = {
        'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
        'intensity': str(intensity),
        'duration': str(duration),
        'vibrate_before': str(vibrate_before)
    }

    with open(user_config_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved alarm for user {username}: {alarm_name} at {alarm_time}, vibrate_before: {vibrate_before}")

def load_user_env(username):
    """Loads the API key and Shock ID from the user's .env file."""
    user_env_file = os.path.join(USER_DIR, username, '.env')
    if os.path.exists(user_env_file):
        config = configparser.ConfigParser()
        config.read(user_env_file)
        api_key = config['DEFAULT'].get('SHOCK_API_KEY')
        shock_id = config['DEFAULT'].get('SHOCK_ID')
        logging.debug(f"Loaded env for user {username}: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")
        return api_key, shock_id
    logging.warning(f"No .env file found for user {username}")
    return None, None

def save_user_env(username, api_key, shock_id):
    """Saves the API key and Shock ID to the user's .env file."""
    user_env_file = os.path.join(USER_DIR, username, '.env')
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'SHOCK_API_KEY': api_key,
        'SHOCK_ID': shock_id
    }
    with open(user_env_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved env for user {username}: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")

def trigger_shock(api_key, shock_id, intensity, duration, shock_type='Shock'):
    """Sends a shock or vibrate command to the OpenShock API."""
    url = 'https://api.shocklink.net/2/shockers/control'
    headers = {
        'accept': 'application/json',
        'OpenShockToken': api_key,
        'Content-Type': 'application/json'
    }

    payload = {
        'shocks': [{
            'id': shock_id,
            'type': shock_type,
            'intensity': intensity,
            'duration': duration,
            'exclusive': True
        }],
        'customName': 'OpenShockClock'
    }

    try:
        response = requests.post(url=url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"{shock_type} triggered successfully: Intensity {intensity}, Duration {duration}")
    except requests.RequestException as e:
        logging.error(f"Failed to send {shock_type}. Error: {str(e)}")

def update_alarms(username):
    """Updates the alarms for the next day and checks if they need to be triggered."""
    logging.info(f"Starting alarm update thread for user {username}")
    while True:
        alarms = load_user_config(username)
        api_key, shock_id = load_user_env(username)

        if not api_key or not shock_id:
            logging.warning(f"Missing API key or Shock ID for user {username}")
            time.sleep(60)
            continue

        now = datetime.now()
        for name, (alarm_time, intensity, duration, vibrate_before) in list(alarms.items()):
            if vibrate_before and now >= alarm_time - timedelta(minutes=1) and now < alarm_time:
                logging.info(f"Triggering vibration for alarm {name} for user {username}")
                trigger_shock(api_key, shock_id, 100, 5000, 'Vibrate')

            if now >= alarm_time:
                logging.info(f"Triggering alarm {name} for user {username}")
                trigger_shock(api_key, shock_id, intensity, duration)

                next_alarm_time = alarm_time + timedelta(days=1)
                alarms[name] = (next_alarm_time, intensity, duration, vibrate_before)
                save_alarm_to_user_config(username, name, next_alarm_time, intensity, duration, vibrate_before)
                logging.info(f"Updated alarm {name} for user {username} to next day: {next_alarm_time}")

        time.sleep(60)

def start_user_alarm_thread(username):
    """Starts a thread to handle alarms for a specific user."""
    if username in user_alarm_threads and user_alarm_threads[username].is_alive():
        logging.info(f"Alarm thread for user {username} is already running")
        return

    thread = threading.Thread(target=update_alarms, args=(username,))
    thread.daemon = True
    thread.start()
    user_alarm_threads[username] = thread
    logging.info(f"Started alarm thread for user {username}")

def initialize_existing_users():
    """Initialize alarm threads for all existing users on startup."""
    if os.path.exists(os.path.join(USER_DIR, 'users.txt')):
        with open(os.path.join(USER_DIR, 'users.txt'), 'r') as f:
            for line in f:
                username = line.strip().split(':')[0]
                logging.info(f"Initializing alarm thread for existing user: {username}")
                start_user_alarm_thread(username)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    api_key, shock_id = load_user_env(username)
    alarms = load_user_config(username)
    env_file_exists = os.path.exists(os.path.join(USER_DIR, username, '.env'))
    return render_template('index.html', alarms=alarms, env_file_exists=env_file_exists)

@app.route('/add', methods=['GET', 'POST'])
def add_alarm():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        name = request.form['name']
        intensity = int(request.form['intensity'])
        duration = int(float(request.form['duration']) * 1000)
        time_str = request.form['time']
        vibrate_before = 'vibrate_before' in request.form
        alarm_time = datetime.strptime(time_str, "%H:%M").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )
        if alarm_time < datetime.now():
            alarm_time += timedelta(days=1)
        save_alarm_to_user_config(username, name, alarm_time, intensity, duration, vibrate_before)

        start_user_alarm_thread(username)

        return redirect(url_for('index'))
    return render_template('add_alarm.html')

@app.route('/edit/<alarm_name>', methods=['GET', 'POST'])
def edit_alarm(alarm_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()

    if not os.path.exists(user_config_file):
        flash('User configuration not found.')
        return redirect(url_for('index'))

    config.read(user_config_file)

    if alarm_name not in config.sections():
        flash('Alarm not found.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_name = request.form['name']
        intensity = int(request.form['intensity'])
        duration = int(float(request.form['duration']) * 1000)
        time_str = request.form['time']
        vibrate_before = 'vibrate_before' in request.form
        alarm_time = datetime.strptime(time_str, "%H:%M").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )
        if alarm_time < datetime.now():
            alarm_time += timedelta(days=1)

        config.remove_section(alarm_name)

        config[new_name] = {
            'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
            'intensity': str(intensity),
            'duration': str(duration),
            'vibrate_before': str(vibrate_before)
        }

        with open(user_config_file, 'w') as configfile:
            config.write(configfile)

        flash('Alarm updated successfully.')
        return redirect(url_for('index'))

    alarm_time = datetime.strptime(config[alarm_name]['time'], '%Y-%m-%d %H:%M:%S')
    intensity = config[alarm_name].getint('intensity')
    duration = config[alarm_name].getint('duration')
    vibrate_before = config[alarm_name].getboolean('vibrate_before', fallback=False)

    return render_template('edit_alarm.html', alarm_name=alarm_name,
                           time=alarm_time.strftime("%H:%M"),
                           intensity=intensity,
                           duration=duration/1000,
                           vibrate_before=vibrate_before)

@app.route('/delete/<alarm_name>')
def delete_alarm(alarm_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_config_file = os.path.join(USER_DIR, username, 'config.txt')
    config = configparser.ConfigParser()

    if os.path.exists(user_config_file):
        config.read(user_config_file)
        if alarm_name in config.sections():
            config.remove_section(alarm_name)
            with open(user_config_file, 'w') as configfile:
                config.write(configfile)
            flash('Alarm deleted successfully.')
        else:
            flash('Alarm not found.')
    else:
        flash('User configuration not found.')

    return redirect(url_for('index'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        api_key = request.form['api_key']
        shock_id = request.form['shock_id']
        save_user_env(username, api_key, shock_id)

        start_user_alarm_thread(username)

        return redirect(url_for('index'))
    else:
        api_key, shock_id = load_user_env(username)
        return render_template('setup.html', api_key=api_key, shock_id=shock_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if os.path.exists(os.path.join(USER_DIR, 'users.txt')):
            with open(os.path.join(USER_DIR, 'users.txt'), 'r') as f:
                existing_users = [line.strip().split(':')[0] for line in f]
            if username in existing_users:
                flash('Username already exists. Please choose a different one.')
                return redirect(url_for('register'))

        user_folder = os.path.join(USER_DIR, username)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)

        user_config_file = os.path.join(user_folder, 'config.txt')
        with open(user_config_file, 'w') as configfile:
            configfile.write('')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        with open(os.path.join(USER_DIR, 'users.txt'), 'a') as f:
            f.write(f"{username}:{hashed_password.decode('utf-8')}\n")

        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with open(os.path.join(USER_DIR, 'users.txt'), 'r') as f:
            users = dict(line.strip().split(':') for line in f)

        if username in users and bcrypt.checkpw(password.encode('utf-8'), users[username].encode('utf-8')):
            session['username'] = username
            start_user_alarm_thread(username)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username in user_alarm_threads:
        del user_alarm_threads[username]
        logging.info(f"Removed alarm thread for user {username}")
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(USER_DIR):
        os.makedirs(USER_DIR)

    logging.info("Starting OpenShockClock application")
    initialize_existing_users()
    logging.info("Initialization complete. Starting Flask server.")

    app.run(debug=False)
