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

@bot.command()
async def setup(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You must be an administrator to use this command")
        return

    channels_to_write = []
    channels_to_read = []
    allowed_roles = []
    write_select_options = []
    for channel in ctx.guild.channels:
        if isinstance(channel, discord.TextChannel) and channel.permissions_for(ctx.guild.me).send_messages:
            write_select_options.append(discord.SelectOption(label=channel.name, value=str(channel.id)))

    async def write_select_callback(interaction):
        nonlocal channels_to_write
        channels_to_write = [ctx.guild.get_channel(int(option)) for option in interaction.data['values']]
        write_select.disabled = True
        await interaction.response.edit_message(view=write_select_view)
        write_select_view.stop()

    write_select = Select(options=write_select_options, max_values=len(write_select_options))
    write_select.callback = write_select_callback

    write_select_view = View()
    write_select_view.add_item(write_select)
    await ctx.send("Select the channel where you want me to write when I get updates on a manga", view=write_select_view)
    timeout = await write_select_view.wait()
    if not timeout:
        read_select_options = []
        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel) and channel.permissions_for(ctx.guild.me).read_messages:
                read_select_options.append(discord.SelectOption(label=channel.name, value=str(channel.id)))

        async def read_select_callback(interaction):
            nonlocal channels_to_read
            channels_to_read = [ctx.guild.get_channel(int(option)) for option in interaction.data['values']]
            read_select.disabled = True
            await interaction.response.edit_message(view=read_select_view)
            read_select_view.stop()

        read_select = Select(options=read_select_options, max_values=len(read_select_options))
        read_select.callback = read_select_callback

        read_select_view = View()
        read_select_view.add_item(read_select)
        await ctx.send("Select the channel where I can read messages", view=read_select_view)
        timeout = await read_select_view.wait()
        if not timeout:
            role_select_options = []
            for role in ctx.guild.roles:
                role_select_options.append(discord.SelectOption(label=role.name, value=str(role.id)))

            async def role_select_callback(interaction):
                nonlocal allowed_roles
                allowed_roles = [ctx.guild.get_role(int(option)) for option in interaction.data['values']]
                role_select.disabled = True
                await interaction.response.edit_message(view=role_select_view)
                role_select_view.stop()

            role_select = Select(options=role_select_options, max_values=len(role_select_options))
            role_select.callback = role_select_callback

            role_select_view = View()
            role_select_view.add_item(role_select)
            await ctx.send("Select the roles that a user must have so that I read his messages", view=role_select_view)

            timeout = await role_select_view.wait()
            if not timeout:
                await ctx.send(f"Configuration enregistrée ! \n"
                               f"Channels pour écrire : {', '.join([channel.mention for channel in channels_to_write])}\n"
                               f"Channels pour lire : {', '.join([channel.mention for channel in channels_to_read])}\n"
                               f"Rôles autorisés : {', '.join([role.mention for role in allowed_roles])}")


bot.run(settings.DISCORD['bot_token'])
