import re
from time import sleep

import discord

import settings
from collector import Manganato
from database import insert_new_comic

intents = discord.Intents.all()
client = discord.Client(intents=intents)
lst_messages = {}


@client.event
async def on_ready():
    channel = client.get_channel(settings.DISCORD['channel_id'])
    bot_channel = client.get_channel(settings.DISCORD['bot_channel_id'])
    async for message in channel.history(limit=1000):
        if 'Marqueur' in [role.name for role in message.author.roles]:
            lst_messages.update({message.id: message.content.strip()})

    for message in lst_messages.values():
        res = get_details_from_message(message)
        if not res:
            # await bot_channel.send(f"Sorry, couldn't process message '{message}'")
            continue

        title, chapter_number = res
        comic_data = Manganato(title).get_data(float(chapter_number))
        if not comic_data:
            # await bot_channel.send(f"Sorry, couldn't find comic '{title}' on manganato :(")
            continue
        print(comic_data)
        insert_new_comic(comic_data, 'manganato')
        sleep(1)


@client.event
async def on_message(message):
    if message.channel.id == settings.DISCORD['channel_id'] and 'Marqueur' in [role.name for role in
                                                                               message.author.roles]:
        lst_messages.update({message.id: message.content})


@client.event
async def on_message_edit(before, after):
    if before.channel.id == settings.DISCORD['channel_id'] and 'Marqueur' in [role.name for role in after.author.roles]:
        lst_messages.update({before.id: after.content})


@client.event
async def on_message_delete(message):
    if message.channel.id == settings.DISCORD['channel_id'] and message.id in lst_messages:
        lst_messages.pop(message.id)


def get_details_from_message(message: str) -> tuple[str, str] | None:
    message = message.lower()
    match = re.search(r'(?: -| –)?\s*(?:chapter|chapitre)\s*(\d+(?:[.,]\d+)?)', message)

    if match:
        title = message[:match.start()].strip()
        cleaned_title = re.sub(r'\bvol\.\d+\b', '', title).strip()
        chapter_number = match.group(1).replace(',', '.')
        return cleaned_title, chapter_number

    second_match = re.match(r'^(.*?)\s+(\d+(?:\.\d+)?)$', message)
    if second_match:
        title = second_match.group(1).strip()
        cleaned_title = re.sub(r'\bvol\.\d+\b', '', title).strip()
        chapter_number = second_match.group(2).replace(',', '.')
        return cleaned_title, chapter_number

    return None


client.run(settings.DISCORD['bot_token'])
