from .src.m5gp import m5gp

import pandas as pd

hyper_params = [
    {
        "generations": (30,),
        "Individuals": (128,),
        "GenesIndividuals": (128,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.25,),
    },
    {
        "generations": (30,),
        "Individuals": (128,),
        "GenesIndividuals": (128,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.15,),
    },
    {
        "generations": (30,),
        "Individuals": (128,),
        "GenesIndividuals": (128,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.1,),
    },
    {
        "generations": (30,),
        "Individuals": (128,),
        "GenesIndividuals": (256,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.1,),
    },
    {
        "generations": (30,),
        "Individuals": (256,),
        "GenesIndividuals": (256,),
        "mutationProb": (0.15,),
        "sizeTournament": (0.15,),
    },
    {
        "generations": (50,),
        "Individuals": (128,),
        "GenesIndividuals": (128,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.25,),
    },
    {
        "generations": (50,),
        "Individuals": (256,),
        "GenesIndividuals": (128,),
        "mutationProb": (0.1,),
        "sizeTournament": (0.15,),
    },
]

functions_set = [
    "+", "-", "*", "/", "sin", "cos", "tan", "tanh",
    "sqrt", "exp", "log", "abs",
]

print("Running m5gp ...")

est = m5gp.m5gpRegressor(
    generations=30,
    Individuals=256,
    GenesIndividuals=128,
    mutationProb=0.1,
    mutationDeleteRateProb=0.01,
    sizeTournament=0.15,
    evaluationMethod=2,
    scorer=0,
    maxRandomConstant=1,
    genOperatorProb=0.50,
    genVariableProb=0.39,
    genConstantProb=0.1,
    genNoopProb=0.01,
    useOpIF=0,
    functions_set=functions_set,
    log=1,
    verbose=1,
    logPath="log/",
)


def complexity(estimator):
    print("Complexity:", estimator.get_n_nodes())
    return estimator.get_n_nodes()


def model(estimator):
    return str(estimator.best_individual())
