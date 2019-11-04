import json
import os
from typing import Dict

from flask import Flask, flash, render_template, request, send_from_directory

from config import Config
from src.http_client import http_get

app = Flask(__name__)
app.config.from_object(Config)

URL = os.environ.get('URL')
API_URL = os.environ.get('API_URL')

s = requests.session()


def _extract_data(data: Dict) -> Dict:
    top = 100 * data["ranking"] / data["ranking_tot"]
    top = '{0:.2f}'.format(top)
    return {
        'url': URL,
        'name': data['pseudo'],
        'avatar': 'https://www.root-me.org/local/cache-vignettes/L64xH64/auton236284-2442c.jpg',
        'score': data['score'],
        'rank': data['ranking_category'],
        'top': f'{top}%',
        'challenge': {
            'solved': data['nb_challenges_solved'],
            'total': data['nb_challenges_tot']
        }
    }


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

    data = _extract_data(data[0])
    return render_template('badge.html', data=data)


@app.route('/storage_server/<string:filename>')
def serve_files(filename):
    return send_from_directory(f'storage_server', filename)


if __name__ == '__main__':
    app.run(debug=True)
