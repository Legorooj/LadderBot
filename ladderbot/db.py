# Copyright (c) 2020 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
from sqlalchemy import Column, Integer, String, Boolean, create_engine, BigInteger, DateTime, or_
from sqlalchemy.orm import Session, Query
from sqlalchemy.ext.declarative import declarative_base
import datetime
from discord.ext import commands

from . import settings

import discord

Base = declarative_base()
session: Session
engine = None


class Player(Base):
    __tablename__ = 'player'
    
    id = Column(BigInteger, primary_key=True, unique=True)
    ign = Column(String, nullable=True)
    steam_name = Column(String, nullable=True)
    rung = Column(Integer, default=1)
    
    @property
    def mention(self):
        return f'<@{self.id}>'
    
    def incomplete(self):
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id) &
            Game.is_confirmed.is_(False)
        ).order_by(Game.opened_ts.desc())
    
    def complete(self):
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id) &
            Game.is_complete.is_(True)
        ).order_by(Game.win_claimed_ts.desc())
    
    def wins(self):
        return session.query(Game).filter(
            Game.winner_id == self.id
        ).order_by(Game.win_claimed_ts.desc())
    
    def losses(self):
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id)
        ).filter(Game.winner_id != self.id).order_by(Game.win_claimed_ts.desc())


class Game(Base):
    __tablename__ = 'game'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    name = Column(String, nullable=True)
    host_id = Column(BigInteger, nullable=False)
    away_id = Column(BigInteger, nullable=False)
    winner_id = Column(BigInteger, nullable=True)
    is_started = Column(Boolean, default=False)
    is_complete = Column(Boolean, default=False)
    is_confirmed = Column(Boolean, default=False)
    host_step = Column(Integer, nullable=False)
    away_step = Column(Integer, nullable=False)
    host_step_change = Column(Integer, nullable=True)
    away_step_change = Column(Integer, nullable=True)
    step = Column(Integer, nullable=False)
    win_claimed_ts = Column(DateTime, nullable=True)
    mobile = Column(Boolean, nullable=False)
    opened_ts = Column(DateTime, nullable=False)
    started_ts = Column(DateTime, nullable=True)
    win_claimed_by = Column(BigInteger, nullable=True)
    host_switched = Column(Boolean, nullable=False, default=False)
    
    def win_unconfirmed(self, player_id: int, claimed_by: int):
        self.winner_id = player_id
        self.win_claimed_by = claimed_by
        self.win_claimed_ts = datetime.datetime.utcnow()
        self.is_complete = True
        self.is_confirmed = False
        
        save()
    
    def win_confirmed(self, player_id: int):
        self.winner_id = player_id
        if not self.win_claimed_ts:
            self.win_claimed_ts = datetime.datetime.utcnow()
        self.is_complete = True
        self.is_confirmed = True
        self.win_claimed_by = None
        
        save()
    
    async def process_win(self, ctx):
        if not self.is_complete or not self.is_confirmed:
            return
        
        # Load the player and member objects
        host, away = ctx.guild.get_member(self.host_id), ctx.guild.get_member(self.away_id)
        winner: discord.Member = host if host.id == self.winner_id else away
        loser: discord.Member = away if host.id == self.winner_id else host
        
        winner_p: Player = session.query(Player).get(winner.id)
        loser_p: Player = session.query(Player).get(loser.id)
        
        # Calculate the step change
        winner_step_change = 1 if not settings.player_in_placement_matches(winner.id) else 2
        loser_step_change = -(1 if not settings.player_in_placement_matches(winner.id) else 2)
        
        self.host_step_change = winner_step_change if winner.id == host.id else loser_step_change
        self.away_step_change = winner_step_change if winner.id == away.id else loser_step_change
        
        # Calculate the new rung values
        winner_new_rung = min(winner_p.rung + winner_step_change, 12)
        loser_new_rung = max(loser_p.rung + loser_step_change, 1)
        
        winner_p.rung = winner_new_rung
        loser_p.rung = loser_new_rung

        GameLog.write(
            game_id=self.id,
            message=f'Win is confirmed and rung changes processed'
        )
        
        save()
    
    def embed(self, guild):
    
        host: discord.Member = guild.get_member(self.host_id)
        away: discord.Member = guild.get_member(self.away_id)
        
        embed = discord.Embed(
            title=f'Game {self.id}   '
                  f'{host.name}{" ({})".format(host.nick) if host.nick else ""} vs '
                  f'{away.name}{" ({})".format(away.nick) if away.nick else ""}'
                  f'\u00a0*{self.name}*')
        
        if self.is_complete:
            winner: discord.Member = guild.get_member(self.winner_id)
            embed.title = embed.title + f'\n\nWINNER{" (Unconfirmed)" if not self.is_confirmed else ""}: {winner.name}'
            embed.set_thumbnail(url=winner.avatar_url_as(size=512))
    
        embed.add_field(
            name=f'__{host.name}{" ({})".format(host.nick) if host.nick else ""}__',
            value=f'Rung: {self.host_step}',
            inline=True
        )
        
        # Separator
        embed.add_field(name='\u200b', value='\u200b', inline=False)
        
        embed.add_field(
            name=f'__{away.name}{" ({})".format(away.nick) if away.nick else ""}__',
            value=f'Rung: {self.away_step}',
            inline=True
        )
        
        status_str = (
            'Not started' if not self.is_started else
            'Incomplete' if self.is_started and not self.is_complete else
            'Unconfirmed' if self.is_complete and not self.is_confirmed else
            'Completed'
        )
        completed_str = f' - Completed {self.win_claimed_ts.strftime("%Y-%m-%d %H:%M:%S")}' if self.is_complete else ''
        
        embed.set_footer(
            text=f'{self.platform_emoji} {status_str} - Created {self.opened_ts.strftime("%Y-%m-%d %H:%M:%S")}'
                 f'{completed_str}{" - Hosted by "+host.name[:20]}'
        )
        
        return embed
    
    @property
    def platform_emoji(self):
        return '' if self.mobile else '🖥'


class Signup(Base):
    __tablename__ = 'signup'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    signup_id = Column(Integer, nullable=False)
    player_id = Column(BigInteger, nullable=False)
    mobile = Column(Boolean, default=True, nullable=False)


class SignupMessage(Base):
    __tablename__ = 'signupmessage'

    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    message_id = Column(BigInteger, unique=True, nullable=False)
    is_open = Column(Boolean, nullable=False)
    close_at = Column(DateTime, nullable=True)


class GameLog(Base):
    __tablename__ = 'gamelog'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    message = Column(String, nullable=True)
    message_ts = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    
    @staticmethod
    def member_string(member):

        try:
            # discord.Member API object
            name = member.display_name
            d_id = member.id
        except AttributeError:
            # local discordmember database entry
            name = member.name
            d_id = member.discord_id
        return f'**{discord.utils.escape_markdown(name)}** (`{d_id}`)'
    
    @classmethod
    def write(cls, message, game_id: int = 0):
        obj = cls(message=f'__{game_id}__ - {message}')
        add(obj)
    
    @classmethod
    def search(cls, keywords: str = None, negative_keyword: str = None, limit: int = 500):
        if not keywords:
            keywords = '%'
        else:
            keywords = f'%{keywords.replace(" ", "%")}%'
        
        if not negative_keyword:
            negative_keyword = 'thiswillnevershowupinthelogs'
        else:
            negative_keyword = f'%{negative_keyword}%'
            
        return session.query(GameLog).filter(
            GameLog.message.ilike(keywords),
            ~GameLog.message.ilike(negative_keyword)
        ).order_by(GameLog.message_ts.desc()).limit(limit)


def setup(conf):
    global engine
    global session
    user, password = conf['DEFAULT']['psql_user'], conf['DEFAULT']['psql_password']
    engine = create_engine(
        f'postgresql://{user}:{password}@localhost/polyladder')
    session = Session(bind=engine)


def add(obj):
    session.add(obj)
    session.commit()


def delete(obj):
    session.delete(obj)
    session.commit()
    

def save():
    session.commit()
