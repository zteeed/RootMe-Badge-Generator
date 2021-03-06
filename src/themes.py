from os.path import abspath
from typing import Tuple


class Theme:
    background_color: Tuple[int, int, int]
    username_color: Tuple[int, int, int]
    ranking_color: Tuple[int, int, int]
    title_color: Tuple[int, int, int]
    score_color: Tuple[int, int, int]
    logo: str


class LightTheme(Theme):
    background_color = (255, 255, 255)
    username_color = (0, 0, 0)
    ranking_color = (38, 38, 38)
    title_color = (255, 172, 18)
    score_color = (34, 186, 0)
    logo = abspath("storage_server/skull-black.png")


class DarkTheme(Theme):
    background_color = (69, 69, 69)
    username_color = (255, 255, 255)
    ranking_color = (255, 241, 227)
    title_color = (230, 120, 2)
    score_color = (34, 186, 0)
    logo = abspath("storage_server/skull-white.png")
