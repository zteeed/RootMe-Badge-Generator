from os.path import abspath, dirname, isdir
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.themes import DarkTheme, LightTheme, Theme

FONT_PATH = "storage_server/BebasNeue-Regular.ttf"

THEMES: Dict[str, Theme] = {
    "light": LightTheme,
    "dark": DarkTheme,
}


class Badge:
    def __init__(
        self,
        pseudo: str,
        profile_picture: str,
        score: int,
        title: str,
        ranking: int,
        total_users: int,
        theme: str = "light",
        width: int = 500,
        height: int = 200,
    ) -> None:
        self.pseudo = pseudo
        self.pp = profile_picture
        self.score = score
        self.title = title
        self.ranking = ranking
        self.total_users = total_users
        self.theme = THEMES.get(theme, LightTheme)
        self.width = width
        self.height = height
        self.badge: Optional[Image.Image] = None

    # -- Drawing primitives -------------------------------------------------

    def _draw_profile_picture(self) -> None:
        pp = Image.open(self.pp)
        size = self._square_size(2 / 3)
        pp = pp.resize(size=size, resample=Image.BICUBIC)
        offset = self._square_size(0.1)
        self.badge.paste(pp, offset)

    def _draw_username(self) -> None:
        font = self._font(0.15)
        draw = ImageDraw.Draw(self.badge)
        offset = (self._right_column_x(), self._y(0.1))
        draw.text(xy=offset, text=self.pseudo, fill=self.theme.username_color, font=font)

    def _draw_points(self) -> None:
        font = self._font(0.10)
        draw = ImageDraw.Draw(self.badge)
        offset = (self._right_column_x(), self._y(0.35))
        draw.text(xy=offset, text=f"{self.score} pts", fill=self.theme.score_color, font=font)

    def _draw_ranking(self) -> None:
        font = self._font(0.10)
        draw = ImageDraw.Draw(self.badge)
        offset = (self._right_column_x(), self._y(0.50))
        text = self._ranking_text()
        draw.text(xy=offset, text=text, fill=self.theme.ranking_color, font=font)

    def _draw_title(self) -> None:
        font = self._font(0.15)
        draw = ImageDraw.Draw(self.badge)
        offset = (self._y(0.1), self._y(0.8))
        draw.text(xy=offset, text=self.title, fill=self.theme.title_color, font=font)

    def _draw_logo(self) -> None:
        size = self._square_size(1 / 3)
        logo = Image.open(self.theme.logo)
        logo = logo.resize(size=size, resample=Image.BICUBIC)
        offset = (int(self.width - size[0] - self.height * 0.1), self._y(0.1))
        self.badge.paste(im=logo, box=offset, mask=logo)

    # -- Layout helpers -----------------------------------------------------

    def _y(self, fraction: float) -> int:
        return int(self.height * fraction)

    def _square_size(self, fraction: float) -> Tuple[int, int]:
        side = int(self.height * fraction)
        return side, side

    def _right_column_x(self) -> int:
        return int(self.height * (2 / 3)) + int(self.height * 0.2)

    def _font(self, size_fraction: float) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(FONT_PATH, size=int(self.height * size_fraction))

    def _ranking_text(self) -> str:
        ranking = int(self.ranking)
        total = int(self.total_users)
        text = f"{ranking}/{total}"
        if ranking != 0 and total != 0:
            top = max(0.01, ranking / total * 100)
            text += f" (Top {top:.2f}%)"
        return text

    # -- Public API ---------------------------------------------------------

    def create(self) -> Image.Image:
        self.badge = Image.new(mode="RGB", size=(self.width, self.height), color=self.theme.background_color)
        self._draw_profile_picture()
        self._draw_username()
        self._draw_points()
        self._draw_logo()
        self._draw_title()
        self._draw_ranking()
        return self.badge

    def save(self, filepath: str) -> None:
        filepath = abspath(filepath)
        if not isdir(dirname(filepath)):
            raise IOError(f"The folder does not exist: '{dirname(filepath)}'")
        if self.badge is None:
            self.create()
        self.badge.save(filepath)


def get_available_themes() -> List[str]:
    return sorted(THEMES.keys())


def make_static_badge(data: Dict, theme: str, folder_path: str, avatar_path: str) -> str:
    badge = Badge(
        pseudo=data["name"],
        profile_picture=avatar_path,
        score=data["score"],
        title=data["rank"],
        ranking=data["ranking"],
        total_users=data["ranking_tot"],
        theme=theme,
    )
    badge.create()
    save_path = f"{folder_path}/static_badge_{theme}.png"
    badge.save(save_path)
    return save_path


def make_static_badges(data: Dict, folder_path: str, avatar_path: str) -> List[Dict[str, str]]:
    return [
        dict(theme=theme, path=make_static_badge(data, theme, folder_path, avatar_path))
        for theme in get_available_themes()
    ]
