import math 
import requests
import json
import importlib
import datetime
import queue
from colorama import Fore
from FetchHelper import fetchPlayer_root
from FetchHelper import fetchPlayerRecents_root
from SQLHelper import addPlayer
from SQLHelper import addGame
from SQLHelper import addParticipation
from SQLHelper import getInterestingPlayersRoster
from ConfigHelper import getConfig

 
config = getConfig()
 #The query starts at the date in question and looks backwards. We use the "End Date" from the config.
#targetIDs = getInterestingPlayersRoster(False,config['EndDate'],config['ChurnDuration'])


#targetIDs = {
#    '7-8-0839' 
#}
updatedPlayers = []
def executeQueryGames(scope ): #Scope should be "full" or "partial"
    config = getConfig()
    if scope == "full": 
        targetIDs = getInterestingPlayersRoster(True,config['StartDate'],config['ChurnDuration'])
    else: 
        targetIDs = getInterestingPlayersRoster(False,config['StartDate'],config['ChurnDuration'])

    queryPlayers(targetIDs,scope)

def queryPlayers (targetIDs,scope):
    updatedPlayers = []
    totalPlayerCount = len(targetIDs)
    counter = 0
    startTime = datetime.datetime.now()
    global WorkerStatus
    for ID in targetIDs:
        WorkerStatus = {}
        if counter >= 20:
            delta = ((datetime.datetime.now() - startTime).total_seconds() / counter) 
            delta = (totalPlayerCount - counter) * delta #seconds remaining
            seconds = round(delta,0)
            minutes = 0
            hours = 0

            if (seconds > 60 ):
                minutes = math.floor(seconds / 60)
                seconds = seconds % 60 
            if (minutes > 60):
                hours = math.floor(minutes / 60 )
                minutes = minutes % 60
            
            delta = "%ih, %im, %is" % (hours,minutes,seconds)
            paddingL = math.floor(10 - (len(delta)/2))
            paddingR = math.ceil(10 - (len(delta)/2))
            delta = "[%s%s%s%s%s]" % (Fore.GREEN," " * paddingL,delta," " * paddingR,Fore.WHITE)
            WorkerStatus["ETA"] = delta 
        else:
            WorkerStatus["ETA"] = "[    Calculating     ]"

        counter = counter + 1 
        region = ID.split("-")[0]
        site =  ID.split("-")[1]
        IDPart = ID.split("-")[2]
        
        DBGstring = "Seeking games for %s-%s-%s, [%i / %i] : " % (region,site,IDPart,counter,totalPlayerCount)
        
        WorkerStatus["CurEntry"] = counter
        WorkerStatus["TotalEntries"] = totalPlayerCount
        WorkerStatus["CurrentAction"] = "games for %s-%s-%s%s" % (region,site,IDPart," "*20) 
        WorkerStatus["CurrentAction"] = "[%s%s%s]" % (Fore.GREEN,WorkerStatus["CurrentAction"][0:20], Fore.WHITE)
        StatusOfFetchPlayer.put((WorkerStatus)) 
        summaryJson = fetchPlayer_root('',region,site,IDPart)
        if summaryJson is not None:
            #print(DBGstring)
            datetime_list = []
            missions = 0
            level = 0
            for i in summaryJson["centre"]:
                datetime_list.append (str(i["joined"]))
                missions += int(i["missions"])
                level = max(level,int(i["skillLevelNum"]))
            joined = min(datetime_list)
            codeName = str(summaryJson["centre"][0]["codename"])
            playerNeedsUpdated = addPlayer(ID,codeName,joined,missions,level)
            
            if playerNeedsUpdated != 0 or scope == "full":
                updatedPlayers.append(ID)
                missionsJson = fetchPlayerRecents_root('',region,site,IDPart)
                if missionsJson != None:
                    for mission in missionsJson["mission"]:
                 
                        missionUUID = addGame(mission[0],mission[1],mission[2])
                        "FetchPlayerAndGames: %s, %s " % (missionUUID, mission)
                        addParticipation(missionUUID,ID,mission[3])
        else:
            DBGstring += "WARNING no data received for user."
            #print(DBGstring)
            
            


    endTime = datetime.datetime.now()
    f = open("Stats.txt","a+")
    f.write("Queried {0} players' recent games, operation completed after {1}. \t\n".format(len(targetIDs),endTime - startTime ))
    f.close()

def manualTargetForGames(targetID):
    queryPlayers([targetID],"full")
 

StatusOfFetchPlayer = queue.Queue()
WorkerStatus = {}
WorkerStatus["CurEntry"] = 0
WorkerStatus["TotalEntries"] = 1
WorkerStatus["CurrentAction"] = "[%s        idle        %s]" % (Fore.GREEN, Fore.WHITE)
WorkerStatus["ETA"] = "[%s      ETC: N/A      %s]" % (Fore.GREEN, Fore.WHITE)

StatusOfFetchPlayer.put(WorkerStatus)