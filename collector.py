import asyncio
import json
import re
import urllib.error

import aiohttp
from bs4 import BeautifulSoup
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
        self.name = name

    async def _get_url_with_name_search(self, session) -> str | None:
        params = parse.urlencode({"searchword": self.name}).encode("utf-8")

        target_url = request.Request(url="https://manganato.com/getstorysearchjson", data=params, headers=self.headers)
        x = request.urlopen(target_url)
        results = json.loads(x.read())
        name_list = {}
        for res in results['searchlist']:
            soup = BeautifulSoup(res['name'], 'html.parser')
            name_text = soup.get_text()
            name_list.update({name_text.lower().strip(): res['url_story']})

        if not name_list:
            print(f'No comic associated for name "{self.name}"')
            return None

        url = None
        try:
            url = name_list[self.name.lower()]
        except KeyError:
            # In case user use an alternative name
            url_list = [res['url_story'] for res in results['searchlist']]
            for url_elt in url_list:
                if url:
                    break

                async with session.get(url_elt, headers=self.headers) as response:
                    page = await response.text()

                soup = BeautifulSoup(page, 'html.parser')
                alt_names = self._get_alt_names(soup)
                for alt_name in alt_names:
                    if self.name.lower() == alt_name.lower().strip():
                        url = url_elt
                        break
                await asyncio.sleep(1)

            if not url:
                print(f'Couldn\'t find comic named "{self.name}"')
                return None

        # noinspection PyUnboundLocalVariable
        return url

    async def _get_url(self, session):
        url = get_url_from_database(self.name)
        if not url:
            url = await self._get_url_with_name_search(session)

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

    def _get_alt_names(self, soup: BeautifulSoup):
        table = soup.find('table', class_='variations-tableInfo')
        td_list = table.find('tr').find_all('td')
        if td_list[0].text != 'Alternative :':
            return []

        brut_alt_names = td_list[1].find('h2').text
        if ';' in brut_alt_names:
            all_alt_names = brut_alt_names.split(';')
        elif ',' in brut_alt_names:
            all_alt_names = brut_alt_names.split(',')
        else:
            all_alt_names = brut_alt_names
        regex = re.compile(r'^[\u0000-\u00FF]+$')
        cleaned_alt_names = [alt_name.strip() for alt_name in all_alt_names if regex.match(alt_name)]
        return cleaned_alt_names if cleaned_alt_names != set() else {}

    async def get_data(self, user_chapter_number: float):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(self.base_url, headers=self.headers) as response:
                homepage = await response.text()
            self.soup = BeautifulSoup(homepage, 'html.parser')

            url = await self._get_url(session)
            if not url:
                return None

            async with session.get(url, headers=self.headers) as response:
                page = await response.text()
            soup = BeautifulSoup(page, 'html.parser')

            title = soup.find('h1').text
            alt_names = self._get_alt_names(soup)
            pic_url = self._get_picture_url(soup)

            all_chapters = soup.select("ul.row-content-chapter li.a-h")
            new_chapters = []

            for chapter in all_chapters:
                chapter_title = chapter.find('a')['title']
                chapter_url = chapter.find('a')['href']

                try:
                    chapter_number = self._get_chapter_number_from_url(chapter_url)
                except urllib.error.HTTPError:
                    print('Failed request to manganato, retrying in 30 seconds...')
                    await asyncio.sleep(30)
                    return await self.get_data(user_chapter_number)

                if float(chapter_number) > user_chapter_number:
                    new_chapters.append({'url': chapter_url, 'title': chapter_title})

            data = {
                'title': title,
                'alt_names': alt_names,
                'pic_url': pic_url,
                'url': url,
                'new_chapters': new_chapters
            }

            return data
