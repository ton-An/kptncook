"""
Repositories to store recipes.

Atm only uses json. But this could also be a sqlite or a
remote api, maybe mealie... hmm.
"""
from datetime import date
from pathlib import Path
from time import time

import httpx
from pydantic import BaseModel, parse_file_as

from .config import settings


class RecipeInDb(BaseModel):
    date: date
    data: dict

    @property
    def id(self):
        return self.data["_id"]["$oid"]


class RecipeListInDb(BaseModel):
    __root__: list[RecipeInDb]


class RecipeRepository:
    name: str = "kptncook.json"

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    @property
    def path(self) -> Path:
        return self.base_dir / self.name

    def _write_models(self, locked):
        try:
            self.path.parent.mkdir(exist_ok=True)
        except AttributeError:
            # LocalPath in tests
            pass
        models = RecipeListInDb(__root__=list(locked.values()))
        with self.path.open("w") as f:
            f.write(models.json())

    def _fetch_all(self):
        """
        Fetch dict of pydantic models from json in self.path
        """
        try:
            return parse_file_as(list[RecipeInDb], self.path)
        except FileNotFoundError:
            return []

    def list(self):
        return self._fetch_all()

    def list_by_id(self):
        by_id = {}
        for recipe in self.list():
            by_id[recipe.id] = recipe
        return by_id

    def needs_to_be_synced(self, date: date):
        """
        Return True if there are no recipes for date.
        """
        return not any(recipe.date == date for recipe in self.list())

    def add(self, recipe: RecipeInDb):
        locked = self.list_by_id()
        locked[recipe.id] = recipe
        self._write_models(locked)

    def add_list(self, recipes: list[RecipeInDb]):
        locked = self.list_by_id()
        for recipe in recipes:
            locked[recipe.id] = recipe
        self._write_models(locked)


class HttpRepository:
    """
    Fetch recipes for today from kptncook site.
    """

    @property
    def today_url(self):
        time_str = str(time())
        return f"https://mobile.kptncook.com/recipes/de/{time_str}?kptnkey={settings.api_key}"

    def list_today(self):
        response = httpx.get(self.today_url)
        response.raise_for_status()
        recipes = []
        today = date.today()
        for data in response.json():
            recipes.append(RecipeInDb(date=today, data=data))
        return recipes
