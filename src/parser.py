import json
import re
from typing import Dict, Optional, Tuple

from src.http_client import RMAPI


def extract_info_username_input(username: str, api: RMAPI) \
        -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    # Check if id_auteur is in username
    result_id_auteur = re.findall(r'-(\d+)$', username)
    if result_id_auteur:
        id_auteur = int(result_id_auteur[0])
        content = api.get_user_data(id_auteur)
        real_username = '-'.join(username.split('-')[:-1])
        if content is not None and json.loads(content)['nom'] != real_username:  # content might be None is score = 0
            return None, None, f'{username} is not a valid RootMe username.', 'error'
        content = api.get_user_info(real_username)
        if content is None:
            return None, None, f'{username} is not a valid RootMe username.', 'error'
        data = json.loads(content)[0]
        if id_auteur not in [int(data[key]['id_auteur']) for key in data]:
            return None, None, f'{username} is not a valid RootMe username.', 'error'
        username = real_username
    else:
        content = api.get_user_info(username)
        if content is None:
            return None, None, f'{username} is not a valid RootMe username.', 'error'
        data = json.loads(content)[0]
        if len(data) > 1:  # several accounts with same username
            users = []
            for key in data:
                users.append({
                    'username_select': f'{data[key]["nom"]}-{data[key]["id_auteur"]}',
                    'score': int(api.get_score_existing_user(data[key]['id_auteur']))
                })
            users = sorted(users, key=lambda x: x['score'], reverse=True)
            message = '<div style="text-align: left">'
            message += 'Several users exists from this username.<br>Please choose between these:<br><ul>'
            for user in users:
                message += f'<li>{user["username_select"]} (Score = {user["score"]} point(s))</li>'
            message += '</ul></div>'
            return None, None, f'{message}', 'info'
        data = data['0']
        id_auteur = data['id_auteur']
    return username, id_auteur, None, None


def extract_data(data: Dict, id_auteur: int, api: RMAPI, url: str) -> Dict:
    nu = api.number_users
    if nu is None or nu < 1:
        raise ValueError(
            'Root-Me total user count is unavailable (api.number_users); '
            'cannot compute ranking. Check API initialization.'
        )

    pos_raw = data.get('position')
    # Score 0 : l’API renvoie souvent "position": "" → dernier rang = nombre total d’auteurs (pas de valeur fictive type 1).
    if pos_raw is None or pos_raw == '':
        position = nu
    else:
        position = int(pos_raw)

    score_raw = data.get('score')
    score = 0 if score_raw in (None, '') else int(score_raw)

    top = max(0.01, 100 * position / nu)
    top = '{0:.2f}'.format(top)
    username = data['nom']
    profile_page_url = api.get_profile_page_url(username, id_auteur, score)
    return {
        'url': url,
        'name': username,
        'fullname': f'{username}-{id_auteur}',
        'avatar_url': api.get_avatar_url(profile_page_url),
        'score': score,
        'rank': api.get_rank(profile_page_url),
        'ranking': position,
        'ranking_tot': nu,
        'top': f'{top}%',
        'challenge': {
            'solved': len(data.get('validations') or []),
            'total': api.number_challenges
        }
    }
