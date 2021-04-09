'''

General things to add:
    maybe make a custom help/advanced help
    handle the draw case
'''
#discord imports
import discord
from discord.ext import commands
import asyncio
#general system imports
import os
import sys
import re
from datetime import datetime,timedelta
import requests
import mariadb
from dotenv import load_dotenv
#local imports
import dchess

load_dotenv()
#if arg log is sent when running, then output should be put into a log file
if len(sys.argv) >= 2 and sys.argv[1] == "log":
    sys.stdout = sys.stderr = open('logfile.log', 'a')

#connect to the database
try:
    CONN = mariadb.connect(user=os.getenv("DB_USER"),password=os.getenv("DB_PASS"),host=os.getenv("DB_IP"),port=int(os.getenv("DB_PORT")),database=os.getenv("DB_DB"))
    if CONN.autocommit is False:
        CONN.autocommit = True
    CUR = CONN.cursor()
except mariadb.Error as e:
    print("Cannot connecto the the database")


#called when a command is being processed, fetches the custom command for the server
async def _determine_prefix(bot,msg):
    user_id = bot.user.id
    base = [f'<@!{user_id}>',f'<@{user_id}>']
    if msg.guild is None:
        base.append('')
        return base
    elif CUR is None:
        base.append('|')
        return base
    else:
        CUR.execute(f'select Command from GuildCommand where GuildID={msg.guild.id}')
        prefix = CUR.fetchone()
        if prefix is None:
            base.append('|')
            return base
        else:
            base.append(prefix[0])
            return base


#used for bot init
help = commands.DefaultHelpCommand(no_category='Commands')
desc = "Bot that lets users play chess against each other."
#client = commands.Bot(command_prefix=_determine_prefix, description=desc, help_command=help)


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=_determine_prefix, description=desc, heartbeat_timeout=150.0)
        self.CONN = None
        self.CUR = None
        self.load_db()
        self.load_extension("dchess")

    def load_db(self):
        #connect to the database
        try:
            self.CONN = mariadb.connect(user=os.getenv("DB_USER"),password=os.getenv("DB_PASS"),host=os.getenv("DB_IP"),port=int(os.getenv("DB_PORT")),database=os.getenv("DB_DB"))
            if self.CONN.autocommit is False:
                self.CONN.autocommit = True
            self.CUR = CONN.cursor()
        except mariadb.Error as e:
            print("Cannot connecto the the database")


    async def on_ready(self):
        print(f'Logged in as {self.user}!')
        await self.change_presence(activity = discord.Game("Chess"))

    #this should log instead of printing, learn log
    async def on_guild_join(self, guild):
        print("joined new guild", guild, guild.id)

    #
    async def on_message(self, m):
        if m.author == self.user:
            return
        await self.process_commands(m)

    #Starts the bot
    def run(self):
        try:
            super().run(os.getenv("DISCORD_TOKEN"), reconnect=True)
        finally:
            print("Could not start")


#Run
bot = DiscordBot()
bot.run()
