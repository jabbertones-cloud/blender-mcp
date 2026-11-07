"""Compare frozen M2 crash fault observations; real fault replays are separate opt-in tests."""
import json
from pathlib import Path

record=json.loads((Path(__file__).parent/'fixtures/blender_render_recovery_observed.json').read_text())
negative=record['negative_control'];candidate=record['candidate'];native=record['native_blender']
assert negative['configured_retries']==candidate['configured_retries']==1
assert negative['consumer_exit_code']==candidate['workhorse_exit_code']==17
assert negative['pending_after_crash']==0 and negative['result_after_crash'] is None
assert 'Work-horse terminated unexpectedly' in str(candidate['log_snippet'])
assert candidate['retries_left']==0 and candidate['status_after_worker_restart']=='finished'
assert native['queued_before_aof_restart'] and native['persisted_after_aof_restart'] and native['completed_after_reboot']
print(json.dumps({'metric':'completed_job_after_abrupt_worker_exit_in_isolated_M2_trial',
                  'baseline':int(negative['recovered']),'candidate':int(candidate['recovered']),
                  'direction':'higher','experiment_count_per_donor':1,
                  'proof':'frozen instrumented donor trials and separate opt-in RQ crash/Blender render test; not a general measured reliability rate'}))
