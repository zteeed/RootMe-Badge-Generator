import re
from typing import Dict, List, Optional, Tuple

from src.http_client import RMAPI


def _find_user_id_from_suffix(username: str, api: RMAPI) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """Handle usernames like 'alice-12345' where the suffix is the author ID."""
    id_auteur = int(re.findall(r"-(\d+)$", username)[0])
    real_username = "-".join(username.split("-")[:-1])

    data = api.get_user_data(id_auteur)
    if data is not None and data["nom"] != real_username:
        return None, None, f"{username} is not a valid RootMe username.", "error"

    user_info = api.get_user_info(real_username)
    if user_info is None:
        return None, None, f"{username} is not a valid RootMe username.", "error"

    known_ids = [int(user_info[key]["id_auteur"]) for key in user_info]
    if id_auteur not in known_ids:
        return None, None, f"{username} is not a valid RootMe username.", "error"

    return real_username, id_auteur, None, None


def _build_disambiguation_message(users: List[Dict]) -> str:
    users = sorted(users, key=lambda u: u["score"], reverse=True)
    items = "".join(
        f'<li>{u["username_select"]} (Score = {u["score"]} point(s))</li>'
        for u in users
    )
    return (
        '<div style="text-align: left">'
        "Several users exists from this username.<br>"
        "Please choose between these:<br>"
        f"<ul>{items}</ul></div>"
    )


def _find_user_id_by_name(username: str, api: RMAPI) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """Handle plain usernames — may match multiple accounts."""
    user_info = api.get_user_info(username)
    if user_info is None:
        return None, None, f"{username} is not a valid RootMe username.", "error"

    if len(user_info) > 1:
        users = [
            {
                "username_select": f'{user_info[key]["nom"]}-{user_info[key]["id_auteur"]}',
                "score": api.get_score(int(user_info[key]["id_auteur"])),
            }
            for key in user_info
        ]
        message = _build_disambiguation_message(users)
        return None, None, message, "info"

    entry = user_info["0"]
    return username, entry["id_auteur"], None, None


def extract_info_username_input(
    username: str, api: RMAPI
) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    has_id_suffix = re.search(r"-(\d+)$", username)
    if has_id_suffix:
        return _find_user_id_from_suffix(username, api)
    return _find_user_id_by_name(username, api)


def extract_data(data: Dict, id_auteur: int, api: RMAPI, url: str) -> Dict:
    nu = api.number_users
    if nu is None or nu < 1:
        raise ValueError(
            "Root-Me total user count is unavailable (api.number_users); "
            "cannot compute ranking. Check API initialization."
        )

    position = _parse_position(data, nu)
    score = _parse_score(data)
    top = _compute_top_percentage(position, nu)

    username = data["nom"]
    profile_page_url = api.get_profile_page_url(username, id_auteur)

    return {
        "url": url,
        "name": username,
        "fullname": f"{username}-{id_auteur}",
        "avatar_url": api.get_avatar_url(profile_page_url),
        "score": score,
        "rank": api.get_rank(profile_page_url),
        "ranking": position,
        "ranking_tot": nu,
        "top": f"{top:.2f}%",
        "challenge": {
            "solved": len(data.get("validations") or []),
            "total": api.number_challenges,
        },
    }


def _parse_position(data: Dict, total_users: int) -> int:
    pos_raw = data.get("position")
    if pos_raw is None or pos_raw == "":
        return total_users
    return int(pos_raw)


def _parse_score(data: Dict) -> int:
    score_raw = data.get("score")
    if score_raw in (None, ""):
        return 0
    return int(score_raw)


def _compute_top_percentage(position: int, total_users: int) -> float:
    return max(0.01, 100 * position / total_users)
