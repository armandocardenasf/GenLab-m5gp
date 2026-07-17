export type User={id:string,email:string,full_name:string,active:boolean,created_at:string};
export type Dataset={id:string,name:string,original_name:string,rows:number,columns:number,column_names:string[],dtypes:Record<string,string>,created_at:string};
export type DatasetPreview={columns:string[],rows:Array<Record<string,unknown>>};
export type GenerationPoint={generation:number,fit:number};
export type TestResults={task_type:'regression'|'classification',sample:number[],actual:number[],prediction:number[],total_points:number,displayed_points:number};
export type ConfusionMatrix={classes:Array<string|number>,matrix:number[][]};
export type ExperimentVisualization={task_type:'regression'|'classification',generation_history:GenerationPoint[],fit_label:string,test_results:TestResults,confusion_matrix?:ConfusionMatrix};
export type Experiment={id:string,dataset_id:string,name:string,task_type:'regression'|'classification',target_column:string,parameters:Record<string,unknown>,status:string,gpu_id:number|null,worker_pid:number|null,progress:Record<string,any>,metrics:Record<string,any>|null,symbolic_model:string|null,complexity:string|null,error:string|null,cancel_requested:boolean,created_at:string,started_at:string|null,finished_at:string|null};
export type GPU={id:number,name:string,memory_total_mb:number|null,busy:boolean,experiment_id:string|null};

export type LocalizedText={es:string,en:string};
export type AboutReference={name:string,repository_url:string,citation:string,doi_url:string|null};
export type AboutInfo={
  product_name:string;
  full_name:LocalizedText;
  version:string;
  release_channel:string;
  copyright:{year:number,holder:string,role:LocalizedText,notice:LocalizedText};
  supporting_institutions:string[];
  acknowledgements:LocalizedText;
  references:AboutReference[];
  source_code:{repository_url:string,download_url:string};
  legal:{
    public_source:boolean;
    open_source_intent:boolean;
    license_name:LocalizedText;
    license_url:string;
    terms:LocalizedText;
    disclaimer:LocalizedText;
  };
};
