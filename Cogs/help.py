import discord
from discord.ext import commands

class MCWHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__()

    def get_params(self,cmd:commands.Command) -> list[str]:

        result:list[str] = []

        for pname,pvalue in cmd.clean_params.items():
            if "**" in str(pvalue):
                continue
            if "=" in str(pvalue):
                result.append(pname+" (optional)")
            else:
                result.append(pname)
                
        return result

    async def send_bot_help(self, mapping):
        channel:discord.DMChannel = self.get_destination()
    
        description = "\n".join([f'**{cog.qualified_name.replace("_"," ")}**\n{", ".join(f"`{cmd.name}`" for cmd in cog.get_commands())}\n' for cog in mapping if cog is not None and len(cog.get_commands()) != 0 and cog.name != "bot_admin_commands"])

        await channel.send(embed= discord.Embed(title="🎶 This is a simple music bot ~",
                                                description = f"Run `{self.clean_prefix}help command` for more infomation about that command\n\n"+description,
                                                color = discord.Color.from_rgb(255,255,255)).set_footer(text="made by MCW 🥞#9722"))
        
    async def send_command_help(self, command:commands.Command):
        channel:discord.DMChannel = self.get_destination()

        aliases = f"\n\nAlternatives : `{'`, `'.join(command.aliases)}`" if command.aliases else ""
        description = command.description or "No description"
        params ='\n\nArguments : `'+'`, `'.join(self.get_params(command))+'`' if command.clean_params else ""

        await channel.send(embed= discord.Embed(title=f"🌟 Usage of command : {command.qualified_name}",
                                                description = f"{description}{params}{aliases}\n\n**Examples:**\n{command.usage.format(self.clean_prefix)}",
                                                color = discord.Color.from_rgb(255,255,255)))

    async def send_group_help(self, group:commands.Group):
        channel:discord.DMChannel = self.get_destination()
        
        await channel.send(embed= discord.Embed(title=f"🌟 Usage of group command : {group.qualified_name} ",
                                                description =f"{group.description}\n\nCommands for this group : `{'`, `'.join([cmd.name for cmd in list(group.walk_commands())])}`\n\n**Examples:**\n{group.usage.format(self.clean_prefix)}",
                                                color = discord.Color.from_rgb(255,255,255)))
    
def setup(*_):
    pass