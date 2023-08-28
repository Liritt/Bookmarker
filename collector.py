import json
import re
from time import sleep
from typing import List

from bs4 import BeautifulSoup
import requests
from urllib import parse, request

from database import get_url_from_database


class Manganato:
    soup: BeautifulSoup = None
    headers: dict = None
    base_url: str = None
    name: str = None

    def __init__(self, name):
        self.base_url = "https://manganato.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36"
        }
        homepage = requests.get(self.base_url, headers=self.headers)
        self.soup = BeautifulSoup(homepage.content, 'html.parser')
        self.name = name

    def _get_url_with_name_search(self) -> str | None:
        params = parse.urlencode({"searchword": self.name}).encode("utf-8")

        target_url = request.Request(url="https://manganato.com/getstorysearchjson", data=params, headers=self.headers)
        x = request.urlopen(target_url)
        results = json.loads(x.read())
        name_list = {}
        for res in results['searchlist']:
            soup = BeautifulSoup(res['name'], 'html.parser')
            name_text = soup.get_text()
            name_list.update({name_text.lower(): res['url_story']})

        if not name_list:
            print(f'No comic associated for name "{self.name}"')
            return None

        url = None
        try:
            url = name_list[self.name.lower()]
        except KeyError:
            # In case someone use an alternative name
            url_list = [res['url_story'] for res in results['searchlist']]
            for url_elt in url_list:
                if url:
                    break

                page = requests.get(url_elt, headers=self.headers)
                soup = BeautifulSoup(page.content, 'html.parser')
                alt_names = self._get_alt_names(soup)
                for alt_name in alt_names:
                    if self.name.lower() == alt_name.lower():
                        url = url_elt
                        break
                sleep(1)

            if not url:
                print(name_list, self.name)
                print(f'Couldn\'t find comic named "{self.name}"')
                return None

        # noinspection PyUnboundLocalVariable
        return url

    def _get_url(self):
        url = get_url_from_database(self.name)
        if not url:
            url = self._get_url_with_name_search()

        return url

    def _get_picture_url(self, soup: BeautifulSoup) -> None | str:
        try:
            pic = soup.find("span", class_='info-image').find("img")['src']
        except (IndexError, KeyError):
            print("Failed to get image")
            return None

        return pic

    def _get_chapter_number_from_url(self, url: str):
        pattern = r'/chapter-(\d+(?:\.\d+)?)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    def _get_alt_names(self, soup: BeautifulSoup):
        table = soup.find('table', class_='variations-tableInfo')
        td_list = table.find('tr').find_all('td')
        if td_list[0].text != 'Alternative :':
            print('No alternative names found for this comic')
            return {}

        all_alt_names = td_list[1].find('h2').text.split(';')
        regex = re.compile(r'^[\u0000-\u00FF]+$')
        cleaned_alt_names = [alt_name.strip() for alt_name in all_alt_names if regex.match(alt_name)]
        return cleaned_alt_names if cleaned_alt_names != set() else {}

    def get_data(self, user_chapter_number: float) -> dict | None:
        url = self._get_url()
        if not url:
            return None

        page = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(page.content, 'html.parser')

        title = soup.find('h1').text
        alt_names = self._get_alt_names(soup)
        pic_url = self._get_picture_url(soup)

        all_chapters = soup.find("ul", class_='row-content-chapter').find_all("li", class_='a-h')
        data = {'title': title, 'alt_names': alt_names, 'pic_url': pic_url, 'url': url}
        new_chapters = []
        for chapter in all_chapters:
            chapter_title = chapter.find('a')['title']
            chapter_url = chapter.find('a')['href']
            chapter_number = self._get_chapter_number_from_url(chapter_url)
            if float(chapter_number) > user_chapter_number:
                new_chapters.append(
                    {
                        'url': chapter_url,
                        'title': chapter_title,
                    }
                )

        data['new_chapters'] = new_chapters
        return data
