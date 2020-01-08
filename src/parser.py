from typing import Dict

from src.http_client import RMAPI


def extract_data(data: Dict, id_auteur: int, api: RMAPI, url: str) -> Dict:
    top = 100 * data['position'] / api.number_users
    top = '{0:.2f}'.format(top)
    return {
        'url': url,
        'name': data['nom'],
        'fullname': f'{data["nom"]}-{id_auteur}',
        'avatar_url': api.get_avatar_url(data['nom'], id_auteur),
        'score': data['score'],
        'rank': api.get_rank(data['nom'], id_auteur),
        'ranking': data['position'],
        'ranking_tot': api.number_users,
        'top': f'{top}%',
        'challenge': {
            'solved': len(data['validations']),
            'total': api.number_challenges
        }
    }
