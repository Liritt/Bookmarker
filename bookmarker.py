import asyncio
import re

import discord
from discord.ext import commands

import settings
from collector import Manganato
from database import insert_new_comic

intents = discord.Intents.all()
client = discord.Client(intents=intents)
lst_messages = {}
lst_bot_messages = {}

bot = commands.Bot(command_prefix="/", intents=intents)


@client.event
async def on_ready():
    """
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
        comic_data = await Manganato(title).get_data(float(chapter_number))
        if not comic_data:
            # await bot_channel.send(f"Sorry, couldn't find comic '{title}' on manganato :(")
            continue

        insert_new_comic(comic_data, 'manganato')
        await asyncio.sleep(1)
    """


# region Message events
@client.event
async def on_message(message):
    bot_channel = get_channel(settings.DISCORD['bot_channel_id'])
    if (message.channel.id == settings.DISCORD['channel_id']
            and 'Marqueur' in [role.name for role in message.author.roles]
            and not message.author.bot):
        await process_message(message, bot_channel)


@client.event
async def on_message_edit(before, after):
    bot_channel = get_channel(settings.DISCORD['bot_channel_id'])
    if (before.channel.id == settings.DISCORD['channel_id']
            and 'Marqueur' in [role.name for role in after.author.roles]
            and not after.author.bot
            and before.id in lst_messages):
        msg = await bot_channel.fetch_message(lst_bot_messages[before.id])
        await msg.delete()
        lst_bot_messages.pop(before.id)
        await process_message(after, bot_channel)


@client.event
async def on_message_delete(message):
    bot_channel = get_channel(settings.DISCORD['bot_channel_id'])
    if (message.channel.id == settings.DISCORD['channel_id']
            and message.id in lst_messages
            and not message.author.bot):
        lst_messages.pop(message.id)
        msg = await bot_channel.fetch_message(lst_bot_messages[message.id])
        await msg.delete()
        lst_bot_messages.pop(message.id)


def get_details_from_message(message: str) -> tuple[str, str] | None:
    message = message.lower()

    # Modèle pour correspondre à "chapter/chapitre x.x" ou "title x.x"
    chapter_match = re.search(r'(?: -| –)?\s*(?:chapter|chapitre)\s*(\d+(?:[.,]\d+)?)', message)

    if chapter_match:
        title = message[:chapter_match.start()].strip()
    else:
        # Modèle pour correspondre à "title x.x" sans le mot "chapter/chapitre"
        title_match = re.fullmatch(r'^(.*?)\s+(\d+(?:\.\d+)?)$', message)
        if not title_match:
            return None

        title = title_match.group(1).strip()

    cleaned_title = re.sub(r'\bvol\.\d+\b', '', title).strip()
    chapter_number = chapter_match.group(1).replace(',', '.') if chapter_match else title_match.group(2).replace(',',
                                                                                                                 '.')

    return cleaned_title, chapter_number


async def process_message(message, bot_channel):
    res = get_details_from_message(message.content)
    if res:
        lst_messages.update({message.id: message.content})
        title, chapter_number = res
        comic_data = await Manganato(title).get_data(float(chapter_number))
        if not comic_data:
            bot_message = await bot_channel.send(f"**Sorry, I couldn't find '{title}' on manganato :frowning:**")
            lst_bot_messages.update({message.id: bot_message.id})
        else:
            new_chapters = comic_data['new_chapters']
            desc = '\n**List of available chapters :**\n\n' if new_chapters else 'Not any new chapters posten yet'
            nb_new_chapters = len(new_chapters)
            if nb_new_chapters > 10:
                new_chapters = new_chapters[nb_new_chapters - 10:nb_new_chapters]
                desc += "*Only 10 elements are listed at maximum*\n"
            for new_chapter in new_chapters:
                desc += f"[{new_chapter['title']}]({new_chapter['url']})\n"

            embed = discord.Embed(
                colour=discord.Colour.dark_teal(),
                description=desc,
                title=comic_data['title'],
            )
            embed.set_footer(text="Website : Manganato. Lang : EN")
            embed.set_author(name="Found on manganato", url=Manganato(title).base_url)
            embed.set_image(url=comic_data['pic_url'])
            embed_message = await bot_channel.send(embed=embed)
            lst_bot_messages.update({message.id: embed_message.id})

            return 'processed'


def get_channel(channel_id: int):
    bot_channel = client.get_channel(channel_id)
    if not bot_channel:
        # TODO
        pass
    return bot_channel

# endregion


client.run(settings.DISCORD['bot_token'])
