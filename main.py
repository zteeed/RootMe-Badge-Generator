import json

from flask import Flask, flash, render_template, request, send_from_directory

from config import Config
from env import URL, API_URL
from src.http_client import http_get
from src.parser import extract_data
from src.storage import make_storage, make_storage_js

app = Flask(__name__)
app.config.from_object(Config)


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

    url = f'{API_URL}/en/{username}/details'
    content = http_get(url)
    data = json.loads(content)['body']
    if data is None:
        flash(f'{username} is not a valid RootMe username.', 'error')
        return render_template('index.html')

    data = data[0]
    data = extract_data(data)
    # store static png badges
    save_paths, folder_path, avatar_path = make_storage(data)
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
    app.run(host='0.0.0.0', port=80)
