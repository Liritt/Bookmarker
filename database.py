from pypika import Query, Table, CustomFunction, terms
import psycopg2
from pypika.terms import Function

import settings

conn = psycopg2.connect(
    f"dbname={settings.DATABASE['name']} port={settings.DATABASE['port']} user={settings.DATABASE['user']} host={settings.DATABASE['host']} password={settings.DATABASE['password']}")

comic = Table('comic')

ARRAY_ANY = CustomFunction('ANY', ['column'])


def insert_new_comic(comic_data: dict, website_name: str):
    with conn.cursor() as curs:
        curs.execute(
            Query.from_(comic)
            .select(comic.star)
            .where(
                (comic.title == comic_data['title'])
                | (terms.Term.wrap_constant(comic_data['title']) == ARRAY_ANY(comic.alt_names))
            ).get_sql())

        if not curs.fetchone():
            column_name = website_name + '_url'
            query = (
                "INSERT INTO \"comic\" (title, alt_names, pic_url, \"{column}\", created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, NOW(), NOW())"
            ).format(column=column_name)

            values = (comic_data['title'], comic_data['alt_names'], comic_data['pic_url'], comic_data['url'])
            curs.execute(query, values)
            conn.commit()


def get_url_from_database(name: str):
    with conn.cursor() as curs:
        curs.execute(
            Query.from_(comic)
            .select(comic.manganato_url)
            .where(
                (Function('lower', comic.title) == name)
                | (terms.Term.wrap_constant(name) == ARRAY_ANY(comic.alt_names))
            ).get_sql())

        res = curs.fetchone()

    if res:
        res = res[0]

    return res
