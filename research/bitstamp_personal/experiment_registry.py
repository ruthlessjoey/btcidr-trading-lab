"""Append-only event-sourced ledger of preregistered market/strategy trials."""
from __future__ import annotations
import hashlib,json
from datetime import date
from pathlib import Path
class TrialRegistryError(ValueError): pass
FIELDS={"trial_id","market_symbol","strategy_id","preregistration_id","event","registered_date"}
EVENTS={"REGISTERED","COMPLETED","FAILED","ABANDONED"}
TERMINAL={"COMPLETED","FAILED","ABANDONED"}
def _unique_pairs(pairs):
 out={}
 for k,v in pairs:
  if k in out: raise TrialRegistryError(f"duplicate JSON key: {k}")
  out[k]=v
 return out
def parse_trial_registry(raw:bytes,*,expected_market_symbols,expected_strategies,preregistration_id):
 if not isinstance(raw,bytes) or not raw: raise TrialRegistryError("registry must be non-empty bytes")
 try: text=raw.decode("utf-8")
 except UnicodeDecodeError as e: raise TrialRegistryError("registry must be UTF-8") from e
 expected={f"{preregistration_id}:{m}:{s}" for m in expected_market_symbols for s in expected_strategies}
 states={}; registered=set(); events=0
 for line_no,line in enumerate(text.splitlines(),1):
  if not line.strip(): raise TrialRegistryError(f"blank registry line at {line_no}")
  try: row=json.loads(line,object_pairs_hook=_unique_pairs)
  except (json.JSONDecodeError,TrialRegistryError,RecursionError) as e: raise TrialRegistryError(f"invalid registry JSON at line {line_no}: {e}") from e
  if not isinstance(row,dict) or set(row)!=FIELDS: raise TrialRegistryError(f"line {line_no} must contain exactly the required fields")
  m,s,trial=row["market_symbol"],row["strategy_id"],row["trial_id"]
  if not all(isinstance(v,str) and v for v in (m,s,trial,row["preregistration_id"],row["event"],row["registered_date"])):
   raise TrialRegistryError(f"line {line_no} contains a non-string or empty identity field")
  if m not in expected_market_symbols or s not in expected_strategies: raise TrialRegistryError(f"unknown market or strategy at line {line_no}")
  if trial!=f"{preregistration_id}:{m}:{s}" or row["preregistration_id"]!=preregistration_id: raise TrialRegistryError(f"trial identity mismatch at line {line_no}")
  try: date.fromisoformat(row["registered_date"])
  except (TypeError,ValueError) as e: raise TrialRegistryError(f"invalid date at line {line_no}") from e
  event=row["event"]
  if event not in EVENTS: raise TrialRegistryError(f"invalid event at line {line_no}")
  if event=="REGISTERED":
   if trial in states: raise TrialRegistryError(f"duplicate REGISTERED event for {trial}")
   states[trial]="REGISTERED";registered.add(trial)
  else:
   if trial not in states: raise TrialRegistryError(f"status event precedes REGISTERED for {trial}")
   if states[trial] in TERMINAL: raise TrialRegistryError(f"terminal trial state cannot be changed for {trial}")
   states[trial]=event
  events+=1
 if registered!=expected: raise TrialRegistryError(f"registry universe mismatch: missing={len(expected-registered)} extra={len(registered-expected)}")
 return {"registered_trial_count":len(registered),"registry_sha256":hashlib.sha256(raw).hexdigest(),"trial_statuses":dict(sorted(states.items())),"trial_ids":sorted(registered),"event_count":events}
def load_trial_registry(path,**kwargs):
 return parse_trial_registry(Path(path).read_bytes(),**kwargs)
