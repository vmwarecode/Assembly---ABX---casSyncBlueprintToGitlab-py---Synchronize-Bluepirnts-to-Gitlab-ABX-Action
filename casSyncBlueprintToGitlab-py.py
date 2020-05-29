#--------------------------------------------------------#
#                     Spas Kaloferov                     #
#                   www.kaloferov.com                    #
# bit.ly/The-Twitter      Social     bit.ly/The-LinkedIn #
# bit.ly/The-Gitlab        Git         bit.ly/The-Github #
# bit.ly/The-BSD         License          bit.ly/The-GNU #
#--------------------------------------------------------#

  #
  #       VMware Cloud Assembly ABX Code Sample          
  #
  # [Description] 
  #   - Syncs Blueprint(s) to Gitlab:
  #      - Syncs when blueprints are versioned or deleted.
  #      - Upon Assembly deletion blueprint can be deleted in Git or preserved by setting blueprint option bluepirnt option blueprintOptionGitDelete
  #      - All blueprints can be synchronized or only selected once by setting blueprint option gitlabSyncEnable
  #      - Renaming a blueprint in Assembly creates a new blueprint in Git 
  #   - Allows secrets and passwords to be provided via action inputs or AWS Secrets Manager secrets  
  #   - Further guidance can be found here: ABX Action to Sync Blueprints from Assembly to Gitlab (http://kaloferov.com/blog/skkb1050)
  # [Inputs]
  #   - gitProjectIdIn (Integer): Git project folder e.g. 14854581     
  #   - gitProjectFolderIn (String): Git project folder e.g. cloud-assembly/blueprints-auto-sync/
  #   - actionOptionAcceptPayloadInputIn (Boolean): Can be used to turn off payload inputs and use action inputs to speed up ABX action testing. 
  #      - True: Accept payload inputs. 
  #      - False: Accept only action inputs. Mainly for ABX testing only 
  #         - runOnBlueprintOptionMatchABXIn: see below
  #         - runOnPorpertyMatchABXIn: see below
  #         - blueprintIdABXIn (String): Id of the blueprint to be synchronized with Git. 
  #         - blueprintNameABXIn (String): Name of the blueprint to be synchronized with Git. 
  #         - blueprintVersionABXIn (String): Blueprint release version to be synchronized with Git. 
  #   - actionOptionRunOnPropertyIn (Boolean): RunOn custom property condition
  #      - True: Check for runOn condition
  #         - runOnPropertyIn (String): Custom property key/value to match for when actionOptionRunOnPropertyIn=True ( e.g. cloudZoneProp: cas.cloud.zone.type:aws )
  #         - runOnPorpertyMatchABXIn (String): Custom property key/value to match actionOptionRunOnPropertyIn=True and actionOptionAcceptPayloadInputIn=False. For ABX testing. ( e.g. cloudZoneProp: cas.cloud.zone.type:aws )
  #      - False: Do not check for runOn condition
  #   - actionOptionRunOnBlueprintOptionIn (Boolean): RunOn blueprint option condition
  #      - True: Check for runOn condition
  #         - runOnBlueprintOptionIn (String): Blueprint property key/value to match for when actionOptionRunOnBlueprintOptionIn=True (e.g. gitlabSyncEnable: true)
  #         - runOnBlueprintOptionMatchABXIn (String): Blueprint property key/value to match for when actionOptionRunOnBlueprintOptionIn=True and actionOptionAcceptPayloadInputIn=False. For ABX testing. (e.g. gitlabSyncEnable: true)
  #      - False: Do not check for runOn condition
  #   - actionOptionUseAwsSecretsManagerIn (Boolean): Allows use of AWS Secrets Manager for secrets retrieval 
  #      - True: Use AWS Secrets Manager for secrets
  #         - awsSmRegionNameIn (String): AWS Secrets Manager Region Name e.g. us-west-2
  #         - awsSmCspTokenSecretIdIn (String): AWS Secrets Manager CSP Token Secret ID
  #         - awsSmGitTokenSecretIdIn (String): AWS Secrets Manager Git Token Secret ID
  #      - False: Use action inputs for secrets
  #         - cspRefreshTokenIn (String): CSP Token
  #         - gitPrivateTokenIn (String): Git Token
  # [Dependency]
  #   - Requires: requests,pyyaml,boto3,requests,python-gitlab 
  # [Subscription]
  #   - Event Topics:
  #      - blueprint.configuration: Subscribe here for blueprint configuration events like create / delete. > Only delete enabled
  #         - Condition: event.eventType = "DELETE_BLUEPRINT"
  #      - blueprint.version.configuration: Subscribe here for blueprint versioning events like create / release / un-release / restore > Only create version enabled.
  #         - Condition: event.eventType = "CREATE_BLUEPRINT_VERSION"
  # [Blueprint Options]
  #   - Supported options: 
  #      - gitlabSyncEnable (Boolean): Enable Git blueprint synchronization   
  #      - gitlabSyncDelete (Boolean): Delete blueprints from Git. If set to false, deleting a blueprint in Cloud Assembly will not delete the blueprint in Git
  #   - For more on blueprint options , visit: Using Blueprint Options in Cloud Assembly (http://kaloferov.com/blog/skkb1051/)
  # [Thanks]
  #   - Thanks to Dana Gertsch (https://www.linkedin.com/in/danagertsch/) for his work with ABX and AWS Systems Manager which gave me the idea to use AWS Secrets Manager https://knotacoder.com/2020/05/11/using-aws-ssm-parameters-with-vra-cloud-abx-actions/
  #


import json
import yaml 
import logging
import boto3
import requests
import gitlab
import urllib3
#import base64


# ----- Global ----- #  

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)   # Warned when making an unverified HTTPS request.
urllib3.disable_warnings(urllib3.exceptions.DependencyWarning)   # Warned when an attempt is made to import a module with missing optional dependencies. 
cspBaseApiUrl = "https://api.mgmt.cloud.vmware.com"    # CSP portal base url


# ----- Functions  ----- # 

def handler(context, inputs):   # Action entry function.

    fn = "handler -"    # Funciton name 
    print("[ABX] "+fn+" Action started.")
    print("[ABX] "+fn+" Function started.")
    

    # ----- Action Options  ----- # 
    
    # General action options    
    actionOptionAcceptPayloadInput = inputs['actionOptionAcceptPayloadInputIn'].lower()     
    actionOptionRunOnProperty = inputs['actionOptionRunOnPropertyIn'].lower()   
    actionOptionRunOnBlueprintOption = inputs['actionOptionRunOnBlueprintOptionIn'].lower()    
    actionOptionUseAwsSecretsManager = inputs['actionOptionUseAwsSecretsManagerIn'].lower()    
    awsSmCspTokenSecretId = inputs['awsSmCspTokenSecretIdIn']   # TODO: Set in actin inputs if actionOptionUseAwsSecretsManagerIn=True  
    awsSmGitTokenSecretId = inputs['awsSmGitTokenSecretIdIn']   # TODO: Set in actin inputs if actionOptionUseAwsSecretsManagerIn=True  
    awsSmRegionName = inputs['awsSmRegionNameIn']   # TODO: Set in actin inputs if actionOptionUseAwsSecretsManagerIn=True    
    runOnProperty = inputs['runOnPropertyIn'].replace('"','').lower()   # TODO: Set in actin inputs if actionOptionRunOnPropertyIn=True  
    runOnBlueprintOption = inputs['runOnBlueprintOptionIn'].replace('"','').lower()    # TODO: Set in actin inputs if actionOptionRunOnBlueprintOptionIn=True  
    runOnPorpertyMatch = inputs['runOnPorpertyMatchABXIn'].replace('"','').lower()    # TODO: Set in actin inputs if actionOptionAcceptPayloadInput=False  
    runOnBlueprintOptionMatch = inputs['runOnBlueprintOptionMatchABXIn'].replace('"','').lower()    # TODO: Set in actin inputs if actionOptionAcceptPayloadInput=False  
    cspRefreshToken = inputs['cspRefreshTokenIn']    # TODO: Set in actin inputs if actionOptionUseAwsSecretsManagerIn=False   
    gitPrivateToken = inputs['gitPrivateTokenIn']    # TODO: Set in actin inputs if actionOptionUseAwsSecretsManagerIn=False     
    blueprintId = inputs['blueprintIdABXIn']    # TODO: Set in actin inputs if actionOptionAcceptPayloadInput=False  
    eventType = ""  # Event Type for which aciton is running
    eventTopicId = ""   # Event Topic for which the aciton is running
    
    
    # ----- Inputs  ----- #     

    # Git inputs
    gitProjectFolder = inputs['gitProjectFolderIn']    # TODO: Set in actin inputs Required   
    gitProjectId = inputs['gitProjectIdIn']    # TODO: Set in actin inputs Required   
    blueprintVersion = inputs['blueprintVersionABXIn']    # TODO: Set in actin inputs if actionOptionAcceptPayloadInput=False  
    blueprintName = inputs['blueprintNameABXIn']    # TODO: Set in actin inputs if actionOptionAcceptPayloadInput=False  
    userName = ""   # Username of who triggered the action


    # eventType 
    if (str(inputs).count('CREATE_BLUEPRINT_VERSION') == 1):
        eventType = "CREATE_BLUEPRINT_VERSION"
    elif (str(inputs).count('DELETE_BLUEPRINT') == 1):
        eventType = "DELETE_BLUEPRINT"
    elif (str(inputs).count("eventType") == 0):
        eventType = "TEST"
    else:
        eventType = "UNSUPPORTED"
    # End Loop
    
    # eventTopicId 
    if (str(inputs).count('blueprint.version.configuration') == 1):
        eventTopicId = "blueprint.version.configuration"
    elif (str(inputs).count("blueprint.configuration") == 1):
        eventTopicId = "blueprint.configuration"
    elif (str(inputs).count("eventTopicId") == 0):
        eventTopicId = "TEST"
    else:
        eventTopicId = "UNSUPPORTED"
    # End Loop
    

    # actionInputs Hashtable
    actionInputs = {}  
    actionInputs['actionOptionAcceptPayloadInput'] = actionOptionAcceptPayloadInput
    actionInputs['actionOptionRunOnProperty'] = actionOptionRunOnProperty
    actionInputs['actionOptionRunOnBlueprintOption'] = actionOptionRunOnBlueprintOption
    actionInputs['actionOptionUseAwsSecretsManager'] = actionOptionUseAwsSecretsManager
    actionInputs['awsSmCspTokenSecretId'] = awsSmCspTokenSecretId 
    actionInputs['awsSmGitTokenSecretId'] = awsSmGitTokenSecretId 
    actionInputs['awsSmRegionName'] = awsSmRegionName 
    actionInputs['runOnProperty'] = runOnProperty 
    actionInputs['runOnBlueprintOption'] = runOnBlueprintOption
    actionInputs['cspRefreshToken'] = cspRefreshToken
    actionInputs['gitPrivateToken'] = gitPrivateToken
    actionInputs['eventType'] = eventType
    actionInputs['eventTopicId'] = eventTopicId
    actionInputs['gitProjectFolder'] = gitProjectFolder
    actionInputs['gitProjectId'] = gitProjectId
    actionInputs['blueprintVersion'] = blueprintVersion
    actionInputs['blueprintName'] = blueprintName
    actionInputs['userName'] = userName


    # ----- AWS Secrets Manager  ----- #     
    
    # Get AWS Secrets Manager Secrets
    if (actionInputs['actionOptionUseAwsSecretsManager'] == "true"):
        print("[ABX] "+fn+" Auth/Secrets source: AWS Secrets Manager")
        awsRegionName = awsSmRegionName
        awsSecretId_csp = awsSmCspTokenSecretId
        awsSecretId_git = awsSmGitTokenSecretId
        awsSecrets = awsSessionManagerGetSecret (context, inputs, awsSecretId_csp, awsSecretId_git, awsRegionName)  # Call function
        cspRefreshToken = awsSecrets['awsSecret_csp']
        gitPrivateToken = awsSecrets['awsSecret_git']
        actionInputs['cspRefreshToken'] = cspRefreshToken
        actionInputs['gitPrivateToken'] = gitPrivateToken
    else:
        # use action inputs
        print("[ABX] "+fn+" Auth/Secrets source: Action Inputs")


    # ----- CSP Token  ----- #     
    
    # Get Token
    getRefreshToken_apiUrl = cspBaseApiUrl + "/iaas/api/login"  # Set API URL
    body = {    # Set call body
        "refreshToken": actionInputs['cspRefreshToken']
    }
    print("[ABX] "+fn+" Getting CSP Bearer Token.")
    getRefreshToken_postCall = requests.post(url = getRefreshToken_apiUrl, data=json.dumps(body))   # Call 
    getRefreshToken_responseJson = json.loads(getRefreshToken_postCall.text)    # Get call response
    bearerToken = getRefreshToken_responseJson["token"]   # Set response
    requestsHeaders= {
        'Accept':'application/json',
        'Content-Type':'application/json',
        'Authorization': 'Bearer {}'.format(bearerToken),
        # 'encoding': 'utf-8'
    }
    
    actionInputs['cspBearerToken'] = bearerToken
    actionInputs['cspRequestsHeaders'] = requestsHeaders
    
    
    
    # replace any emptry , optional, "" or '' inputs with empty value 
    for key, value in actionInputs.items(): 
        if (("Optional".lower() in str(value).lower()) or ("empty".lower() in str(value).lower()) or ('""' in str(value).lower())  or ("''" in str(value).lower())):
            actionInputs[key] = ""
        else:
            print('')
    # End Loop
    

    if (actionInputs['actionOptionAcceptPayloadInput'] == 'true'):     # Loop. If Payload exists and Accept Payload input action option is set to True , accept payload inputs . Else except action inputs.
        print("[ABX] "+fn+" Using PAYLOAD inputs based on actionOptionAcceptPayloadInputIn action option")
        
        # blueprintId / blueprintVersion / blueprintName / userName
        if (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION"):
            blueprintId = inputs['blueprintId']
            blueprintVersion = inputs['version']
            blueprintName = inputs['blueprintName']
            userName = inputs['__metadata']['userName']
        elif (inputs['eventType'] == "TEST"):
            # use action inputs
            print('')
        else:  # (inputs['eventType'] == "DELETE_BLUEPRINT")
            blueprintId = inputs['id']    
            blueprintVersion = ""
            blueprintName = inputs['name']
            userName = inputs['__metadata']['userName']
        # End Loop
        

        # runOn Condition Inputs
        if (actionInputs['eventTopicId'] != "TEST"):
            
            # runOnPorpertyMatch
            if (actionInputs['actionOptionRunOnProperty'] == "true"):    # Loop. Get property to match against. 
                runOnPorpertyMatch = (json.dumps(inputs)).replace('"','').lower()
            else:
                print('')
                # Get value from action inputs
            # End Loop
    
            # runOnBlueprintOptionMatch
            if (actionInputs['actionOptionRunOnBlueprintOption'] == "true"):    # Loop. Get property to match against. 
                print("[ABX] "+fn+" Using BLUEPRINT for blueprintOptions based on actionOptionRunOnBlueprintOptionIn action option")
                print("[ABX] "+fn+" Getting blueprintOptions...")
                body = {}
                resp_blueprintOptions_callUrl = cspBaseApiUrl + '/blueprint/api/blueprints/'+blueprintId+'?$select=*&apiVersion=2019-09-12'
                resp_blueprintOptions_call = requests.get(resp_blueprintOptions_callUrl, data=json.dumps(body), verify=False, headers=(actionInputs['cspRequestsHeaders']))
                #runOnBlueprintOptionMatch = str(json.loads(resp_blueprintOptions_call.text)).lower()
                runOnBlueprintOptionMatch = json.loads(resp_blueprintOptions_call.text)
                runOnBlueprintOptionMatch = yaml.safe_load(runOnBlueprintOptionMatch['content'])   # Get the BP Yaml from the Content
                runOnBlueprintOptionMatch = str(runOnBlueprintOptionMatch['options']).replace("'","").lower()    # Get the options from the BP Yaml
            else:
                print('')
                # Get value from action inputs
            # End Loop
            
        else:
            print('')
            # Get value from action inputs
        # End Loop

    elif (actionInputs['actionOptionAcceptPayloadInput'] == 'false'):
        print("[ABX] "+fn+" Using ACTION inputs for ABX action based on actionOptionAcceptPayloadInputIn action option")
        print("[ABX] "+fn+" Using ACTION inputs for blueprintOptions based on actionOptionRunOnBlueprintOptionIn action option")
        # Get values from action inputs
    else: 
        print("[ABX] "+fn+" INVALID action inputs based on actionOptionAcceptPayloadInputIn action option")
    # End Loop


    actionInputs['blueprintId'] = blueprintId
    actionInputs['blueprintVersion'] = blueprintVersion
    actionInputs['blueprintName'] = blueprintName
    actionInputs['userName'] = userName
    
    actionInputs['runOnPorpertyMatch'] = runOnPorpertyMatch    
    actionInputs['runOnBlueprintOptionMatch'] = runOnBlueprintOptionMatch


    # Print actionInputs
    for key, value in actionInputs.items(): 
        if (("cspRefreshToken".lower() in str(key).lower()) or ("cspBearerToken".lower() in str(key).lower()) or ("cspRequestsHeaders".lower() in str(key).lower()) or ("runOnPorpertyMatch".lower() in str(key).lower()) or ("runOnBlueprintOptionMatch".lower() in str(key).lower()) or ("slackToken".lower() in str(key).lower()) or ("gitPrivateToken".lower() in str(key).lower())   ):
            print("[ABX] "+fn+" actionInputs[] - "+key+": OMITED")
        else:
            print("[ABX] "+fn+" actionInputs[] - "+key+": "+str(actionInputs[key]))
    # End Loop
    

    # ----- Evals ----- # 
    
    evals = {}  # Holds evals values
    
    # runOnProperty eval
    if ((actionInputs['actionOptionRunOnProperty'] == "true") and (actionInputs['runOnProperty'] in actionInputs['runOnPorpertyMatch'])):   # Loop. RunOn eval.
        runOnProperty_eval = "true"
    elif ((actionInputs['actionOptionRunOnProperty'] == "true") and (actionInputs['runOnProperty'] not in actionInputs['runOnPorpertyMatch'])):
        runOnProperty_eval = "false"
    else:
        runOnProperty_eval = "Not Evaluated"
    # End Loop

    # runOnBlueprintOption  eval
    if ((actionInputs['actionOptionRunOnBlueprintOption'] == 'true') and (actionInputs['runOnBlueprintOption'] in actionInputs['runOnBlueprintOptionMatch'])):     # Loop. RunOn eval.
        runOnBlueprintOption_eval = "true"
    elif ((actionInputs['actionOptionRunOnBlueprintOption'] == 'true') and (actionInputs['runOnBlueprintOption'] not in actionInputs['runOnBlueprintOptionMatch'])):  
        runOnBlueprintOption_eval = "false"
    else:  
        runOnBlueprintOption_eval = "Not Evaluated"
    # End Loop

    evals['runOnProperty_eval'] = runOnProperty_eval.lower()
    print("[ABX] "+fn+" runOnProperty_eval: " + evals['runOnProperty_eval'])        
    evals['runOnBlueprintOption_eval'] = runOnBlueprintOption_eval.lower()
    print("[ABX] "+fn+" runOnBlueprintOption_eval: " + evals['runOnBlueprintOption_eval'])


    # ----- Function Calls  ----- # 
    
    if (evals['runOnProperty_eval'] != 'false' and evals['runOnBlueprintOption_eval'] != 'false'): 
        print("[ABX] "+fn+" runOnProperty matched or actionOptionRunOnPropertyIn action option disabled.")
        print("[ABX] "+fn+" runOnBlueprintOption matched or actionOptionRunOnBlueprintOptionIn action option disabled.")
        print("[ABX] "+fn+" Running myActionFunction...")
        resp_myActionFunction = myActionFunction (context, inputs, actionInputs, evals)     # Call function
    else:
        print("[ABX] "+fn+" runOn condition(s) NOT matched. Skipping action run.")
        resp_myActionFunction = ""
     
        
    # ----- Outputs ----- #
    
    resp_handler = {}   # Set function response 
    resp_handler = evals
    resp_handler
    outputs = {   # Set action outputs
       "actionInputs": actionInputs,
       "resp_handler": resp_handler,
       "resp_myActionFunction": resp_myActionFunction,
    }
    print("[ABX] "+fn+" Function return: \n" + json.dumps(resp_handler))    # Write function responce to console  
    print("[ABX] "+fn+" Function completed.")     
    #print("[ABX] "+fn+" Action return: \n" +  json.dumps(outputs))    # Write action output to console     
    print("[ABX] "+fn+" Action completed.")     
    print("[ABX] "+fn+" P.S. Spas Is Awesome !!!")

    return outputs    # Return outputs 



def myActionFunction (context, inputs, actionInputs, evals):   # Main Function. 
    fn = "myActionFunction -"    # Holds the funciton name. 
    print("[ABX] "+fn+" Action started.")
    print("[ABX] "+fn+" Function started.")
    
    
    # ----- Script ----- #

    # Get Blueprint
    resp_getBlueprint_json = {}
    if ( (actionInputs['eventType'] == "CREATE_BLUEPRINT_VERSION") or (actionInputs['actionOptionAcceptPayloadInput'] == "false") ):  
        body = {}
        print("[ABX] "+fn+" Getting Blueprint...")
        resp_getBlueprint_callUrl = cspBaseApiUrl + '/blueprint/api/blueprints/'+actionInputs['blueprintId']+'?$select=*&apiVersion=2019-09-12'
        resp_getBlueprint_call = requests.get(resp_getBlueprint_callUrl, data=json.dumps(body), verify=False, headers=(actionInputs['cspRequestsHeaders']) )
        resp_getBlueprint_json = json.loads(resp_getBlueprint_call.text)
        #print(resp_getBlueprint_json['content'])
        blueprint = (resp_getBlueprint_json['content'])
        #blueprint_yaml = yaml.load(resp_getBlueprint_json['content'])   # Convert blueprint content to yaml
        
        # Loop to replace blueprint version value
        str_list = blueprint.split('\n')
        length = len(str_list) 
        i = 0
        while i < length: 
            if ("version: " in str_list[i]):
                str_list[i] = "version: " + actionInputs['blueprintVersion'] + "    # Value overridden by ABX Action"
                break
            else:
                i += 1
        # End Loop        
        
        # Loop to replace blueprint name value
        i = 0
        while i < length: 
            if ("name: " in str_list[i]):
                str_list[i] = "name: " + actionInputs['blueprintName'] + "    # Value overridden by ABX Action"
                break
            else:
                i += 1
        # End Loop
        
        string = "\n".join(str_list)    
        blueprint = string
    
    else: 
        blueprint = ""  # Used when BP content is not needed. For exmaple for delete events. 
    
    # Connect to Git
    gtUrl = "https://gitlab.com/"   # Git URL
    gPrivateToken = str(actionInputs['gitPrivateToken'])   # Git private token
    gl = gitlab.Gitlab(gtUrl, private_token=gPrivateToken, api_version=4)   # Auth to Gitlab
    gProjectId = actionInputs['gitProjectId']   # Git project ID 
    gPproject = gl.projects.get(gProjectId)    # Get project
    gFolder = actionInputs['gitProjectFolder']    # Root repo folder
    gFilename = "/blueprint.yaml"    # Blueprint name
    gBlueprintName = actionInputs['blueprintName']
    gBlueprintNameFolder = gBlueprintName.lower().replace(" ",'-').replace("(",'-').replace(")",'-').replace("{",'-').replace("}",'-').replace("_",'-').replace("=",'-').replace("+",'-').replace(".",'-').replace(",",'-').replace("--",'-').replace("--",'-') # convert to path [a-z\-]
    gFilepath = gFolder + gBlueprintNameFolder + gFilename    # Entire Filepath 

    if ( (actionInputs['eventType'] == "CREATE_BLUEPRINT_VERSION") or (actionInputs['eventType'] == "TEST") ):  

        # Check if file exists
        try:    
            fileExists = gPproject.files.get(file_path=gFilepath, ref='master')
            fileExists = "True"
        except:
            fileExists = "False"

        if (fileExists == "True"):
            print("[ABX] "+fn+" Git - File exists")
            print("[ABX] "+fn+" Git - Updating file...")
            gFileGet = gPproject.files.get(file_path=gFilepath, ref='master')
            gFileGet.content = str(blueprint)   
            gFileGet.save(branch='master', commit_message='Updated by www.kaloferov.com' ) # '+ actionInputs['userName'])' use this to add email
    
        elif (fileExists == "False"):
            print("[ABX] "+fn+" Git - File does not exist")
            print("[ABX] "+fn+" Git - Creating File...")
            gFileCreate = gPproject.files.create({
                'file_path': gFilepath,
                'branch': 'master',
                'content': "Created By ABX",
                'author_email': "www.kaloferov.com", # TODO: replace with actionInputs['userName'] to add email 
                'author_name': "www.kaloferov.com", # TODO: replace with actionInputs['userName'] to add email 
                'encoding': 'base64',
                'commit_message': 'Created by '+ actionInputs['userName']}
                )
            print("[ABX] "+fn+" Git - Adding content to file...")
            gFileGet = gPproject.files.get(file_path=gFilepath, ref='master')
            gFileGet.content = str(blueprint)   
            gFileGet.save(branch='master', commit_message='Updated by www.kaloferov.com' ) # TODO: replace with actionInputs['userName'] to add email 
        else:
            print("")
        # End Loop
    
    elif (actionInputs['eventType'] == "DELETE_BLUEPRINT"):
        print("[ABX] "+fn+" Git - Preparing for deletion...")
        # Check if file exists
        try:    
            fileExists = gPproject.files.get(file_path=gFilepath, ref='master')
            fileExists = "True"
        except:
            fileExists = "False"

        if (fileExists == "True"):
            print("[ABX] "+fn+" Git - File exists")
            gFileDelete = gPproject.files.get(file_path=gFilepath, ref='master')
            gFileDelete_decoded = str(gFileDelete.decode()).lower()
            #blueprintOptionGitlabSyncDeleteTrue = "blueprintOptionGitDelete: true"
            blueprintOptionGitlabSyncDeleteTrue = "gitlabSyncDelete: true"
            print("[ABX] "+fn+" Git - Checking for blueprint option gitlabSyncDelete is set...")
            if (blueprintOptionGitlabSyncDeleteTrue.lower() not in gFileDelete_decoded.lower()):
                print("[ABX] "+fn+" Git - Skipping file deletion based on blueprint option gitlabSyncDelete...")
            elif (blueprintOptionGitlabSyncDeleteTrue.lower() in gFileDelete_decoded.lower()):
                gFileDelete.delete(commit_message='Deleted by ' + actionInputs['userName'], branch='master')
                print("[ABX] "+fn+" Git - File deleted.")
            else:
                print("")
            # End Loop    
            
        elif (fileExists == "False"):
            print("[ABX] "+fn+" Git - File does not exist")
        else:
            print("")
        # End Loop                

    else:
        print("")
    # End Loop    


    # ----- Outputs ----- #

    response = {    # Set action outputs
        # "response": resp_getBlueprint_json
    }
    #print("[ABX] "+fn+" Function return: \n" + json.dumps(response))    # Write function responce to console  
    print("[ABX] "+fn+" Function completed.")   
    
    return response    # Return response 
    # End Function    



def awsSessionManagerGetSecret (context, inputs, awsSecretId_csp, awsSecretId_git, awsRegionName):  # Retrieves AWS Secrets Manager Secrets
    # Ref: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html
    fn = "awsSessionManagerGetSecret -"    # Holds the funciton name. 
    print("[ABX] "+fn+" Function started.")
    
    
    # ----- Script ----- #
        
    # Create a Secrets Manager client
    print("[ABX] "+fn+" AWS Secrets Manager - Creating session...")
    session = boto3.session.Session()
    sm_client = session.client(
        service_name='secretsmanager',
        region_name=awsRegionName
    )

    # Get Secrets
    print("[ABX] "+fn+" AWS Secrets Manager - Getting secret(s)...")
    resp_awsSecret_csp = sm_client.get_secret_value(
            SecretId=awsSecretId_csp
        )
    resp_awsSecret_git = sm_client.get_secret_value(
            SecretId=awsSecretId_git
        )
    #print(awsSecret)
    awsSecret_csp = json.dumps(resp_awsSecret_csp['SecretString']).replace(awsSecretId_csp,'').replace("\\",'').replace('"{"','').replace('"}"','').replace('":"','')   # Cleanup the response to get just the secret
    awsSecret_git = json.dumps(resp_awsSecret_git['SecretString']).replace(awsSecretId_git,'').replace("\\",'').replace('"{"','').replace('"}"','').replace('":"','')   # Cleanup the response to get just the secret
    
    # ----- Outputs ----- #
    
    response = {   # Set action outputs
        "awsSecret_csp" : str(awsSecret_csp),
        "awsSecret_git": str(awsSecret_git),
        }
    print("[ABX] "+fn+" Function completed.")  
    
    return response    # Return response 
    # End Function  
