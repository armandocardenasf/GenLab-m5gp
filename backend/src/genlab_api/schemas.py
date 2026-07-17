from __future__ import annotations
from datetime import datetime
from typing import Literal,Any
from pydantic import BaseModel,EmailStr,Field,ConfigDict,field_validator,model_validator
class UserCreate(BaseModel): email:EmailStr; full_name:str=Field(min_length=2,max_length=200); password:str=Field(min_length=10,max_length=200)
class Login(BaseModel): email:EmailStr; password:str
class RefreshRequest(BaseModel): refresh_token:str
class LogoutRequest(BaseModel): refresh_token:str
class UserOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:str; email:EmailStr; full_name:str; active:bool; created_at:datetime
class TokenPair(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"; expires_in:int
class DatasetOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:str; name:str; original_name:str; rows:int; columns:int; column_names:list[str]; dtypes:dict; created_at:datetime
class DatasetPreview(BaseModel): columns:list[str]; rows:list[dict[str,Any]]
class ExperimentCreate(BaseModel):
    name:str=Field(min_length=2,max_length=200); dataset_id:str; task_type:Literal["regression","classification"]; target_column:str; parameters:dict[str,Any]=Field(default_factory=dict)
    @field_validator("parameters")
    @classmethod
    def protect_parameters(cls,v):
        forbidden={"_progress_callback","_cancel_callback","owner_id","artifact_dir"}
        if forbidden.intersection(v): raise ValueError("Parámetros internos no permitidos")
        return v

    @model_validator(mode="after")
    def validate_task_parameters(self):
        parameters=dict(self.parameters or {})
        if self.task_type == "classification":
            evaluation_method=int(parameters.get("evaluationMethod",0))
            scorer=int(parameters.get("scorer",0))
            average_mode=str(parameters.get("averageMode","macro"))
            k=int(parameters.get("k",3))
            if evaluation_method not in {0,1,2,3}:
                raise ValueError(
                    "Para clasificación evaluationMethod debe ser 0, 1, 2 o 3"
                )
            if scorer not in {0,1,2,3}:
                raise ValueError(
                    "Para clasificación scorer debe ser 0, 1, 2 o 3"
                )
            if average_mode not in {"micro","macro","weighted","samples"}:
                raise ValueError("averageMode inválido para clasificación")
            if k < 2:
                raise ValueError("k debe ser mayor o igual que 2")
            parameters.setdefault("evaluationMethod",0)
            parameters.setdefault("scorer",0)
            parameters.setdefault("crossVal",True)
            parameters.setdefault("k",3)
            parameters.setdefault("averageMode","macro")
            parameters.setdefault("CrossAverage",False)
        else:
            evaluation_method=int(parameters.get("evaluationMethod",4))
            scorer=int(parameters.get("scorer",0))
            if evaluation_method not in set(range(0,11)):
                raise ValueError(
                    "Para regresión evaluationMethod debe estar entre 0 y 10"
                )
            if scorer not in {0,1,2}:
                raise ValueError(
                    "Para regresión scorer debe ser 0, 1 o 2"
                )
            parameters.setdefault("evaluationMethod",4)
            parameters.setdefault("scorer",0)
        self.parameters=parameters
        return self
class ExperimentOut(BaseModel):
    model_config=ConfigDict(from_attributes=True); id:str; dataset_id:str; name:str; task_type:str; target_column:str; parameters:dict; status:str; gpu_id:int|None; worker_pid:int|None; progress:dict; metrics:dict|None; symbolic_model:str|None; complexity:str|None; error:str|None; cancel_requested:bool; created_at:datetime; started_at:datetime|None; finished_at:datetime|None
class GPUOut(BaseModel): id:int; name:str; memory_total_mb:int|None; busy:bool; experiment_id:str|None=None; user_id:str|None=None; acquired_at:datetime|None=None

class LocalizedText(BaseModel):
    es: str
    en: str


class AboutCopyright(BaseModel):
    year: int
    holder: str
    role: LocalizedText
    notice: LocalizedText


class AboutReference(BaseModel):
    name: str
    repository_url: str
    citation: str
    doi_url: str | None = None


class AboutSourceCode(BaseModel):
    repository_url: str
    download_url: str


class AboutLegal(BaseModel):
    public_source: bool
    open_source_intent: bool
    license_name: LocalizedText
    license_url: str
    terms: LocalizedText
    disclaimer: LocalizedText


class AboutOut(BaseModel):
    product_name: str
    full_name: LocalizedText
    version: str
    release_channel: str
    copyright: AboutCopyright
    supporting_institutions: list[str]
    acknowledgements: LocalizedText
    references: list[AboutReference]
    source_code: AboutSourceCode
    legal: AboutLegal
