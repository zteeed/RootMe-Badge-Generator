import json

import os
import re
from flask import Flask, flash, render_template, request, send_from_directory

from config import Config
from dotenv import load_dotenv
from datetime import timedelta

from src.http_client import RMAPI
from src.parser import extract_data
from src.storage import make_storage, make_storage_js


load_dotenv()
app = Flask(__name__)
app.config.from_object(Config)

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

    # Check if id_auteur is in username
    result_id_auteur = re.findall(r'-(\d+)$', username)
    if result_id_auteur:
        id_auteur = int(result_id_auteur[0])
        content = api.get_user_data(id_auteur)
        real_username = '-'.join(username.split('-')[:-1])
        if content is not None and json.loads(content)['nom'] != real_username:  # content might be None is score = 0
            flash(f'{username} is not a valid RootMe username.', 'error')
            return render_template('index.html')
        content = api.get_user_info(real_username)
        if content is None:
            flash(f'{username} is not a valid RootMe username.', 'error')
            return render_template('index.html')
        data = json.loads(content)[0]
        if id_auteur not in [int(data[key]['id_auteur']) for key in data]:
            flash(f'{username} is not a valid RootMe username.', 'error')
            return render_template('index.html')
        username = real_username
    else:
        content = api.get_user_info(username)
        if content is None:
            flash(f'{username} is not a valid RootMe username.', 'error')
            return render_template('index.html')
        data = json.loads(content)[0]
        if len(data) > 1:  # several accounts with same username
            message = '<div style="text-align: left">'
            message += 'Several users exists from this username.<br>Please choose between these:<br><ul>'
            for key in data:
                username_select = f'{data[key]["nom"]}-{data[key]["id_auteur"]}'
                score = api.get_score_existing_user(data[key]['id_auteur'])
                message += f'<li>{username_select} (Score = {score} point(s))</li>'
            message += '</ul></div>'
            flash(message, 'info')
            return render_template('index.html')
        data = data['0']
        id_auteur = data['id_auteur']

    url = f'{api.api_url}/auteurs/{id_auteur}'
    content = api.http_get(url)
    if content is None:
        data = {
            'nom': username,
            'position': api.number_users,
            'score': 0,
            'validations': []
        }
    else:
        data = json.loads(content)
    data = extract_data(data, id_auteur, api, URL)

    # store static png badges
    save_paths, folder_path, avatar_path = make_storage(api, data)
    # update avatar_url with local url
    data['avatar_url'] = f'{URL}/{avatar_path}'
    # store dynamic js badge as js script
    dynamic_js_badge = render_template('dynamic-js-badge.html', data=data)
    js_file_path = make_storage_js(dynamic_js_badge, folder_path)
    return render_template('badge.html', data=data, save_paths=save_paths, js_file_path=js_file_path)


@app.route('/storage_server/<string:filename>')
def serve_files(filename):
    return send_from_directory(f'storage_server', filename)


@app.route('/storage_clients/<string:folder>/<string:filename>')
def serve_files_clients(folder, filename):
    return send_from_directory(f'storage_clients/{folder}', filename)


if __name__ == '__main__':
    api = RMAPI()
    app.run(host='0.0.0.0', port=80)
