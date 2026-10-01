from __future__ import annotations
import math
from statistics import mean,pstdev
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Dataset,Experiment,ExperimentGroup,ExperimentDatasetLink,ExperimentRunLink,ExperimentStatus

SYSTEM_PRESETS = [
    {"id":"system-quick","name":"Rápida","description":"Exploración y pruebas funcionales","task_type":"regression","is_default":False,"system":True,
     "parameters":{"generations":30,"Individuals":256,"GenesIndividuals":64,"mutationProb":0.10,"mutationDeleteRateProb":0.05,"sizeTournament":0.15}},
    {"id":"system-standard","name":"Estándar","description":"Configuración equilibrada recomendada","task_type":"regression","is_default":True,"system":True,
     "parameters":{"generations":50,"Individuals":512,"GenesIndividuals":64,"mutationProb":0.10,"mutationDeleteRateProb":0.05,"sizeTournament":0.15}},
    {"id":"system-intensive","name":"Intensiva","description":"Búsqueda más amplia con mayor costo computacional","task_type":"regression","is_default":False,"system":True,
     "parameters":{"generations":100,"Individuals":1024,"GenesIndividuals":128,"mutationProb":0.10,"mutationDeleteRateProb":0.05,"sizeTournament":0.15}},
]

def validation_defaults(value:dict|None=None)->dict:
    v={"strategy":"holdout","train_size":0.75,"test_size":0.25,"random_state":42,"folds":5,"shuffle":True}
    v.update(value or {})
    if v["strategy"] not in {"holdout","kfold"}: raise ValueError("strategy debe ser holdout o kfold")
    train=float(v["train_size"]); test=float(v["test_size"])
    if v["strategy"]=="holdout" and (train<=0 or test<=0 or abs((train+test)-1.0)>1e-6): raise ValueError("train_size + test_size debe ser 1.0")
    if int(v["folds"])<2: raise ValueError("folds debe ser >= 2")
    return v

def create_runs(db:Session,group:ExperimentGroup)->list[Experiment]:
    existing=list(db.scalars(select(ExperimentRunLink).where(ExperimentRunLink.group_id==group.id)))
    if existing: return [db.get(Experiment,x.run_id) for x in existing if db.get(Experiment,x.run_id)]
    links=list(db.scalars(select(ExperimentDatasetLink).where(ExperimentDatasetLink.group_id==group.id).order_by(ExperimentDatasetLink.position)))
    validation=validation_defaults(group.validation)
    created=[]
    folds=int(validation["folds"]) if validation["strategy"]=="kfold" else 1
    base_seed=int(validation["random_state"])
    for dataset_link in links:
        dataset=db.get(Dataset,dataset_link.dataset_id)
        if not dataset: continue
        for repeat in range(group.runs_per_dataset):
            seed=base_seed+repeat
            for fold in range(folds):
                split={**validation,"random_state":seed,"repeat_index":repeat,"fold_index":fold if validation["strategy"]=="kfold" else None}
                params=dict(group.parameters or {})
                params["_genlab_split"]=split
                # These names are forwarded automatically when a future M5GP constructor declares them.
                params.update({"train_size":validation["train_size"],"test_size":validation["test_size"],"random_state":seed,"validation_strategy":validation["strategy"],"cv_folds":validation["folds"]})
                run=Experiment(owner_id=group.owner_id,dataset_id=dataset.id,name=f"{group.name} · {dataset.name} · R{repeat+1}"+(f" F{fold+1}" if folds>1 else ""),task_type=group.task_type,target_column=dataset_link.target_column,parameters=params,status=ExperimentStatus.queued.value,progress={"stage":"queued","percent":0,"message":"Corrida en cola"})
                db.add(run); db.flush()
                db.add(ExperimentRunLink(group_id=group.id,run_id=run.id,repeat_index=repeat,fold_index=fold if folds>1 else None,seed=seed))
                created.append(run)
    group.status="queued"; db.commit()
    return created

def group_runs(db:Session,group_id:str)->list[tuple[ExperimentRunLink,Experiment]]:
    rows=[]
    for link in db.scalars(select(ExperimentRunLink).where(ExperimentRunLink.group_id==group_id).order_by(ExperimentRunLink.created_at)):
        run=db.get(Experiment,link.run_id)
        if run: rows.append((link,run))
    return rows

def aggregate_metrics(db:Session,group:ExperimentGroup)->dict:
    rows=group_runs(db,group.id)
    completed=[r for _,r in rows if r.status==ExperimentStatus.completed.value and isinstance(r.metrics,dict)]
    def collect(section,key):
        vals=[]
        for run in completed:
            source=(run.metrics or {}).get(section,{}) if section else (run.metrics or {})
            value=source.get(key) if isinstance(source,dict) else None
            if isinstance(value,(int,float)) and math.isfinite(float(value)): vals.append(float(value))
        return vals
    keys=["rmse","mse","mae","r2"] if group.task_type=="regression" else ["accuracy","f1_macro","precision_macro","recall_macro"]
    summary={}
    for section in ("train","test"):
        summary[section]={}
        for key in keys:
            vals=collect(section,key)
            if vals: summary[section][key]={"mean":mean(vals),"std":pstdev(vals) if len(vals)>1 else 0.0,"min":min(vals),"max":max(vals),"n":len(vals)}
    statuses={}
    for _,run in rows: statuses[run.status]=statuses.get(run.status,0)+1
    return {"experiment_id":group.id,"task_type":group.task_type,"total_runs":len(rows),"completed_runs":len(completed),"status_counts":statuses,"metrics":summary}

def serialize_group(db:Session,group:ExperimentGroup,include_runs:bool=True)->dict:
    datasets=[]
    for link in db.scalars(select(ExperimentDatasetLink).where(ExperimentDatasetLink.group_id==group.id).order_by(ExperimentDatasetLink.position)):
        ds=db.get(Dataset,link.dataset_id)
        if ds: datasets.append({"dataset_id":ds.id,"dataset_name":ds.name,"target_column":link.target_column})
    rows=group_runs(db,group.id)
    statuses=[run.status for _,run in rows]
    if statuses:
        if all(s==ExperimentStatus.completed.value for s in statuses): status="completed"
        elif any(s in {ExperimentStatus.running.value,ExperimentStatus.reserved.value} for s in statuses): status="running"
        elif any(s==ExperimentStatus.queued.value for s in statuses): status="queued"
        elif all(s in {ExperimentStatus.failed.value,ExperimentStatus.cancelled.value,ExperimentStatus.rejected.value} for s in statuses): status="failed"
        else: status=group.status
    else: status=group.status
    payload={"id":group.id,"name":group.name,"task_type":group.task_type,"parameters":group.parameters or {},"validation":group.validation or {},"runs_per_dataset":group.runs_per_dataset,"preset_name":group.preset_name,"status":status,"created_at":group.created_at,"datasets":datasets,"summary":aggregate_metrics(db,group)}
    if include_runs:
        payload["runs"]=[{"id":run.id,"name":run.name,"dataset_id":run.dataset_id,"status":run.status,"repeat_index":link.repeat_index,"fold_index":link.fold_index,"seed":link.seed,"metrics":run.metrics,"progress":run.progress,"created_at":run.created_at,"finished_at":run.finished_at} for link,run in rows]
    return payload
