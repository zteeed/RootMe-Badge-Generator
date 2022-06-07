import json
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, render_template, request, send_from_directory
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
from timeloop import Timeloop

from config import Config
from src.http_client import RMAPI
from src.parser import extract_data, extract_info_username_input
from src.storage import make_storage, make_storage_js

load_dotenv()
tl = Timeloop()
app = Flask(__name__)
app.config.from_object(Config)
api = RMAPI()
app.api = api
CORS(app)

URL = os.environ.get('URL')


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    if 'username' not in request.form:
        flash('A wrong form has been sent.', 'error')
        return render_template('index.html')

    username = request.form['username']
    if not username:
        flash('Username is empty', 'error')
        return render_template('index.html')

    username, id_auteur, flash_message, flash_type = extract_info_username_input(username, app.api)
    if flash_message is not None and flash_type is not None:  # username input is not related to a real RootMe account
        flash(f'{flash_message}', flash_type)
        return render_template('index.html')

    url = f'{app.api.api_url}/auteurs/{id_auteur}'
    content = app.api.http_get(url)
    if content is None:  # account exists but has a score equal to zero
        data = {
            'nom': username,
            'position': app.api.number_users,
            'score': 0,
            'validations': []
        }
    else:
        data = json.loads(content)
    data = extract_data(data, id_auteur, app.api, URL)

    # store static png badges
    save_paths, folder_path, avatar_path = make_storage(app.api, data)
    # update avatar_url with local url
    data['avatar_url'] = f'{URL}/{avatar_path}'
    # store dynamic js badge as js script
    dynamic_js_badge = render_template('dynamic-js-badge.html', data=data)
    js_file_path = make_storage_js(dynamic_js_badge, folder_path)
    return render_template('badge.html', data=data, save_paths=save_paths, js_file_path=js_file_path)


@app.route('/storage_server/<string:filename>')
@cross_origin(origin='*')
def serve_files(filename):
    filename = secure_filename(filename)
    return send_from_directory(f'storage_server', filename)


@app.route('/storage_clients/<string:folder>/<string:filename>')
def serve_files_clients(folder, filename):
    folder = secure_filename(folder)
    filename = secure_filename(filename)
    if filename == 'badge.js':
        return send_from_directory(f'storage_clients/{folder}', filename, mimetype='text/javascript')
    return send_from_directory(f'storage_clients/{folder}', filename)


@tl.job(interval=timedelta(days=1))
def update_number_rootme_challenges() -> None:
    app.api.update_number_rootme_challenges()


@tl.job(interval=timedelta(days=1))
def update_number_rootme_users() -> None:
    app.api.update_number_rootme_challenges()


def start_tl():
    tl.start(block=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
