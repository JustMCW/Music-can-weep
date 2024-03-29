import discord
from discord.ext import commands

async def setup(*_): pass

class MCWHelpCommand(commands.HelpCommand):

    def get_params(self,cmd:commands.Command) -> list:

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
        channel = self.get_destination()
        description = "\n".join([f'**{cog.qualified_name.replace("_"," ")}**\n{", ".join(f"`{cmd.name}`" for cmd in cog.get_commands())}\n' for cog in mapping if cog is not None and len(cog.get_commands()) != 0 and "admin" not in cog.qualified_name.lower()])

        await channel.send(embed= discord.Embed(title="🎶 This is a simple music bot ~",
                                                description = f"Run `{self.context.prefix}help command` for more infomation about that command\n\n"+description,
                                                color = discord.Color.from_rgb(255,255,255)).set_footer(text="bot made by MCW"))
        
    async def send_command_help(self, command:commands.Command):
        channel = self.get_destination()

        aliases = f"\n\nAlternatives : `{'`, `'.join(command.aliases)}`" if command.aliases else ""
        description = command.description or "No description"
        params ='\n\nArguments : `'+'`, `'.join([p for p in self.get_params(command) if not p.startswith("_")])+'`' if command.clean_params else ""
        usage = command.usage.format(self.context.prefix) if command.usage else f"{self.context.prefix}{command.qualified_name}"

        await channel.send(embed= discord.Embed(
            title=f"🌟 Usage of command : {command.qualified_name}",
            description = f"{description}{params}{aliases}\n\n**Examples:**\n{usage}",
            color = discord.Color.from_rgb(255,255,255))
        )

    async def send_group_help(self, group:commands.Group):
        channel = self.get_destination()

        if group.usage == None:
            raise RuntimeError(f"Group {group.name} lacked a usuage description, give it one.")
        
        await channel.send(embed= discord.Embed(
            title=f"🌟 Usage of group command : {group.qualified_name} ",
            description =f"{group.description}\n\nCommands for this group : `{'`, `'.join([cmd.name for cmd in list(group.walk_commands())])}`\n\n**Examples:**\n{group.usage.format(self.context.prefix)}",
            color = discord.Color.from_rgb(255,255,255)
        ))
