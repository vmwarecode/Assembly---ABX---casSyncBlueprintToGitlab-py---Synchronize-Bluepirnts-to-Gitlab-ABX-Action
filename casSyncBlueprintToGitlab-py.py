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
  #      - All blueprints can be synchronized or only selected once by setting blueprint option blueprintOptionGitSync
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
  #         - runOnCustomPorpertyMatchABXIn: see below
  #         - blueprintIdABXIn (String): Id of the blueprint to be synchronized with Git. 
  #         - blueprintNameABXIn (String): Name of the blueprint to be synchronized with Git. 
  #         - blueprintVersionABXIn (String): Blueprint release version to be synchronized with Git. 
  #   - actionOptionRunOnCustomPropertyIn (Boolean): RunOn custom property condition
  #      - True: Check for runOn condition
  #         - runOnCustomPropertyIn (String): Custom property key/value to match for when actionOptionRunOnCustomPropertyIn=True ( e.g. cloudZoneProp: cas.cloud.zone.type:aws )
  #         - runOnCustomPorpertyMatchABXIn (String): Custom property key/value to match actionOptionRunOnCustomPropertyIn=True and actionOptionAcceptPayloadInputIn=False. For ABX testing. ( e.g. cloudZoneProp: cas.cloud.zone.type:aws )
  #      - False: Do not check for runOn condition
  #   - actionOptionRunOnBlueprintOptionIn (Boolean): RunOn blueprint option condition
  #      - True: Check for runOn condition
  #         - runOnBlueprintOptionIn (String): Blueprint property key/value to match for when actionOptionRunOnBlueprintOptionIn=True (e.g. blueprintOptionsGitSync: true)
  #         - runOnBlueprintOptionMatchABXIn (String): Blueprint property key/value to match for when actionOptionRunOnBlueprintOptionIn=True and actionOptionAcceptPayloadInputIn=False. For ABX testing. (e.g. blueprintOptionsGitSync: true)
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
  #      - blueprint.version.configuration: Subscribe here for blueprint versioning events like create / release / un-release / restore > Only create version enabled.
  # [Thanks]
  #   - Thanks to Dana Gertsch (https://www.linkedin.com/in/danagertsch/) for his work with ABX and AWS Systems Manager which gave me the idea to use AWS Secrets Manager https://knotacoder.com/2020/05/11/using-aws-ssm-parameters-with-vra-cloud-abx-actions/
  


import json
import yaml 
import logging
import boto3
import requests
import gitlab
import urllib3
import boto3
#import base64


# ----- Global ----- #  

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)   # Warned when making an unverified HTTPS request.
urllib3.disable_warnings(urllib3.exceptions.DependencyWarning)   # Warned when an attempt is made to import a module with missing optional dependencies. 
cspBaseApiUrl = "https://api.mgmt.cloud.vmware.com"    # CSP portal base url


# ----- Functions  ----- # 

def handler(context, inputs):   # Action entry function.

    fn = "handler -"    # Holds the funciton name. 
    print("[ABX] "+fn+" Action started.")
    print("[ABX] "+fn+" Function started.")
    
    if ( (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION") or (inputs['eventType'] == "DELETE_BLUEPRINT") ):  # Runs only for selected event types
        
        print("[ABX] "+fn+" Runnig for eventType: " + inputs['eventType'])
        
        
        # ----- Action Options  ----- # 
        
        actionOptionAcceptPayloadInput = inputs['actionOptionAcceptPayloadInputIn']    # If set to False inputs from deployment payload will be ignored in favor of action inputs. 
        actionOptionRunOnCustomProperty = inputs['actionOptionRunOnCustomPropertyIn']    # Run only if given constraint , passed via custom peorprty , matches azure endpoint. 
        actionOptionRunOnBlueprintOption = inputs['actionOptionRunOnBlueprintOptionIn']    # Accept blueprint options or not
        actionOptionUseAwsSecretsManager = inputs['actionOptionUseAwsSecretsManagerIn']    # Set to True to use AWS Secrets Manager. Set to false to provide secrets via action inputs
        awsSmCspTokenSecretId = inputs['awsSmCspTokenSecretIdIn']  # AWS Secrets Manager CSP Token Secret ID
        awsSmGitTokenSecretId = inputs['awsSmGitTokenSecretIdIn']  # AWS Secrets Manager GIT Token Secret ID
        awsSmRegionName = inputs['awsSmRegionNameIn']  # AWS Secrets Manager Region Name e.g. us-west-2
        runOnCustomProperty = inputs['runOnCustomPropertyIn']   # Custom property key/value <<< TODO: SET for actionOptionRunOnCustomPropertyIn=True >>> 
        runOnBlueprintOption = inputs['runOnBlueprintOptionIn']    # Blueprint option key/value <<< TODO: SET for actionOptionRunOnBlueprintOptionIn=True >>> 
        cspRefreshToken = inputs['cspRefreshTokenIn']   # CSP Refresh Token
        gitPrivateToken = inputs['gitPrivateTokenIn']   # Git Refresh Token
        gitProjectFolder = inputs['gitProjectFolderIn']   # Git project folder e.g. cloud-assembly/blueprints-auto-sync/
        gitProjectId = inputs['gitProjectIdIn']   # Git project folder e.g. 14854581
        
        print("[ABX] "+fn+" actionOptionAcceptPayloadInput: " + actionOptionAcceptPayloadInput)    
        print("[ABX] "+fn+" actionOptionRunOnCustomProperty: " + actionOptionRunOnCustomProperty)
        print("[ABX] "+fn+" actionOptionRunOnBlueprintOption: " + actionOptionRunOnBlueprintOption)
        print("[ABX] "+fn+" actionOptionUseAwsSecretsManager: " + actionOptionUseAwsSecretsManager)
        print("[ABX] "+fn+" awsSmCspTokenSecretId: " + awsSmCspTokenSecretId)
        print("[ABX] "+fn+" awsSmGitTokenSecretId: " + awsSmGitTokenSecretId)
        print("[ABX] "+fn+" awsSmRegionName: " + awsSmRegionName)
        print("[ABX] "+fn+" runOnCustomProperty: " + runOnCustomProperty)
        print("[ABX] "+fn+" runOnBlueprintOption: " + runOnBlueprintOption )
        print("[ABX] "+fn+" gitProjectFolder: " + gitProjectFolder)
        print("[ABX] "+fn+" gitProjectId: " + str(gitProjectId) )
        
        actionInputs = {}  #  build json with the action inputs 
        actionInputs['actionOptionAcceptPayloadInput'] = actionOptionAcceptPayloadInput
        actionInputs['actionOptionRunOnBlueprintOption'] = actionOptionRunOnBlueprintOption
        actionInputs['actionOptionRunOnCustomProperty'] = actionOptionRunOnCustomProperty
        actionInputs['actionOptionUseAwsSecretsManager'] = actionOptionUseAwsSecretsManager
        actionInputs['awsSmCspTokenSecretId'] = awsSmCspTokenSecretId 
        actionInputs['awsSmGitTokenSecretId'] = awsSmGitTokenSecretId 
        actionInputs['awsSmRegionName'] = awsSmRegionName 
        actionInputs['runOnCustomProperty'] = runOnCustomProperty 
        actionInputs['runOnBlueprintOption'] = runOnBlueprintOption
        actionInputs['cspRefreshToken'] = cspRefreshToken
        actionInputs['gitPrivateToken'] = gitPrivateToken
        actionInputs['gitProjectFolder'] = gitProjectFolder
        actionInputs['gitProjectId'] = gitProjectId


        # ----- AWS Secrets Manager  ----- #     
        
        # Get AWS Secrets Manager Secrets
        if (actionOptionUseAwsSecretsManager.lower() == "True".lower()):
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
            print('')


        # ----- CSP Token  ----- #     
        
        # Get Token
        getRefreshToken_apiUrl = cspBaseApiUrl + "/iaas/api/login"  # Set API URL
        body = {    # Set call body
            "refreshToken": cspRefreshToken
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
        csp = {}
        csp['bearerToken'] = bearerToken
        csp['requestsHeaders'] = requestsHeaders
        
        
        # ----- Action Inputs  ----- #     
    
        blueprintId = inputs['blueprintIdABXIn']    # Blueprint ID
        blueprintVersion = inputs['blueprintVersionABXIn']
        blueprintName = inputs['blueprintNameABXIn']
        runOnCustomPorpertyMatch = inputs['runOnCustomPorpertyMatchABXIn']   # Property to match against when deciding weather to run the action or not. Alternative to Event Topic Condition filterring
        runOnBlueprintOptionMatch = inputs['runOnBlueprintOptionMatchABXIn']    # Blueprint Option gitSync

        if (actionOptionAcceptPayloadInput == 'True'):     # Loop. If Payload exists and Accept Payload input action option is set to True , accept payload inputs . Else except action inputs.
            print("[ABX] "+fn+" Using PAYLOAD inputs based on actionOptionAcceptPayloadInputIn action option")
            
            # blueprintId / blueprintVersion / blueprintName
            if (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION"):
                blueprintId = inputs['blueprintId']
                blueprintVersion = inputs['version']
                blueprintName = inputs['blueprintName']
            else :  # (inputs['eventType'] == "DELETE_BLUEPRINT")
                blueprintId = inputs['id']    
                blueprintVersion = ""
                blueprintName = inputs['name']

            # End Loop
            
            actionInputs['blueprintId'] = blueprintId
            actionInputs['blueprintVersion'] = blueprintVersion
            actionInputs['blueprintName'] = blueprintName
            
            
            # runOnCustomPorpertyMatch
            if (actionOptionRunOnCustomProperty == "True"):    # Loop. Get property to match against. 
                runOnCustomPorpertyMatch = (json.dumps(inputs['customProperties'])).replace('"','')
            else:
                print('')
                # Get value from action inputs
            # End Loop
    
            # runOnBlueprintOptionMatch
            if (actionOptionRunOnBlueprintOption == "True"):    # Loop. Get property to match against. 
                print("[ABX] "+fn+" Using BLUEPRINT for blueprintOptions based on actionOptionRunOnBlueprintOptionIn action option")
                print("[ABX] "+fn+" Getting blueprintOptions...")
                body = {}
                resp_blueprintOptions_callUrl = cspBaseApiUrl + '/blueprint/api/blueprints/'+blueprintId+'?$select=*&apiVersion=2019-09-12'
                resp_blueprintOptions_call = requests.get(resp_blueprintOptions_callUrl, data=json.dumps(body), verify=False, headers=(csp['requestsHeaders']))
                runOnBlueprintOptionMatch = str(json.loads(resp_blueprintOptions_call.text))
            else:
                print('')
                # Get value from action inputs
            # End Loop
    
        elif (actionOptionAcceptPayloadInput == 'False'):
            print("[ABX] "+fn+" Using ACTION inputs for ABX action based on actionOptionAcceptPayloadInputIn action option")
            print("[ABX] "+fn+" Using ACTION inputs for blueprintOptions based on actionOptionRunOnBlueprintOptionIn action option")
            # Get values from action inputs
        else: 
            print("[ABX] "+fn+" INVALID action inputs based on actionOptionAcceptPayloadInputIn action option")
        # End Loop
    
        actionInputs['blueprintId'] = blueprintId
        print("[ABX] "+fn+" blueprintId: " + blueprintId)
        actionInputs['runOnCustomPorpertyMatch'] = runOnCustomPorpertyMatch    
        #print("[ABX] "+fn+" runOnCustomPorpertyMatch: " + runOnCustomPorpertyMatch)
        actionInputs['runOnBlueprintOptionMatch'] = runOnBlueprintOptionMatch    
        #print("[ABX] "+fn+" runOnBlueprintOptionMatch: " + runOnBlueprintOptionMatch)
     
     
        # ----- Evals ----- # 
        
        evals = {}  # Holds evals values
        
        # Run Evals only for stages that have properties . E.g. in Delete and other stages blueprint will not be available
        if (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION"):
            # runOnCustomProperty eval
            if ((actionOptionRunOnCustomProperty == "True") and (runOnCustomProperty.lower() in runOnCustomPorpertyMatch.lower())):   # Loop. RunOn eval.
                runOnCustomProperty_eval = "True"
            elif ((actionOptionRunOnCustomProperty == "True") and (runOnCustomProperty.lower() not in runOnCustomPorpertyMatch.lower())):
                runOnCustomProperty_eval = "False"
            else:
                runOnCustomProperty_eval = "Not Evaluated"
            # End Loop
        
            # runOnBlueprintOption  eval
            if ((actionOptionRunOnBlueprintOption == 'True') and (runOnBlueprintOption.lower() in runOnBlueprintOptionMatch.lower())):     # Loop. RunOn eval.
                runOnBlueprintOption_eval = "True"
            elif ((actionOptionRunOnBlueprintOption == 'True') and (runOnBlueprintOption.lower() not in runOnBlueprintOptionMatch.lower())):  
                runOnBlueprintOption_eval = "False"
            else:  
                runOnBlueprintOption_eval = "Not Evaluated"
            # End Loop
        else:   
            runOnCustomProperty_eval = "Not Evaluated"
            runOnBlueprintOption_eval = "Not Evaluated"
        # End Loop

        evals['runOnCustomProperty_eval'] = runOnCustomProperty_eval
        print("[ABX] "+fn+" runOnCustomProperty_eval: " + runOnCustomProperty_eval)        
        evals['runOnBlueprintOption_eval'] = runOnBlueprintOption_eval
        print("[ABX] "+fn+" runOnBlueprintOption_eval: " + runOnBlueprintOption_eval)
    
    
        # ----- Function Calls  ----- # 
        
        if (runOnCustomProperty_eval != 'False' and runOnBlueprintOption_eval != 'False'): 
            print("[ABX] "+fn+" runOnProperty matched or actionOptionRunOnCustomPropertyIn action option disabled.")
            print("[ABX] "+fn+" runOnBlueprintOption matched or actionOptionRunOnBlueprintOptionIn action option disabled.")
            print("[ABX] "+fn+" Running myActionFunction...")
            resp_myActionFunction = myActionFunction (context, inputs, actionInputs, evals, csp)     # Call function
        else:
            print("[ABX] "+fn+" Skipping action based on RunOn action option(s).")
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

    else:
        print("[ABX] "+fn+" Not set to run for eventType: " + inputs['eventType'])
    # End Function



def myActionFunction (context, inputs, actionInputs, evals, csp):   # Main Function. 
    fn = "myActionFunction -"    # Holds the funciton name. 
    print("[ABX] "+fn+" Action started.")
    print("[ABX] "+fn+" Function started.")
    
    
    # ----- Script ----- #

    # Get Blueprint
    resp_getBlueprint_json = {}
    if (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION"):
        body = {}
        print("[ABX] "+fn+" Getting Blueprint...")
        resp_getBlueprint_callUrl = cspBaseApiUrl + '/blueprint/api/blueprints/'+actionInputs['blueprintId']+'?$select=*&apiVersion=2019-09-12'
        resp_getBlueprint_call = requests.get(resp_getBlueprint_callUrl, data=json.dumps(body), verify=False, headers=(csp['requestsHeaders']) )
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
    gFilepath = gFolder + gBlueprintName + gFilename    # Entire Filepath 
    casUser = inputs['__metadata']['userName']

    if (inputs['eventType'] == "CREATE_BLUEPRINT_VERSION"):

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
            gFileGet.save(branch='master', commit_message='Updated by www.kaloferov.com' ) # '+ casUser)' use this to add email
    
        elif (fileExists == "False"):
            print("[ABX] "+fn+" Git - File does not exist")
            print("[ABX] "+fn+" Git - Creating File...")
            gFileCreate = gPproject.files.create({
                'file_path': gFilepath,
                'branch': 'master',
                'content': "Created By ABX",
                'author_email': casUser,
                'author_name': casUser,
                'encoding': 'base64',
                'commit_message': 'Created by '+ casUser}
                )
            print("[ABX] "+fn+" Git - Adding content to file...")
            gFileGet = gPproject.files.get(file_path=gFilepath, ref='master')
            gFileGet.content = str(blueprint)   
            gFileGet.save(branch='master', commit_message='Updated by www.kaloferov.com' ) # '+ casUser)' use this to add email
        else:
            print("")
        # End Loop
    
    elif (inputs['eventType'] == "DELETE_BLUEPRINT"):
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
            BlueprintOptionGitDeleteTrue = "blueprintOptionGitDelete: true"
            print("[ABX] "+fn+" Git - Checking for blueprintOptionGitDelete is set...")
            if (BlueprintOptionGitDeleteTrue.lower() not in gFileDelete_decoded.lower()):
                print("[ABX] "+fn+" Git - Skipping file deletion based on blueprintOptionGitDelete blueprint option...")
            elif (BlueprintOptionGitDeleteTrue.lower() in gFileDelete_decoded.lower()):
                gFileDelete.delete(commit_message='Deleted by ' + casUser, branch='master')
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
