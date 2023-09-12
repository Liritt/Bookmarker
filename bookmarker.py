import asyncio
import re

import discord
from discord.ext import commands
from discord.ui import Select, View, RoleSelect

import settings
from collector import Manganato
from database import insert_new_comic

intents = discord.Intents.all()
lst_messages = {}
lst_bot_messages = {}

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    """
    channel = bot.get_channel(settings.DISCORD['channel_id'])
    bot_channel = bot.get_channel(settings.DISCORD['bot_channel_id'])
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
@bot.event
async def on_message(message):
    bot_channel = get_channel(settings.DISCORD['bot_channel_id'])
    if (message.channel.id == settings.DISCORD['channel_id']
            and 'Marqueur' in [role.name for role in message.author.roles]
            and not message.author.bot):
        await process_message(message, bot_channel)

    await bot.process_commands(message)


@bot.event
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


@bot.event
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
    bot_channel = bot.get_channel(channel_id)
    if not bot_channel:
        # TODO
        pass
    return bot_channel

# endregion


@bot.command(name="bookmarker_setup")
async def bookmarker_setup(ctx):
    await ctx.send("Hello! I am Bookmarker, the bot able to get the latest chapters of your favorite mangas!")

    guild = bot.get_guild(ctx.guild.id)
    text_channels = guild.text_channels
    options_readable_channels = [discord.SelectOption(label=text_channel.name) for text_channel in text_channels if text_channel.permissions_for(guild.me).read_messages]

    async def readable_channels_callback(interaction):
        if len(interaction.data['values']) > 1:
            await interaction.response.send_message(f"Understood! From now on, I'll watch the following channels: {', '.join(interaction.data['values'])}")
        else:
            await interaction.response.send_message(f"Understood! From now on, I'll watch channel \"{interaction.data['values'][0]}\"")

    select = Select(max_values=len(options_readable_channels), options=options_readable_channels, custom_id="readable_channels")
    select.callback = readable_channels_callback

    user_channels = View()
    user_channels.add_item(select)
    await ctx.send("Select the channel where you want to receive the updates", view=user_channels)

    async def roles_callback(interaction):
        await interaction.response.send_message(f"Ok, I'll only read messages from users that has the chosen role(s).")
    roles = RoleSelect(max_values=len(ctx.guild.roles))
    roles.callback = roles_callback
    roles_view = View()
    roles_view.add_item(roles)
    await ctx.send("Now, select which roles must a user have so that I read his messages", view=roles_view)

    options_writable_channels = [discord.SelectOption(label=text_channel.name) for text_channel in text_channels if text_channel.permissions_for(guild.me).send_messages]

    async def writable_channels_callback(interaction):
        await interaction.response.send_message(f"Understood! From now on, I'll send updates in channel \"{interaction.data['values'][0]}\"")

    select = Select(options=options_writable_channels, custom_id="writable_channels")
    select.callback = writable_channels_callback

    bot_channel = View()
    bot_channel.add_item(select)
    await ctx.send("Now, select the channel where you want me to write when I get updates on a manga", view=bot_channel)


bot.run(settings.DISCORD['bot_token'])
