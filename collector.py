import json
import re

from bs4 import BeautifulSoup
import requests
from urllib import parse, request


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

    def _get_url_with_id(self):
        return

    def _get_url_with_name_search(self):
        params = parse.urlencode({"searchword": self.name}).encode("utf-8")

        target_url = request.Request(url="https://manganato.com/getstorysearchjson", data=params, headers=self.headers)
        x = request.urlopen(target_url)
        results = json.loads(x.read())
        name_list = {}
        for res in results['searchlist']:
            soup = BeautifulSoup(res['name'], 'html.parser')
            name_text = soup.get_text()
            name_list.update({name_text: res['url_story']})

        try:
            url = name_list[self.name.lower()]
        except KeyError:
            print(f"{self.name} not found among values {name_list.keys()}")
            exit(1)

        return url

    def _get_image_url(self, soup: BeautifulSoup) -> str:
        try:
            pic = soup.find("span", class_='info-image').find("img")['src']
        except (IndexError, KeyError):
            print("Failed to get image")
            exit(1)

        return pic

    def _get_chapter_number_from_url(self, url: str):
        pattern = r'/chapter-(\d+(?:\.\d+)?)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    def get_data(self, user_chapter_number: int):
        url = self._get_url_with_name_search()
        page = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        pic = self._get_image_url(soup)
        title = soup.find('h1').text

        all_chapters = soup.find("ul", class_='row-content-chapter').find_all("li", class_='a-h')
        data = {'pic': pic, 'title': title, 'url': url}
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
