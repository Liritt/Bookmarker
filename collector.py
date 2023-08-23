from bs4 import BeautifulSoup


class Mangakakalot:
    soup = None

    def __init__(self, html):
        self.soup = BeautifulSoup(html, 'html.parser')

    def get_title(self):
        return self.soup.find('h1').text

    def get_manwha_chapters(self):
        lst_chapters = []
        chapters = self.soup.select(
            "div.container-main-left div.panel-story-chapter-list ul.row-content-chapter li.a-h, "
            "#chapter div div.chapter-list div.row"
        )

        if len(chapters) > 0:
            for chapter in chapters:
                url_element = chapter.find("a") or chapter.find("span a")
                url = url_element["href"]

                try:
                    title_element = chapter.find("a") or chapter.find("span a")
                    title = title_element["title"]

                    name = ""
                    number = ""

                    if "Chapter" in title:
                        name = title.split("Chapter")[0].strip()
                        number = title.split("Chapter")[1].strip()
                    elif "chapter" in title:
                        name = title.split("chapter")[0].strip()
                        number = title.split("chapter")[1].strip()

                    if ":" in number:
                        number = number.split(":")[0].strip()

                    if "chapter" in name:
                        name = name.split("chapter")[0].strip()
                    try:
                        dat_upload = chapter.select_one("span.chapter-time.text-nowrap")
                        dat_upload = dat_upload["title"]
                    except Exception as e:
                        print(dat_upload, name, number)

                    if number and name:
                        lst_chapters.append({"name": name, "number": number, "url": url, "datUpload": dat_upload})

                except Exception as e:
                    print(e)
