# Copyright (c) 2021 Jasper Harrison. This file is licensed under the terms of the Apache license, version 2.0. #
from typing import Union, Optional

import datetime
import discord
from discord.ext import commands
from sqlalchemy import (
    Column, Integer, String, Boolean, create_engine, BigInteger, DateTime, or_, ForeignKey, Float, and_
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from . import settings
from .logging import logger

Base = declarative_base()
session: Session
engine = None


class ModelBase(Base):
    __abstract__ = True

    def __init__(self, *args, **kwargs):
        super(ModelBase, self).__init__(*args, **kwargs)
    
    @classmethod
    def query(cls) -> Query:
        return session.query(cls)

    @classmethod
    def get(cls, pk) -> Optional['ModelBase']:
        return session.query(cls).get(pk)
    
    def save(self):
        session.add(self)
        session.commit()
        
    def __del__(self):
        session.delete(self)
        session.commit()


class Player(ModelBase):
    __tablename__ = 'player'
    
    id = Column(BigInteger, primary_key=True, unique=True)
    ign = Column(String, nullable=True)
    steam_name = Column(String, nullable=True)
    rung = Column(Integer, default=1)
    win_ratio = Column(Float, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    name = Column(String)
    
    def update_ratio(self):
        try:
            self.win_ratio = self.wins().count() / self.complete().count()
        except ZeroDivisionError:
            self.win_ratio = 1/1
        save()
    
    @property
    def mention(self):
        return f'<@{self.id}>'
    
    @property
    def user(self):
        return settings.bot.get_user(self.id)

    def member(self, guild):
        return guild.get_member(self.id)

    def in_game(self, game_id):
        return Game.query().filter(
            Game.id == game_id, or_(Game.host_id == self, Game.away_id == self)
        ).first() is not None

    @classmethod
    def get_by_name(cls, name_str, return_all=False, in_game_id: int = None):
        if in_game_id is not None:
            query: Query = cls.query().join(
                Game,
                and_(Game.id == in_game_id, or_(Game.host_id == Player.id, Game.away_id == Player.id))
            )
        else:
            query = cls.query()
        query: Query = query.filter(
            cls.name.ilike(f'%{name_str}%')
        ).distinct()
        return query.first() if not return_all else query
    
    def incomplete(self) -> Query:
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id) &
            Game.is_confirmed.is_(False)
        ).order_by(Game.opened_ts.desc())
    
    def complete(self) -> Query:
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id) &
            Game.is_complete.is_(True)
        ).order_by(Game.win_claimed_ts.desc())
    
    def wins(self) -> Query:
        return session.query(Game).filter(
            Game.winner_id == self.id
        ).order_by(Game.win_claimed_ts.desc())
    
    def losses(self) -> Query:
        return session.query(Game).filter(
            or_(Game.host_id == self.id, Game.away_id == self.id),
            Game.winner_id != self.id
        ).order_by(Game.win_claimed_ts.desc())
    
    @staticmethod
    def leaderboard():
        results = session.query(Player).join(Game, or_(Game.away_id == Player.id, Game.host_id == Player.id)).filter(
            Game.is_confirmed.is_(True),
            Game.win_claimed_ts > datetime.datetime.utcnow() - datetime.timedelta(days=60),
            Player.active.is_(True)
        ).order_by(Player.rung.desc(), Player.win_ratio.desc(), Player.id.asc())
        
        return results
    
    def leaderboard_rank(self):
        lb: Query = self.leaderboard()
        
        for n, player in enumerate(lb, start=1):
            player: Player
            if player == self:
                return n, lb.count()
        return 0, lb.count()
    
    def embed(self, guild: discord.Guild):
        
        embed = discord.Embed(
            description=f'__Player card for {self.mention}__'
        )
        
        embed.add_field(
            name='Results',
            value=f'Rung: {self.rung}\nW {self.wins().count()} / L {self.losses().count()}'
        )
        
        lb_rank, lb_length = self.leaderboard_rank()
        embed.add_field(
            name='Ranking',
            value=f'{lb_rank} of {lb_length}' if lb_rank != 0 else 'Unranked'
        )
        
        if self.ign:
            embed.add_field(
                name='Polytopia Game name',
                value=discord.utils.escape_markdown(self.ign)
            )
        if self.steam_name:
            embed.add_field(
                name='Steam Name',
                value=discord.utils.escape_markdown(self.steam_name)
            )
        if member := guild.get_member(self.id):
            embed.set_thumbnail(url=member.avatar_url_as(size=512))

        return embed


class Game(ModelBase):
    __tablename__ = 'game'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    name = Column(String, nullable=True)
    host_id = Column(ForeignKey(Player.id), nullable=False)
    away_id = Column(ForeignKey(Player.id), nullable=False)
    winner_id = Column(ForeignKey(Player.id), nullable=True)
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
    
    @property
    def host(self) -> Player:
        return Player.get(self.host_id)
    
    @host.setter
    def host(self, value):
        if not isinstance(value, Player):
            raise TypeError(f'value must be a player, not {value.__class__.__name__}')
        self.host_id = value.id

    @property
    def away(self) -> Player:
        return Player.get(self.away_id)

    @away.setter
    def away(self, value):
        if not isinstance(value, Player):
            raise TypeError(f'value must be a player, not {value.__class__.__name__}')
        self.away_id = value.id

    @property
    def winner(self) -> Player:
        return Player.get(self.winner_id)

    @winner.setter
    def winner(self, value):
        if not isinstance(value, Player):
            raise TypeError(f'value must be a player, not {value.__class__.__name__}')
        self.winner_id = value.id
    
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
    
    async def process_win(self):
        if not self.is_complete or not self.is_confirmed:
            return
        
        host_id, away_id = self.host_id, self.away_id
        winner_id = self.winner_id
        loser_id = away_id if host_id == winner_id else host_id
        
        winner_p: Player = self.winner
        loser_p: Player = Player.get(loser_id)
        
        # Calculate the step change
        winner_step_change = 1 if not settings.player_in_placement_matches(winner_id) else 2
        loser_step_change = -(1 if not settings.player_in_placement_matches(loser_id) else 2)
        
        self.host_step_change = winner_step_change if winner_id == host_id else loser_step_change
        self.away_step_change = winner_step_change if winner_id == away_id else loser_step_change
        
        # Calculate the new rung values
        winner_new_rung = min(winner_p.rung + winner_step_change, 12)
        loser_new_rung = max(loser_p.rung + loser_step_change, 1)

        GameLog.write(
            game_id=self.id,
            message=f'Win is confirmed and rung changes processed. {GameLog.member_string(winner_p)} goes from '
                    f'{winner_p.rung} to {winner_new_rung}. {GameLog.member_string(loser_p)} goes from {loser_p.rung} '
                    f'to {loser_new_rung}.'
        )

        winner_p.rung = winner_new_rung
        loser_p.rung = loser_new_rung
        
        save()
        logger.info(f'Game {self.id} - win confirmed, rung changes processed. ')
        
        winner_p.update_ratio()
        loser_p.update_ratio()
    
    def embed(self, guild):
    
        host, away = self.host, self.away
        embed = discord.Embed(
            title=f'Game {self.id}   '
                  f'{host.name} vs '
                  f'{away.name}'
                  f'\u00a0*{self.name}*')
        
        if self.is_complete:
            if winner := guild.get_member(self.winner_id):
                embed.set_thumbnail(url=winner.avatar_url_as(size=512))
            embed.title = embed.title + f'\n\nWINNER{" (Unconfirmed)" if not self.is_confirmed else ""}: ' \
                                        f'{self.winner.name}'
        
        embed.add_field(
            name=f'__{host.name}'
                 f'{" ({})".format(nick) if (nick := getattr(host.member(guild), "nick", None)) else ""}__',
            value=f'Rung: {self.host_step}',
            inline=True
        )
        
        # Separator
        embed.add_field(name='\u200b', value='\u200b', inline=False)
        
        embed.add_field(
            name=f'__{away.name}'
                 f'{" ({})".format(nick) if (nick := getattr(away.member(guild), "nick", None)) else ""}__',
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
    
    @classmethod
    async def convert(cls, ctx, game_id):
        try:
            game_id = int(game_id)
        except Exception:
            await ctx.send(
                f'Unable to convert "{game_id}" to a number.',
                allowed_mentions=discord.AllowedMentions(users=False, roles=False)
            )
            raise commands.UserInputError()
        game = cls.get(game_id)
        if not game:
            await ctx.send(f'Unable to find game with ID {game_id}')
            raise commands.UserInputError()
        return game


class Signup(ModelBase):
    __tablename__ = 'signup'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    signup_id = Column(ForeignKey('signupmessage.id'), nullable=False)
    player_id = Column(ForeignKey(Player.id), nullable=False)
    mobile = Column(Boolean, default=True, nullable=False)

    @property
    def signup(self) -> 'SignupMessage':
        return SignupMessage.get(self.signup_id)

    @signup.setter
    def signup(self, value):
        if not isinstance(value, Player):
            raise TypeError(f'value must be a player, not {value.__class__.__name__}')
        self.signup_id = value.id

    @property
    def player(self) -> 'Player':
        return Player.get(self.player_id)

    @player.setter
    def player(self, value):
        if not isinstance(value, Player):
            raise TypeError(f'value must be a player, not {value.__class__.__name__}')
        self.player_id = value.id


class SignupMessage(ModelBase):
    __tablename__ = 'signupmessage'

    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    message_id = Column(BigInteger, unique=True, nullable=False)
    is_open = Column(Boolean, nullable=False)
    close_at = Column(DateTime, nullable=True)


class GameLog(ModelBase):
    __tablename__ = 'gamelog'
    
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    message = Column(String, nullable=True)
    message_ts = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    
    @staticmethod
    def member_string(member: Union[discord.Member, discord.User, Player]):

        try:
            # discord.Member API object
            name = member.display_name
            d_id = member.id
        except AttributeError:
            # discord.User API object/Player DB instance
            name = member.name
            d_id = member.id
        return f'**{discord.utils.escape_markdown(name)}** (`{d_id}`)'
    
    @classmethod
    def write(cls, message, game_id: int = 0):
        obj = cls(message=f'__{game_id}__ - {message}')
        obj.save()
    
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
