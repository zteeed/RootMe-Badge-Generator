import os
from typing import Dict

from env import URL


def extract_data(data: Dict) -> Dict:
    top = 100 * data["ranking"] / data["ranking_tot"]
    top = '{0:.2f}'.format(top)
    return {
        'url': URL,
        'name': data['pseudo'],
        'avatar_url': data['avatar_url'],
        'score': data['score'],
        'rank': data['ranking_category'],
        'ranking': data['ranking'],
        'ranking_tot': data['ranking_tot'],
        'top': f'{top}%',
        'challenge': {
            'solved': data['nb_challenges_solved'],
            'total': data['nb_challenges_tot']
        }
    }
