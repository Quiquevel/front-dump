from shuttlelib.openshift.client import OpenshiftClient
from shuttlelib.utils.logger import logger
from urllib3 import disable_warnings, exceptions
from functions.switch import getSwitchStatus
from pytz import timezone
from datetime import datetime, timedelta
from shuttlelib.middleware.authorization import is_authorized_user
from fastapi.encoders import jsonable_encoder
from sys import platform
import os, aiohttp

disable_warnings(exceptions.InsecureRequestWarning)

dynaVariables = {
    "onpremise": {
        "urlbaseproblem": os.getenv("DYNA_URI_BASEPROBLEM_ESP"),
        "urlbaseapi": os.getenv("DYNA_URI_BASEAPI_ESP"),        
        "managementZone": os.getenv("DYNA_MANAGEMENTZONE_ESP"),
        "token": os.getenv("TOKEN_DYNA_ESP"),
        "proxy": None
    },
    "saas": {
        "urlbaseproblem": os.getenv("DYNA_URI_BASEPROBLEM_SaaS"),
        "urlbaseapi": os.getenv("DYNA_URI_BASEAPI_SaaS"),
        "managementZone": os.getenv("DYNA_MANAGEMENTZONE_SaaS"),
        "token": os.getenv("TOKEN_DYNA_SaaS"),
        "proxy": os.getenv("PROXY_DYNA_SaaS")
    }
}

dynaVariablesKeys = ["onpremise", "saas"]
for key in dynaVariablesKeys:
    dynaVariables[key]["urlbasepagesize"] = dynaVariables[key]["urlbaseapi"] + "?nextPageKey="
    #dynaVariables[key]["urlbasepagesize"] = dynaVariables[key]["urlbaseapi"]
    dynaVariables[key]["headers"] = {"Authorization": "Api-Token " + dynaVariables[key]["token"], "Accept": "application/json; charset=utf-8"}

def getEnvironmentsClustersList(entityID):
    client = OpenshiftClient(entityID=entityID)
    environmentList = []    
    clusterNameList = []
    clusterUrlList = []
    
    environmentList = list(client.clusters.keys())
    for environment in environmentList:
        clusterNameList = list(client.clusters[environment])
        for cluster in clusterNameList:
            if 'azure' in cluster:
                clusterUrl = client.clusters[environment][cluster]['weu1']['url']
                clusterUrlList.append(client.clusters[environment][cluster]['weu1']['url'])
            else: 
                clusterUrl = client.clusters[environment][cluster]['bo1']['url']
                clusterUrlList.append(clusterUrl)

    environmentList.extend([x.upper() for x in environmentList])    
    clusterNameList.extend([x.upper() for x in clusterNameList])
    clusterNameList = list(set(clusterNameList))
    clusterNameList.sort()
    
    return environmentList, clusterNameList

async def dynatraceTreatment(functionalEnvironment, timedyna = None):
    logger.info(f"starting getDynaProblems process")
    
    switchednamespaces = await getSwitchStatus(functionalEnvironment)
    detailalertlist = await getDynaProblems(timedyna, switchednamespaces)
    
    logger.info(f"finished getDynaProblems process")

    return detailalertlist

async def getDynaProblems(timedyna, switchednamespaces):
    detailalertlist = []
    detailalertlistCurrent = []
    detailalertlistNext = []
    nextpagekey = ""
    
    global urlbaseproblem
    global urlbaseapi
    global headers
    global proxy

    if timedyna == None:
        timedyna = "now"

    async with aiohttp.ClientSession() as session:
        for key in dynaVariablesKeys:            
            headers = dynaVariables[key]["headers"]
            params = {"from":timedyna, "problemSelector":dynaVariables[key]["managementZone"], "pageSize":"500"}
            urlbaseapi = dynaVariables[key]["urlbaseapi"]
            urlbasepagesize = dynaVariables[key]["urlbasepagesize"]
            urlbaseproblem = dynaVariables[key]["urlbaseproblem"]
            proxy = dynaVariables[key]["proxy"]
            
            try:
                #logger.info(f"Dynatrace GetProblems {key}")
                #logger.info(f"Dynatrace GetProblems Proxy: {proxy}")
                async with session.get(urlbaseapi, headers = headers, params = params, ssl = False, proxy = proxy) as res:
                    res_json = await res.json()
                    Ps = res_json['problems']
                    #logger.info(f"Dynatrace response: {res.status}, {res.reason}")
                    #logger.info(f"Dynatrace # alerts Ps: {len(Ps)}")
            except aiohttp.client_exceptions.ServerTimeoutError:
                logger.error(f"Timeout detected against {urlbaseapi} ")
                infodetailalert = {'alertingType': None, 'problemId': None, 'urlproblem': None, 'snowId': None, 'urlsnow': None, 'incidentProvider': 'Dynatrace', 'status': None, 'start': None, 'end': None, 'namespace': None, 'microservice': None, 'cluster': None, 'region': None, 'switchStatus': None} 
                detailalertlist.append(infodetailalert)
                #logger.error(f"Dynatrace response: {res.status}, {res.reason}")
                return detailalertlist
            except:
                logger.error(f"{urlbaseapi} could not be retrieved. Skipping...")
                infodetailalert = {'alertingType': None, 'problemId': None, 'urlproblem': None, 'snowId': None, 'urlsnow': None, 'incidentProvider': 'Dynatrace', 'status': None, 'start': None, 'end': None, 'namespace': None, 'microservice': None, 'cluster': None, 'region': None, 'switchStatus': None}
                detailalertlist.append(infodetailalert)
                #logger.error(f"Dynatrace response: {res.status}, {res.reason}")
                return detailalertlist
            detailalertlistCurrent = await loopDynaProblems(Ps, switchednamespaces)
            detailalertlist.extend(detailalertlistCurrent)
            #loop for nextPageKey
            try:
                nextpagekey = res_json['nextPageKey']
            except:
                nextpagekey = None            
            while nextpagekey is not None:
                #logger.info(f"Dynatrace alerts nextpagekey in {key}")
                async with session.get(urlbasepagesize + nextpagekey, headers = headers, ssl = False, proxy = proxy) as resnextpagekey:
                    resnextpagekey_json = await resnextpagekey.json()
                    try:
                        nextpagekey = resnextpagekey_json['nextPageKey']
                    except:
                        nextpagekey = None
                    PsNext = resnextpagekey_json['problems']
                    #logger.info(f"Dynatrace # alerts PsNext: {len(PsNext)}")
                    detailalertlistNext = await loopDynaProblems(PsNext, switchednamespaces)
                    detailalertlist.extend(detailalertlistNext)

            logger.info(f"Dynatrace alerts getDynaProblems (after {key} execution Total: {len(detailalertlist)})")
        logger.info(f"Dynatrace alerts getDynaProblems (Total: {len(detailalertlist)})")
    return detailalertlist

async def loopDynaProblems(Ps, switchednamespaces):
    detailalertlist = []
    alertTypeList = ["Long garbage-collection time", "Memory resources exhausted", "Response time degradation", "Failure rate increase", "Multiple service problems"]
    
    global hostdetectedlist
    global namespace
    global microservice
    global platform

    for p in range(len(Ps)):
        paasproblem = Ps[p]
        problemtags = paasproblem["entityTags"]        
        dateS,dateE = await matchProblemTime(paasproblem["startTime"], paasproblem["endTime"])
        displayId = paasproblem["displayId"]
        problemId = paasproblem["problemId"]
        title = paasproblem["title"]
        status = paasproblem["status"]
        
        if displayId == "P-240817741":
            pass

        if paasproblem["title"] in alertTypeList and len(problemtags) > 0:
            for t in range(len(problemtags)):
                value = problemtags[t].get("value", None)
                key = problemtags[t]['key']

                if value:              
                    await matchProblemTags(key, value)

            if not namespace:
                try:
                    namespaceAux = paasproblem['affectedEntities'][0]['name']            
                except:
                    pass

                if "-pro" in namespaceAux:
                    namespaceAux = namespaceAux.split("-")
                    x = slice(3)
                    namespaceAux = namespaceAux[x]
                    namespaceAux = '-'.join(namespaceAux)
                    namespace = namespaceAux
                else:
                    try:
                        managementZones = paasproblem['managementZones']
                    except:
                        pass
                    for t in range(len(managementZones)):
                        managementZone = managementZones[t]
                        if "-pro" in managementZone['name']:
                            namespaceAux = managementZone['name']
                            namespaceAux = namespaceAux.split("- ")
                            namespace = ''.join(namespaceAux[-1:])
                            break

            detailalert = await paasProblemReport(displayId, problemId, title, status, dateS, dateE, namespace, microservice, platform, hostdetectedlist, switchednamespaces)

            platform = None
            namespace= None
            microservice = None
            hostdetectedlist = None

            if len(detailalert) != 0:
                detailalertlist.extend(detailalert)
            hostdetectedlist = []
        
    return detailalertlist

async def matchProblemTime(starttime, endtime):
    dateE = None

    summer = await isSummer(datetime.today())
    if summer:
        delta = 0
    else:
        delta = 1
     
    dateDyna = int(starttime)/1000
    dateS = datetime.fromtimestamp(dateDyna)
    dateS = dateS + timedelta(hours = delta)
    dateS = dateS.strftime('%Y-%m-%d %H:%M:%S')

    if int(endtime) != -1:
        dateDyna = int(endtime)/1000
        dateE = datetime.fromtimestamp(dateDyna)
        dateE = dateE + timedelta(hours = delta)
        dateE = dateE.strftime('%Y-%m-%d %H:%M:%S')

    return (dateS, dateE)

hostdetectedlist = []
async def matchProblemTags(key, value):
    global platform
    global namespace
    global microservice
    global hostdetectedlist

    match key:
        case "HostDetectedName":            
            hostdetected = value
            hostdetectedlist.append(hostdetected)            
        case "PLATFORM":
            platform = value
        case "PROYECTO_PaaS2.0":
            namespace = value
        case "Container_name":
            microservice = value            
        case "Microservicio":
            microservice = value

async def paasProblemReport(displayId, problemId, type, status, start, end, namespace, microservice, platform, hostdetectedlist, switchednamespaces):
    detailalertlist = []

    #find switchednamespaces
    switched = [x for x in switchednamespaces if x == namespace]
    if switched:
        switchStatus = True
    else:
        switchStatus = False

    match type:
        case 'Long garbage-collection time':
            detailalertlist = await detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus)
        case 'Memory resources exhausted':
            detailalertlist = await detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus)
        case 'Response time degradation':            
            detailalertlist = await detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus)
        case 'Failure rate increase':            
            detailalertlist = await detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus)
        case "Multiple service problems":            
            detailalertlist = await detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus)
        case _:
            pass

    return detailalertlist

async def isSummer(dt):
    timeZone = timezone("Europe/Madrid")
    aware_dt = timeZone.localize(dt)
    
    return aware_dt.dst() != timedelta(0,0)

async def detailAlertFill(type, problemId, displayId, status, start, end, namespace, microservice, platform, hostdetectedlist, switchStatus):    
    detailalertlist = []
    
    global urlbaseproblem
    global urlbaseapi

    urlproblem = urlbaseproblem + problemId
    inforegion = await paasProblemRegion(hostdetectedlist)      
    platform = await paasProblemPlatform(platform, hostdetectedlist) 
    idSNOW, urlSNOW = await matchProblemSNOW(problemId)
    
    if not platform and (type == "Memory resources exhausted" or type == "Long garbage-collection time"):
        platform = await matchHostName(problemId, urlbaseapi)
        
    if inforegion != None:
        validateregion = inforegion.split(", ")
        if validateregion:
            for region in validateregion:
                infodetailalert = {
                    'alertingType': type,
                    'problemId': displayId,
                    'urlproblem': urlproblem,
                    'snowId': idSNOW,
                    'urlsnow': urlSNOW,
                    'incidentProvider': 'Dynatrace',
                    'status': status,
                    'start': start,
                    'end': end,
                    'namespace': namespace,
                    'microservice': microservice,
                    'cluster': platform,
                    'region': region,
                    'switchStatus': switchStatus
                } 
                detailalertlist.append(infodetailalert)
    else:        
        infodetailalert = {
            'alertingType': type,
            'problemId': displayId,
            'urlproblem': urlproblem,
            'snowId': idSNOW,
            'urlsnow': urlSNOW,
            'incidentProvider': 'Dynatrace',
            'status': status,
            'start': start,
            'end': end,
            'namespace': namespace,
            'microservice': microservice,
            'cluster': platform,
            'region': None,
            'switchStatus': switchStatus
        } 
        detailalertlist.append(infodetailalert)

    return detailalertlist

async def paasProblemRegion(hostdetectedlist):
    if len(hostdetectedlist) == 0:
        return None

    for hostnames in hostdetectedlist:        
        try:
            hostname = hostnames.split(", ")
            region= set()
            hostnames = [nodo.split(".")[4] for nodo in hostname if "." in nodo]            
            if len(hostnames) > 0:
                region.update(hostnames)
                region= ", ".join(str(item) for item in region)
            else:
                region = None
        except:
            region = None
    
    return region

async def paasProblemPlatform(cluster, hostdetectedlist):
    if len(hostdetectedlist) == 0:
        platform = None
        return platform        

    if cluster == "AZURE" or cluster == "AZURE_CCC":
        platform = "azure"
        return platform    
    else:
        for hostname in hostdetectedlist:
            if "san01.san.pro" in hostname:
                platform = "proohe"
                return platform
            elif "san01.san.dmzb" in hostname:
                platform = "dmzbohe"
                return platform
            elif "san01darwin.san.pro" in hostname:
                platform = "prodarwin"
                return platform
            elif "san01darwin.san.dmzb" in hostname:
                platform = "dmzbdarwin"
                return platform
            elif "san01confluent.san" in hostname:
                platform = "confluent"
                return platform
            elif "san01bks.san.pro" in hostname:
                platform = "probks"
                return platform
            elif "san01bks.san.dmzb" in hostname:
                platform = "dmzbbks"
                return platform
            elif "san01mov.san.dmz2b" in hostname:
                platform = "dmz2bmov"
                return platform
            elif "ocp05.san.pro" in hostname:
                platform = "azure"
                return platform
            elif "weu" in hostname:
                platform = "azure"
                return platform
            else:
                platform = None
                return platform
            
async def matchProblemSNOW(problemId):
    idSNOW = None
    urlSNOW = None
    
    global urlbaseapi
    global headers
    global proxy
    
    params = None
    urlrequestproblem = urlbaseapi + '/' + problemId

    async with aiohttp.ClientSession() as session:
        try:            
            async with session.get(urlrequestproblem, headers = headers, params = params, ssl = False, proxy = proxy) as res:
                Ps = await res.json()
                #logger.info(f"Dynatrace response: {res.status}, {res.reason}")
        except aiohttp.client_exceptions.ServerTimeoutError:
            logger.error(f"Timeout detected against {urlrequestproblem} ")            
            return None, None
        except:
            logger.error(f"{urlrequestproblem} could not be retrieved. Skipping...")                        
            return None, None

        try:
            comments = Ps["recentComments"]                
        except:
            return None, None
        
        for comment in comments['comments']:
            if comment['content'].startswith("Incidencia creada en ServiceNow"):
                datos = comment['content'].split("\n")
                try:
                    urlSNOW = datos[3] 
                except:
                    return None, None
                idSNOW = datos[0].split(":")
                idSNOW = str(idSNOW[1].strip())

    return idSNOW, urlSNOW


async def matchHostName(problemId, urlbaseapi = None):
    params = None
    urlrequestproblem = urlbaseapi + '/' + problemId

    async with aiohttp.ClientSession() as session:
        try:            
            async with session.get(urlrequestproblem, headers = headers, params = params, ssl = False, proxy = proxy) as res:
                Ps = await res.json()
                #logger.info(f"Dynatrace response: {res.status}, {res.reason}")
        except aiohttp.client_exceptions.ServerTimeoutError:
            logger.error(f"Timeout detected against {urlrequestproblem} ")            
            return None
        except:
            logger.error(f"{urlrequestproblem} could not be retrieved. Skipping...")                        
            return None

        try:
            evidenceDetails = Ps['evidenceDetails']['details']
        except:
            return None

        for t in range(len(evidenceDetails)):
            evidence = evidenceDetails[t]
            if evidence['evidenceType'] == 'EVENT':
                properties = evidence['data']['properties']

                if evidence['displayName'] == "Memory resources exhausted":
                    for t in range(len(properties)):                    
                        key = properties[t]['key']                   
                        if key == 'host.name':
                            host = properties[t].get("value", None)
                            platform = await paasProblemPlatform(None, [host])
                            return platform                        
                elif evidence['displayName'] == "Long garbage-collection time":
                    for t in range(len(properties)):                    
                        key = properties[t]['key']                   
                        if key == 'dt.event.description':
                            host = properties[t].get("value", None)
                            hostPart = host.split("on host ")
                            platform = await paasProblemPlatform(None, [hostPart[1]]) 
                            return platform