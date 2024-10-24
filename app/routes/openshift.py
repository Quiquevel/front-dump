from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, validator
from middleware.authorization import is_devops
from functions.dyna import getEnvironmentsClustersList, dynatraceTreatment

pod_delete = APIRouter(tags=["v1"])
alerting_status = APIRouter(tags=["v1"])

environmentList = getEnvironmentsClustersList("spain")

class pod_2_delete(BaseModel):
    functionalEnvironment: str
    cluster: str
    region: str
    namespace: str
    pod: list

    @validator("functionalEnvironment")
    def validate_environment(cls, v):
        if not any(x in v for x in ["dev","pre","pro"]):
            raise HTTPException(status_code=400, detail=f"{v} value is not valid for functionalEnvironment")
        return v
    
    #To validate the cluster parameter.
    @validator("cluster")
    def validate_cluster(cls, v):
        if not any(x in v for x in ["ohe","bks","probks","dmzbbks","dmzbazure","ocp05azure","ohe","probks","dmzbbks","azure","prodarwin","dmzbdarwin","proohe","dmzbohe","confluent"]):
            raise HTTPException(status_code=400, detail=f"{v} value is not valid for cluster")
        return v
    
    @validator("namespace")
    def validate_namespace(cls,v):
        return v
    
    #to validate the region parameter
    @validator("region")
    def validate_region(cls, v):
        if not any(x in v for x in ["bo1","bo2","weu1","weu2"]):
            raise HTTPException(status_code=400, detail=f"{v} value is not valid for region")
        return v

class check_token(BaseModel):
    ldap: str

class DynaModel(BaseModel):
    functionalEnvironment: str
    timedyna: str = None
 
    @validator("functionalEnvironment")
    def validate_environment(cls, v):        
        if not any(x == v for x in environmentList):
            raise HTTPException(status_code = 400, detail=f"{v} value is not valid for functionalEnvironment")
        return v
    
@alerting_status.post("/dynatrace", tags = ["v1"], description = "GET DYNATRACE ALERT", response_description = "JSON", status_code = 200)
async def get_dynatrace_alert(target: DynaModel):
    return await dynatraceTreatment(functionalEnvironment = target.functionalEnvironment, timedyna = target.timedyna)