#!/usr/bin/env python3
"""Compare HTTP Range behavior at the LOLA TIFF IFD offset using requests, curl and GDAL VSI."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

def response_record(client, start, end, status, final_url, headers, body, elapsed, redirects=None, extra=None):
    expected=end-start+1
    cr=headers.get("Content-Range","")
    ok=(status==206 and cr.startswith(f"bytes {start}-{end}/") and len(body)==expected
        and "text/html" not in headers.get("Content-Type","").lower())
    result={"client":client,"requested_range":[start,end],"http_status":status,
            "final_url":final_url,"final_host":urlparse(final_url or "").netloc,
            "content_range":cr,"content_length":headers.get("Content-Length"),
            "content_type":headers.get("Content-Type"),
            "received_bytes":len(body),"expected_bytes":expected,"pass":ok,
            "elapsed_seconds":elapsed,"redirect_chain":redirects or []}
    if not ok:
        result["reason"]="expected exact HTTP 206 range response"
        result["error_body"]={"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest(),
                              "preview_utf8":body[:512].decode("utf-8","replace"),
                              "preview_hex":body[:128].hex()}
    if extra: result.update(extra)
    return result

def requests_probe(url,start,end):
    began=time.monotonic()
    try:
        r=requests.get(url,headers={"Range":f"bytes={start}-{end}","Accept-Encoding":"identity",
                         "User-Agent":"LunaSight COG range diagnostic"},timeout=(20,90),allow_redirects=True)
        redirects=[{"status":h.status_code,"url":h.url,"location":h.headers.get("Location")} for h in r.history]
        return response_record("requests",start,end,r.status_code,r.url,dict(r.headers),r.content,
                               time.monotonic()-began,redirects)
    except Exception as exc:
        return {"client":"requests","requested_range":[start,end],"pass":False,
                "status":"ERROR","error":str(exc),"elapsed_seconds":time.monotonic()-began}

def curl_probe(url,start,end):
    began=time.monotonic()
    if not shutil.which("curl"):
        return {"client":"curl","requested_range":[start,end],"pass":False,"status":"UNAVAILABLE"}
    with tempfile.TemporaryDirectory(prefix="lunasight-range-") as tmp:
        hp=str(Path(tmp)/"headers"); bp=str(Path(tmp)/"body")
        cmd=["curl","-sS","-L","--max-time","90","-D",hp,"-o",bp,
             "-H",f"Range: bytes={start}-{end}","-H","Accept-Encoding: identity",
             "-w","%{http_code}\n%{url_effective}",url]
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
            lines=p.stdout.splitlines()
            status=int(lines[0]) if lines and lines[0].isdigit() else None
            final=lines[1] if len(lines)>1 else url
            raw=Path(hp).read_text(encoding="latin1",errors="replace") if Path(hp).exists() else ""
            body=Path(bp).read_bytes() if Path(bp).exists() else b""
            # The final HTTP header block is used; intermediate redirect blocks are retained.
            blocks=[x for x in raw.split("\r\n\r\n") if x.strip()]
            headers={}
            if blocks:
                for line in blocks[-1].splitlines()[1:]:
                    if ":" in line:
                        k,v=line.split(":",1); headers[k.strip()]=v.strip()
            result=response_record("curl",start,end,status,final,headers,body,time.monotonic()-began,
                                   [{"raw_header_block":x[:2000]} for x in blocks[:-1]],
                                   {"curl_exit_code":p.returncode,"curl_stderr":p.stderr[-2000:]})
            return result
        except Exception as exc:
            return {"client":"curl","requested_range":[start,end],"pass":False,
                    "status":"ERROR","error":str(exc),"elapsed_seconds":time.monotonic()-began}

def gdal_probe(url,start,end):
    began=time.monotonic()
    try:
        from osgeo import gdal
        gdal.UseExceptions()
        h=gdal.VSIFOpenL("/vsicurl/"+url,"rb")
        if h is None: raise RuntimeError("GDAL VSIFOpenL returned None")
        try:
            if gdal.VSIFSeekL(h,start,0)!=0: raise RuntimeError("GDAL seek failed")
            body=bytes(gdal.VSIFReadL(1,end-start+1,h) or b"")
        finally: gdal.VSIFCloseL(h)
        ok=len(body)==end-start+1
        return {"client":"gdal-vsi","http_status":"NOT_EXPOSED_BY_GDAL",
                "requested_range":[start,end],"expected_bytes":end-start+1,
                "received_bytes":len(body),"body_sha256":hashlib.sha256(body).hexdigest(),
                "pass":ok,"elapsed_seconds":time.monotonic()-began,
                "reason":None if ok else "GDAL returned a short read"}
    except Exception as exc:
        return {"client":"gdal-vsi","requested_range":[start,end],"pass":False,
                "status":"ERROR","error":str(exc),"elapsed_seconds":time.monotonic()-began}

def atomic_json(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sources",required=True)
    p.add_argument("--product",default="ldem_87s_5mpp")
    p.add_argument("--offset",type=int,default=197624)
    p.add_argument("--output",default="cog_range_client_matrix.json")
    a=p.parse_args()
    sources=json.loads(Path(a.sources).read_text(encoding="utf-8"))
    entry=next((v for k,v in sources.items() if k.casefold()==a.product.casefold()),None)
    if not entry: raise RuntimeError("Product missing from official source manifest")
    url=entry["download_url"]
    sizes=[("same_offset_16B",16),("same_offset_1KiB",1024),
           ("same_offset_4KiB",4096),("same_offset_16KiB",16384)]
    ranges=[{"label":label,"start":a.offset,"end":a.offset+n-1} for label,n in sizes]
    ranges += [{"label":"nearby_before_1KiB","start":max(0,a.offset-1024),"end":a.offset-1},
               {"label":"nearby_after_1KiB","start":a.offset+16384,"end":a.offset+17407},
               {"label":"file_start_control_16B","start":0,"end":15}]
    report={"product":a.product,"source_url":url,"offset":a.offset,
            "scope":"transport diagnostics only; no TIFF interpretation or DEM modification",
            "status":"PARTIAL_FAILURE","results":[],"summary":{}}
    try:
        for item in ranges:
            start,end=item["start"],item["end"]
            record=dict(item)
            # Each client runs regardless of the outcome of the others.
            record["clients"]=[requests_probe(url,start,end),curl_probe(url,start,end),
                               gdal_probe(url,start,end)]
            report["results"].append(record)
            atomic_json(a.output,report)
        report["status"]="COMPLETED"
    except Exception as exc:
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
        raise
    finally:
        flat=[c for r in report["results"] for c in r["clients"]]
        report["summary"]={"range_count":len(report["results"]),"client_result_count":len(flat),
                           "pass_count":sum(bool(x.get("pass")) for x in flat),
                           "fail_count":sum(not bool(x.get("pass")) for x in flat),
                           "note":"GDAL VSI does not expose raw HTTP headers/status; its result records read length and error only."}
        atomic_json(a.output,report)
    print(json.dumps(report["summary"],indent=2))
    return 0 if report["status"]=="COMPLETED" else 2

if __name__=="__main__":
    raise SystemExit(main())
