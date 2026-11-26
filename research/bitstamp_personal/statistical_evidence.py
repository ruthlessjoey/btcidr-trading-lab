"""Offline DSR and paired moving-block bootstrap for OOS return series."""
from __future__ import annotations
import math, random
from collections.abc import Sequence

class StatisticalEvidenceError(ValueError):
    """Invalid return series or statistical configuration."""

def _series(values,name,minimum=30):
    if isinstance(values,(str,bytes)) or not isinstance(values,Sequence) or len(values)<minimum:
        raise StatisticalEvidenceError(f"{name} requires a numeric sequence of at least {minimum} observations")
    out=[]
    for i,v in enumerate(values):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or float(v)<=-1:
            raise StatisticalEvidenceError(f"{name}[{i}] must be finite and greater than -100%")
        out.append(float(v))
    return out

def _moments(x):
    n=len(x); mean=math.fsum(x)/n; c=[v-mean for v in x]
    m2=math.fsum(v*v for v in c)/n
    if not math.isfinite(m2): raise StatisticalEvidenceError("return variance must be finite")
    if m2<=0:
        if mean==0: return 0.0,0.0,3.0
        raise StatisticalEvidenceError("constant non-zero return series has undefined Sharpe")
    sharpe=mean/math.sqrt(math.fsum(v*v for v in c)/(n-1))
    skew=math.fsum(v**3 for v in c)/n/(m2**1.5)
    kurt=math.fsum(v**4 for v in c)/n/(m2**2)
    if not all(map(math.isfinite,(sharpe,skew,kurt))): raise StatisticalEvidenceError("return moments are not finite")
    return sharpe,skew,kurt

def _ppf(p):
    if not 0<p<1: raise StatisticalEvidenceError("normal quantile probability must be in (0,1)")
    a=(-39.69683028665376,220.9460984245205,-275.9285104469687,138.3577518672690,-30.66479806614716,2.506628277459239)
    b=(-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771972,-13.28068155288572)
    c=(-.007784894002430293,-.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783)
    d=(.007784695709041462,.3224671290700398,2.445134137142996,3.754408661907416)
    if p<.02425:
        q=math.sqrt(-2*math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p>1-.02425:
        q=math.sqrt(-2*math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q=p-.5; r=q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def deflated_sharpe_probability(candidate_returns,registered_trial_return_series,*,registered_trial_count):
    """PSR against expected-max-Sharpe threshold; returns are unannualized per-period."""
    candidate=_series(candidate_returns,"candidate_returns")
    if isinstance(registered_trial_count,bool) or not isinstance(registered_trial_count,int) or registered_trial_count<2:
        raise StatisticalEvidenceError("registered_trial_count must be an integer >= 2")
    if isinstance(registered_trial_return_series,(str,bytes)) or not isinstance(registered_trial_return_series,Sequence):
        raise StatisticalEvidenceError("trial return series must be a sequence")
    if not 2<=len(registered_trial_return_series)<=registered_trial_count:
        raise StatisticalEvidenceError("supply 2..registered_trial_count completed trial series")
    trials=[_series(v,f"trial[{i}]") for i,v in enumerate(registered_trial_return_series)]
    if any(len(v)!=len(candidate) for v in trials): raise StatisticalEvidenceError("all trial series must have equal observation counts")
    if candidate not in trials: raise StatisticalEvidenceError("candidate series must be included in trial series")
    sr,skew,kurt=_moments(candidate)
    sharpes=[_moments(v)[0] for v in trials]
    avg=math.fsum(sharpes)/len(sharpes)
    dispersion=math.sqrt(math.fsum((v-avg)**2 for v in sharpes)/(len(sharpes)-1))
    gamma=.5772156649015329; n=registered_trial_count
    threshold=dispersion*((1-gamma)*_ppf(1-1/n)+gamma*_ppf(1-1/(n*math.e)))
    denom=1-skew*sr+((kurt-1)/4)*(sr**2)
    if not math.isfinite(denom) or denom<=0: raise StatisticalEvidenceError("DSR variance adjustment must be positive")
    z=(sr-threshold)*math.sqrt(len(candidate)-1)/math.sqrt(denom)
    return {"deflated_sharpe_probability":.5*(1+math.erf(z/math.sqrt(2))),"candidate_sharpe_per_period":sr,
      "expected_max_sharpe_threshold_per_period":threshold,"trial_sharpe_dispersion":dispersion,
      "registered_trial_count":n,"completed_trial_series_count":len(trials),"observations":len(candidate),
      "skewness":skew,"non_excess_kurtosis":kurt,
      "method":"PSR against expected maximum Sharpe; Euler-Mascheroni order-statistic approximation"}

def paired_moving_block_bootstrap_lower_bound(strategy_returns,benchmark_returns,*,block_length=24,replicates=5000,confidence_level=.95,seed=0):
    """Deterministic paired circular moving-block bootstrap of mean excess return."""
    a=_series(strategy_returns,"strategy_returns"); b=_series(benchmark_returns,"benchmark_returns")
    if len(a)!=len(b): raise StatisticalEvidenceError("strategy and benchmark series must have equal length")
    n=len(a)
    if isinstance(block_length,bool) or not isinstance(block_length,int) or not 1<=block_length<=n:
        raise StatisticalEvidenceError("block_length must be within the observation count")
    if isinstance(replicates,bool) or not isinstance(replicates,int) or replicates<1000:
        raise StatisticalEvidenceError("replicates must be an integer >= 1000")
    if isinstance(confidence_level,bool) or not isinstance(confidence_level,(int,float)) or not .5<confidence_level<1:
        raise StatisticalEvidenceError("confidence_level must be in (.5,1)")
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0: raise StatisticalEvidenceError("seed must be nonnegative integer")
    diff=[x-y for x,y in zip(a,b)]; rng=random.Random(seed); means=[]; blocks=math.ceil(n/block_length)
    for _ in range(replicates):
        sample=[]
        for _ in range(blocks):
            start=rng.randrange(n)
            for j in range(block_length):
                if len(sample)==n: break
                sample.append(diff[(start+j)%n])
        means.append(math.fsum(sample)/n)
    means.sort(); pos=(1-confidence_level)*(replicates-1); lo=math.floor(pos); hi=math.ceil(pos); frac=pos-lo
    bound=means[lo] if lo==hi else means[lo]*(1-frac)+means[hi]*frac
    return {"paired_bootstrap_mean_excess":math.fsum(diff)/n,"bootstrap_excess_ci_lower":bound,
      "confidence_level":float(confidence_level),"block_length":block_length,"replicates":replicates,"seed":seed,
      "method":"paired circular moving-block bootstrap of per-period strategy-minus-benchmark returns"}
