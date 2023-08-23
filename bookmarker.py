import discord

import settings

intents = discord.Intents.all()
client = discord.Client(intents=intents)
lst_messages = {}


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    channel = client.get_channel(settings.DISCORD['channel_id'])
    async for message in channel.history(limit=1000):
        if 'Marqueur' in [role.name for role in message.author.roles]:
            lst_messages.update({message.id: message.content})
    print(len(lst_messages))


@client.event
async def on_message(message):
    if message.channel.id == settings.DISCORD['channel_id'] and 'Marqueur' in [role.name for role in message.author.roles]:
        lst_messages.update({message.id: message.content})


@client.event
async def on_message_edit(before, after):
    if before.channel.id == settings.DISCORD['channel_id'] and 'Marqueur' in [role.name for role in after.author.roles]:
        lst_messages.update({before.id: after.content})


@client.event
async def on_message_delete(message):
    if message.channel.id == settings.DISCORD['channel_id'] and message.id in lst_messages:
        lst_messages.pop(message.id)


client.run(settings.DISCORD['bot_token'])
