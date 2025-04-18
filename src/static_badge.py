from os.path import dirname, isdir, abspath
from typing import Dict, List, Union

from PIL import Image, ImageDraw, ImageFont

from src.themes import LightTheme, DarkTheme


class Badge:
    THEMES = {
        "light": LightTheme,
        "dark": DarkTheme
    }
    FONT = "storage_server/BebasNeue-Regular.ttf"

    def __init__(self, pseudo: str, profile_picture: str, score: int, title: str, ranking: int, total_users: int,
                 theme: str = "light", width: int = 500, height: int = 200) -> None:
        self.pseudo = pseudo
        self.pp = profile_picture
        self.score = score
        self.title = title
        self.ranking = ranking
        self.total_users = total_users
        self.theme = self.THEMES.get(theme, "light")
        self.width = width
        self.height = height
        self.badge: Union[Image.Image, None] = None

    @classmethod
    def get_themes(cls):
        return sorted(tuple(cls.THEMES.keys()))

    def __draw_profile_picture(self) -> None:
        pp: Image.Image = Image.open(self.pp)
        size = int(self.height * (2 / 3)), int(
            self.height * (2 / 3))  # We want the pp to be 2/3 the height of the badge
        pp = pp.resize(
            size=size,
            resample=Image.BICUBIC
            # resample=Image.NEAREST
        )
        # We want the pp's top left corner to at an offset from the top left corner of the badge
        offset = int(self.height * 0.1), int(self.height * 0.1)
        self.badge.paste(pp, offset)

    def __draw_username(self) -> None:
        size = int(self.height * 0.15)
        font = ImageFont.truetype(self.FONT, size=size)
        d = ImageDraw.Draw(self.badge)
        offset = (
            int(self.height * (2 / 3)) + int(self.height * 0.2),  # The size of the pp, plus spacing between the objects
            int(self.height * 0.1)  # Spacing from the top of the badge
        )
        d.text(
            xy=offset,
            text=self.pseudo,
            fill=self.theme.username_color,
            font=font
        )

    def __draw_points(self) -> None:
        size = int(self.height * 0.10)
        font = ImageFont.truetype(self.FONT, size=size)
        d = ImageDraw.Draw(self.badge)
        offset = (
            int(self.height * (2 / 3)) + int(self.height * 0.2),  # The size of the pp, plus spacing between the objects
            int(self.height * 0.35)  # Spacing from the top of the badge + size of the username + padding
        )
        d.text(
            xy=offset,
            text=f"{self.score} pts",
            fill=self.theme.score_color,
            font=font
        )

    def __draw_logo(self) -> None:
        size = int(self.height * (1 / 3)), int(self.height * (1 / 3))
        logo: Image.Image = Image.open(self.theme.logo)
        logo = logo.resize(
            size=size,
            resample=Image.BICUBIC
        )
        offset = (
            int(self.width - size[0] - self.height * 0.1),
            int(self.height * 0.1)
        )
        self.badge.paste(
            im=logo,
            box=offset,
            mask=logo
        )

    def __draw_title(self) -> None:
        size = int(self.height * 0.15)
        font = ImageFont.truetype(self.FONT, size=size)
        d = ImageDraw.Draw(self.badge)
        offset = (
            int(self.height * 0.1),  # Spacing from the left side of the badge
            int(self.height * 0.8)  # Spacing from the bottom of the badge
        )
        d.text(
            xy=offset,
            text=self.title,
            fill=self.theme.title_color,
            font=font
        )

    def __draw_ranking(self) -> None:
        size = int(self.height * 0.10)
        font = ImageFont.truetype(self.FONT, size=size)
        d = ImageDraw.Draw(self.badge)
        offset = (
            int(self.height * (2 / 3)) + int(self.height * 0.2),  # The size of the pp, plus spacing between the objects
            int(self.height * 0.50)  # Spacing from the top of the badge + size of the username + padding
        )
        ranking = int(self.ranking)
        total = int(self.total_users)
        text = f"{ranking}/{total}"
        if ranking != 0 and total != 0:
            text += f" (Top {max(0.01, ranking / total * 100):.2f}%)"
        d.text(
            xy=offset,
            text=text,
            fill=self.theme.ranking_color,
            font=font
        )

    def create(self) -> Image.Image:
        self.badge = Image.new(
            mode="RGB",
            size=(self.width, self.height),
            color=self.theme.background_color
        )

        self.__draw_profile_picture()
        self.__draw_username()
        self.__draw_points()
        self.__draw_logo()
        self.__draw_title()
        self.__draw_ranking()

        return self.badge

    def save(self, filepath: str) -> None:
        filepath = abspath(filepath)
        if not isdir(dirname(filepath)):
            raise IOError(f"The folder does not exist: '{dirname(filepath)}'")
        if self.badge is None:
            self.create()
        self.badge.save(filepath)


def make_static_badge(data: Dict, theme: str, folder_path: str, avatar_path: str) -> str:
    badge = Badge(
        pseudo=data["name"],
        profile_picture=avatar_path,
        score=data["score"],
        title=data["rank"],
        ranking=data["ranking"],
        total_users=data["ranking_tot"],
        theme=theme
    )
    badge.create()
    save_path = f'{folder_path}/static_badge_{theme}.png'
    badge.save(save_path)
    return save_path


def make_static_badges(data: Dict, folder_path: str, avatar_path: str) -> List[Dict[str, str]]:
    save_paths = []
    themes = Badge.get_themes()
    for theme in themes:
        save_path = make_static_badge(data, theme, folder_path, avatar_path)
        save_paths.append(dict(theme=theme, path=save_path))
    return save_paths
