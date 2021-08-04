# Copyright (c) 2021 Jasper Harrison. This file is licensed under the terms of the Apache license, version 2.0. #
import traceback
from configparser import ConfigParser
import pathlib
import os

import discord
from discord.ext import commands

from ladderbot import matchmaking, admin, db, settings, league, help as l_help
from ladderbot.logging import logger

conf = ConfigParser()
conf.read(pathlib.Path(__file__).parent / 'config.ini')

settings.owner_id = conf['DEFAULT']['owner_id']

intents = discord.Intents.default()
intents.members = True
intents.reactions = True

am = discord.AllowedMentions(everyone=False)

bot = commands.Bot(command_prefix='$', intents=intents, allowed_mentions=am)
settings.bot = bot
settings.conf = conf
settings.server_id = int(conf['DEFAULT']['server_id'])


@bot.event
async def on_command_error(ctx, exc):
    if hasattr(ctx.command, 'on_error'):
        return
    ignored = (commands.CommandNotFound, commands.UserInputError, commands.CheckFailure)
    if isinstance(exc, ignored):
        logger.warning(f'Exception on ignored list raised in {ctx.command}. {exc}')
        return
    else:
        exception_str = ''.join(traceback.format_exception(etype=type(exc), value=exc, tb=exc.__traceback__))
        logger.critical(f'Ignoring exception in command {ctx.command}: {exc} {exception_str}', exc_info=True)
        await ctx.send(f'Unhandled error (notifying <@{settings.owner_id}>): {exc}')


cooldown = commands.CooldownMapping.from_cooldown(6, 30.0, commands.BucketType.user)


@bot.check
async def block_dms(ctx):
    return ctx.guild is not None


@bot.check
async def cooldown_check(ctx):
    if ctx.invoked_with == 'help' and ctx.command.name != 'help':
        # Check will run once for every command in the bot if someone calls $help, so exclude it.
        return True
    if ctx.author.id == settings.owner_id:
        return True
    bucket = cooldown.get_bucket(ctx.message)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        await ctx.send('You\'re on cooldown. Slow down those commands!')
        logger.warning(f'Cooldown limit reached for user {ctx.author.id}')
        return False
    return True


matchmaking.setup(bot, conf)
admin.setup(bot, conf)
league.setup(bot, conf)
l_help.setup(bot)
db.setup(conf)

bot.run(conf['DEFAULT']['discord_token'], bot=True, reconnect=True)
