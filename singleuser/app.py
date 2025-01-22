from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import os
import configparser
import threading
import time
import requests
import logging
import webview
import importlib.util
import sys
import argparse
from typing import Optional

app = Flask(__name__)
app.secret_key = 'arxdeari'
CONFIG_DIR = os.path.dirname(__file__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True

alarm_thread = None

def load_config():
    """Loads saved alarms from config.txt file."""
    alarms = {}
    config_file = os.path.join(CONFIG_DIR, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
        for section in config.sections():
            alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
            intensity = int(config[section]['intensity'])
            duration = int(config[section]['duration'])
            vibrate_before = config[section].getboolean('vibrate_before', fallback=False)
            alarms[section] = (alarm_time, intensity, duration, vibrate_before)
    logging.debug(f"Loaded alarms: {alarms}")
    return alarms

def save_alarm_to_config(alarm_name, alarm_time, intensity, duration, vibrate_before):
    """Saves an alarm to the config.txt file."""
    config_file = os.path.join(CONFIG_DIR, 'config.txt')
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)

    if alarm_name in config.sections():
        config.remove_section(alarm_name)

    config[alarm_name] = {
        'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
        'intensity': str(intensity),
        'duration': str(duration),
        'vibrate_before': str(vibrate_before)
    }

    with open(config_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved alarm: {alarm_name} at {alarm_time}, vibrate_before: {vibrate_before}")

def load_env():
    """Loads the API key and Shock ID from .env file."""
    env_file = os.path.join(CONFIG_DIR, '.env')
    if os.path.exists(env_file):
        config = configparser.ConfigParser()
        config.read(env_file)
        api_key = config['DEFAULT'].get('SHOCK_API_KEY')
        shock_id = config['DEFAULT'].get('SHOCK_ID')
        logging.debug(f"Loaded env: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")
        return api_key, shock_id
    logging.warning("No .env file found")
    return None, None

def save_env(api_key, shock_id):
    """Saves the API key and Shock ID to .env file."""
    env_file = os.path.join(CONFIG_DIR, '.env')
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'SHOCK_API_KEY': api_key,
        'SHOCK_ID': shock_id
    }
    with open(env_file, 'w') as configfile:
        config.write(configfile)
    logging.debug(f"Saved env: API Key: {'*' * len(api_key)}, Shock ID: {shock_id}")

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

def update_alarms():
    """Updates the alarms for the next day and checks if they need to be triggered."""
    logging.info("Starting alarm update thread")
    while True:
        alarms = load_config()
        api_key, shock_id = load_env()

        if not api_key or not shock_id:
            logging.warning("Missing API key or Shock ID")
            time.sleep(60)
            continue

        now = datetime.now()
        for name, (alarm_time, intensity, duration, vibrate_before) in list(alarms.items()):
            if vibrate_before and now >= alarm_time - timedelta(minutes=1) and now < alarm_time:
                logging.info(f"Triggering vibration for alarm {name}")
                trigger_shock(api_key, shock_id, 100, 5000, 'Vibrate')

            if now >= alarm_time:
                logging.info(f"Triggering alarm {name}")
                trigger_shock(api_key, shock_id, intensity, duration)

                next_alarm_time = alarm_time + timedelta(days=1)
                alarms[name] = (next_alarm_time, intensity, duration, vibrate_before)
                save_alarm_to_config(name, next_alarm_time, intensity, duration, vibrate_before)
                logging.info(f"Updated alarm {name} to next day: {next_alarm_time}")

        time.sleep(60)

def start_alarm_thread():
    """Starts the alarm update thread."""
    global alarm_thread
    if alarm_thread and alarm_thread.is_alive():
        logging.info("Alarm thread is already running")
        return

    alarm_thread = threading.Thread(target=update_alarms)
    alarm_thread.daemon = True
    alarm_thread.start()
    logging.info("Started alarm thread")

@app.route('/')
def index():
    api_key, shock_id = load_env()
    alarms = load_config()
    env_file_exists = os.path.exists(os.path.join(CONFIG_DIR, '.env'))
    return render_template('index.html', alarms=alarms, env_file_exists=env_file_exists)

@app.route('/add', methods=['GET', 'POST'])
def add_alarm():
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
        save_alarm_to_config(name, alarm_time, intensity, duration, vibrate_before)
        start_alarm_thread()
        return redirect(url_for('index'))
    return render_template('add_alarm.html')

@app.route('/edit/<alarm_name>', methods=['GET', 'POST'])
def edit_alarm(alarm_name):
    config_file = os.path.join(CONFIG_DIR, 'config.txt')
    config = configparser.ConfigParser()

    if not os.path.exists(config_file):
        flash('Configuration not found.')
        return redirect(url_for('index'))

    config.read(config_file)

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

        if new_name != alarm_name:
            # If name is changed, remove old section first
            config.remove_section(alarm_name)
            # Then write the complete config in one operation
            config[new_name] = {
                'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
                'intensity': str(intensity),
                'duration': str(duration),
                'vibrate_before': str(vibrate_before)
            }
            with open(config_file, 'w') as configfile:
                config.write(configfile)
        else:
            # If name hasn't changed, just update the existing alarm
            save_alarm_to_config(alarm_name, alarm_time, intensity, duration, vibrate_before)

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
    config_file = os.path.join(CONFIG_DIR, 'config.txt')
    config = configparser.ConfigParser()

    if os.path.exists(config_file):
        config.read(config_file)
        if alarm_name in config.sections():
            config.remove_section(alarm_name)
            with open(config_file, 'w') as configfile:
                config.write(configfile)
            flash('Alarm deleted successfully.')
        else:
            flash('Alarm not found.')
    else:
        flash('Configuration not found.')

    return redirect(url_for('index'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        api_key = request.form['api_key']
        shock_id = request.form['shock_id']
        save_env(api_key, shock_id)
        start_alarm_thread()
        return redirect(url_for('index'))
    else:
        api_key, shock_id = load_env()
        return render_template('setup.html', api_key=api_key, shock_id=shock_id)

def run_server(app, port: int):
    if app:
        app.run(port=port)

def open_window(name: str, url: str, width: int = 800, height: int = 600):
    webview.create_window(name, url, width=width, height=height)
    webview.start()

if __name__ == '__main__':
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

    logging.info("Starting OpenShockClock application")
    start_alarm_thread()
    logging.info("Initialization complete. Starting Flask server and webview.")

    server = threading.Thread(
        target=run_server,
        args=(app, 1260),
        daemon=True
    )
    server.start()

    open_window("OpenShockClock", "http://localhost:1260", width=785, height=400)
