import json, urllib.request, concurrent.futures as cf, time
D='/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/diversity2/'
S=json.load(open(D+'stories.json'))
def go(s):
    req=urllib.request.Request('http://127.0.0.1:8141/request',data=json.dumps({"text":s['text'],"mode":"event"}).encode(),headers={'Content-Type':'application/json'})
    t=time.time()
    try:
        r=json.load(urllib.request.urlopen(req,timeout=300)); json.dump(r,open(D+s['id']+'.resp.json','w')); return s['id'],'ok',round(time.time()-t,1)
    except Exception as e: return s['id'],'FAIL '+repr(e)[:200],round(time.time()-t,1)
res=[]
with cf.ThreadPoolExecutor(3) as ex:
    for x in ex.map(go,S): res.append(x); print(x,flush=True)
json.dump(res,open(D+'request_log.json','w'))
urllib.request.urlretrieve('http://127.0.0.1:8141/sowhat',D+'sowhat_tables_live.json')
