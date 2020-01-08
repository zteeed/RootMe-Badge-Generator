from typing import Dict


def extract_data(data: Dict, url: str) -> Dict:
    top = 100 * data["ranking"] / data["ranking_tot"]
    top = '{0:.2f}'.format(top)
    return {
        'url': url,
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
