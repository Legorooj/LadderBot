# Copyright (c) 2020 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
import os

import discord
from discord.ext import commands

from ladderbot import db, settings
from ladderbot.logging import logger


class Admin(commands.Cog):
    
    def __init__(self, bot: commands.Bot, conf: dict):
        self.bot = bot
        self.conf = conf
    
    @commands.Cog.listener()
    async def on_ready(self):
        s = f'Online. Logged in as {self.bot.user.name}/{self.bot.user.id}, PID {os.getpid()}'
        print(s)
        logger.info(s)
    
    @commands.command(aliases=['restart'])
    @commands.is_owner()
    async def quit(self, ctx: commands.Context):
        db.session.close()
        logger.info('Shutting down.')
        await ctx.send('Shutting down...')
        await self.bot.close()
    
    @commands.command()
    @commands.is_owner()
    async def clear_signupmessages(self, ctx):
        db.session.query(db.SignupMessage).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command()
    @commands.is_owner()
    async def clear_players(self, ctx):
        db.session.query(db.Player).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command()
    @commands.is_owner()
    async def clear_signups(self, ctx):
        db.session.query(db.Signup).delete()
        db.save()
        await ctx.send('Cleared.')
    
    @commands.command()
    @commands.is_owner()
    async def delete(self, ctx: commands.Context, game: settings.GameLoader, *, args: str = None):
        """*Owner*: delete an in progress/yet to be started game"""
        game: db.Game
        args = args or ''
    
        if not game:
            return await ctx.send('Game ID not provided.')
        
        if game.is_complete and '-override' not in args.lower():
            return await ctx.send(f'Please unwin the game first.')
        
        db.delete(game)
        
        logger.info(f'Game {game.id} deleted.')
        
        await ctx.send(f'Game {game.id} deleted.')
    
    @commands.command()
    @settings.is_mod_check()
    async def confirm(self, ctx: commands.Context, game: settings.GameLoader):
        pass


def setup(bot, conf):
    bot.add_cog(Admin(bot, conf))
