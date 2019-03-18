from discord.ext import commands
from discord.ext.commands import Bot
from discord.ext.commands import MemberConverter
from discord import Status
import discord
import asyncio
import json

GROUP_FILE = 'groupsData.json'
groupDataHasChanged = False
isLoaded = False

RESERVED_WORDS = ['group','groups','all']
TICK_RATE = 1

groupData = {}

#temp = test['group']['group1']['members']

#groupsJSON = {groupName: {desc:desc, members: [list]}}

# members: [listOfMembers]
# groupName: {description, members}

class GroupManager(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        readGroupData()
        

    @commands.command(name='jsdump', hidden=True)
    async def dump(self, context):
        print(groupData)
        writeGroupData()

    # Return full list of all groups with member count (short descr too?)
    @commands.command(name='list',
                    description='List all groups. To see members of a specific group, include the group name.',
                    brief='List all groups, or members of a group.',
                    aliases=['ls'],
                    invoke_without_command=True,
                    rest_is_raw=True,
                    pass_context=True
                    )
    async def listGroupsCommand(self, context, groupName=None):
        messageToSend = ''
        if (groupName is None) or (groupName is RESERVED_WORDS) or (groupName not in groupData):
            messageToSend += 'There are currently ' + str(len(groupData)) + ' groups on PWPG!\n'
            for name in groupData:
                messageToSend += name + ': ' + groupData[name]['description'] + '\n\tMembers: ' + str(len(groupData[name]['member'])) + '\n'
        elif groupName in groupData:
            messageToSend += groupName + ' has ' + str(len(groupData[groupName]['member'])) + ' members.\n' + groupData[groupName]['description'] + '\n'
            for m in groupData[groupName]['member']:
                messageToSend += str(m) + '\n'
        else:
            print('how did this even happen?')
            messageToSend += 'THIS SHOULD NOT BE SEEN!?'

        await context.send('```' + messageToSend + '```')
    
    # TODO docs and command params
    @commands.command(name='members',
                    hidden=True,
                    pass_context=True
                    )
    async def listGroupMembersCommand(self, context, groupName):
        if groupName in groupData:
            print ('print shit for a group')
        else: print ('no group')

    # Joins an existing group and writes to file
    # TODO error calls?
    @commands.command(name='sub',
                    description='Subscribe to a group. Belonging '+
                    'to a group will include you in pings.\n'+
                    'Use [list] to find existing groups.',
                    brief='Subscribe to a group.',
                    aliases=['subscribe','join'],
                    rest_is_raw=True,
                    pass_context=True
                    )
    async def joinGroupCommand(self, context, groupName, offlinePing=True):
        if joinGroup(context, groupName, offlinePing):
            await context.send('`'+ str(context.author) + '` has been added to `' + groupName + '`')
        else:
            await context.send('`'+ str(context.author) + '` could not be added to `' + groupName + '`')

    # Leaves a group the user is a member of
    @commands.command(name='unsub',
                    description='Unsubscribe from a group that you are a part of. Removes you from future '+
                    'pings and notifications for this group.',
                    brief='Unsubscribe from a group.',
                    aliases=['unsubscribe', 'leave'],
                    rest_is_raw=True,
                    pass_context=True
                    )
    async def leaveGroupCommand(self, context, groupName):
        if leaveGroup(context, groupName):
            await context.send('`' + str(context.author) + '` has left `' + groupName + '`')
        else:
            await context.send('`' + str(context.author) + '` could not leave `' + groupName + '`')

    # Ping a group with an optional message
    # Check if user is online, consult property
    @commands.command(name='ping',
                    description='Ping a group. Pinging sends a single message to all users in a group. '+
                    'Include an optional message for the ping.',
                    brief='Ping a group',
                    aliases=['poke'],
                    invoke_without_command=True,
                    pass_context=True
                    )
    async def pingGroupCommand(self, context, groupName, *, optionalMessage=None):
        if groupName in groupData:
            m = MemberConverter()
            
            # Assemble message to send.
            messageToSend = '`' + str(context.author) + '` has pinged `' + groupName + '`.'
            if optionalMessage is not None:
                messageToSend += '\n' + optionalMessage

            # For each member in the group,
            # check user status and preference for offline ping
            # send the message if online or wants offline pings
            for u in groupData[groupName]['member']:
                user = await m.convert(context, u)
                if groupData[groupName]['member'][u].get('offlinePing') or (user.status is Status.online or user.status is Status.idle):
                    await user.send(messageToSend)
                else:
                    print('no offline ping and they aren\'t online')
            return True
        else:
            print('ping error -> no group')
            return False

    # Creates a non-existing group
    # Write to GROUP_FILE
    @commands.command(name='create',
                    description='Make a group and add yourself to it. Add a short description of the group after the name. Groups can be pinged using [ping] <groupName>.',
                    brief='Create a group',
                    aliases=['make'],
                    pass_context=True
                    )
    async def createGroupCommand(self, context, groupName, *, description=None):
        if addGroup(context, groupName, description):
            await context.send('Group `' + groupName + '` has been created.')
        else:
            print('create group failed')

    # Deletes an existing group
    # Write to GROUP_FILE
    @commands.command(name='delete',
                    description='Removes an existing group. Confirmation is not implemented yet.',
                    brief='Remove a group',
                    aliases=['remove', 'del', 'rm'],
                    hidden=True,
                    pass_context=True
                    )
    async def deleteGroupCommand(self, context, groupName):
        if removeGroup(groupName):
            await context.send('Group `' + groupName + '` has been deleted.')
        else:
            print('delete group failed')

    # Edits an existing group's description
    @commands.command(name='edit',
                    description='Edit an existing group\'s description. No quotations are needed.',
                    brief='Edit a group description',
                    aliases=['editgroup', 'editdesc'],
                    pass_context=True
                    )
    async def editGroupDescriptionCommand(self, context, groupName, *, description=None):
        if description is None:
            if editGroupDescription(groupName, 'No Description'):
                await context.send('The description for `' + groupName + '` has been removed.')
        else:
            if editGroupDescription(groupName, description):
                await context.send('The description for `' + groupName + '` has been updated.')

# Main loop for the Group Manager to operate under
# Checks for changes to the groupData and writes when needed
async def groupManagerLoop(tickRate: int):
    while (isLoaded):
        if writeGroupData(): continue
        await asyncio.sleep(tickRate)

# Update data bool
# Simple helper
def signalForGroupDataUpdate(v: bool):
    global groupDataHasChanged
    groupDataHasChanged = v
    return groupDataHasChanged

# Create a group entry with an optional name
# Returns false if group exists
# TODO error throws
def addGroup(context, name: str, description=None):
    global groupData
    if name in groupData:
        print('group exists -> throw error')
        return False
    else:
        if description is None: description='No Description'
        groupData[name] = {'member':{}, 'description': description}
        joinGroup(context, name)
        signalForGroupDataUpdate(True)
        return True

# Removes entire entry for a group
# Returns false if group doesn't exist
# TODO error throws
def removeGroup(name: str):
    global groupData
    if name in groupData.keys():
        groupData.pop(name)
        signalForGroupDataUpdate(True)
        return True
    else:
        print('group doesn\'t exist -> throw error')
        return False

# Edits an existing group's description
# Returns false if the group doesn't exist
# TODO error throws
def editGroupDescription(name: str, description: str):
    global groupData
    if name in groupData:
        groupData[name]['description'] = description
        signalForGroupDataUpdate(True)
        return True
    else:
        print('group doesn\'t exist -> throw error')
        return False

# Add author to a group
# Returns false if no matching group name or in group already
# TODO error throws
def joinGroup(context, name: str, offlinePing=True):
    global groupData
    userProps = {'offlinePing': offlinePing}
    if name in groupData:
        if str(context.author) in groupData[name]['member']:
            print('user already in group -> throw error')
            return False
        groupData[name]['member'][str(context.author)] = userProps
        signalForGroupDataUpdate(True)
        return True
    else:
        print('group doesn\'t exist -> throw error')
        return False

# Remove author from a group
# Returns false if not in the group, or if the group doesn't exist
# TODO error throws
def leaveGroup(context, name: str):
    global groupData
    if name in groupData:
        if str(context.author) in groupData[name]['member']:
            groupData[name]['member'].pop(str(context.author))
            signalForGroupDataUpdate(True)
            return True
        else:
            print ('not in this group')
            return False
    else:
        print ('group doesn\'t exist -> throw error')
        return False

# Replace user properties for a group with dictionary
# Returns false if already in group or no matching group
# TODO throw error if no dict provided (missing arg)
# TODO error throws
def updateUserGroupProperties(context, name: str, properties: dict):
    global groupData
    if name in groupData:
        if str(context.author) in groupData[name]['member']:
            print('throw error, already in group')
            return False
        groupData[name]['member'] = {str(context.author): properties}
        signalForGroupDataUpdate(True)
        return True
    else:
        print('group no exist -> throw error')
        return False

# Write groupData dict to GROUP_FILE, return True if sucessful
# Writes every TICK_RATE inside groupManagerLoop(int)
def writeGroupData():
    if groupDataHasChanged:
        with open(GROUP_FILE, 'w') as f:
            json.dump(groupData, f, indent=4)
            signalForGroupDataUpdate(False)
            print('Group Data Written')
            return True

# Read GROUP_FILE and assign to groupData dict, return groupData
def readGroupData():
    with open(GROUP_FILE, 'r') as f:
        global groupData
        groupData = json.load(f)
        print('Group Data Loaded')
        return groupData

def setup(bot):
    global isLoaded
    isLoaded = True
    bot.add_cog(GroupManager(bot))
    bot.loop.create_task(groupManagerLoop(TICK_RATE))

def teardown(bot):
    global isLoaded
    isLoaded = False
    writeGroupData()
    bot.remove_cog('GroupManager')