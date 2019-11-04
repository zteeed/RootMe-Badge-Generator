import os
from typing import Dict

URL = os.environ.get('URL')


def extract_data(data: Dict) -> Dict:
    top = 100 * data["ranking"] / data["ranking_tot"]
    top = '{0:.2f}'.format(top)
    return {
        'url': URL,
        'name': data['pseudo'],
        'avatar_url': 'https://www.root-me.org/local/cache-vignettes/L64xH64/auton236284-2442c.jpg',
        'score': data['score'],
        'rank': data['ranking_category'],
        'top': f'{top}%',
        'challenge': {
            'solved': data['nb_challenges_solved'],
            'total': data['nb_challenges_tot']
        }
    }
