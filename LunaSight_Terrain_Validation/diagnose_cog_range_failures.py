#!/usr/bin/env python3
"""Diagnose selected COG byte ranges using TIFF tile metadata, requests, curl and GDAL.

This is transport/format diagnostics only. It does not download complete DEMs,
change rasters, validate lunar frames/datums, or authorize terrain-horizon work.
"""
from __future__ import annotations
import argparse
import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TRANSIENT = (429, 500, 502, 503, 504)
TIFF_READ_CHUNK_SIZE = 16 * 1024


class RangeReader:
    def __init__(self, url: str, timeout=(20, 90)):
        self.url = url
        self.timeout = timeout
        retry = Retry(total=3, connect=3, read=3, status=3, backoff_factor=1,
                      status_forcelist=TRANSIENT,
                      allowed_methods=frozenset({"GET", "HEAD"}))
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.history = []

    def get(self, start: int, end: int, client="requests", include_body=False) -> dict:
        if start < 0 or end < start:
            raise ValueError("Invalid byte range")
        headers = {"Range": f"bytes={start}-{end}",
                   "Accept-Encoding": "identity",
                   "User-Agent": "LunaSight COG range diagnostic"}
        if client == "curl":
            exe = shutil.which("curl")
            if not exe:
                return {"client": "curl", "status": "UNAVAILABLE", "error": "curl not installed"}
            cmd = [exe, "-sS", -L, -D, "-", "-o", "/dev/stdout",
                   "--max-time", str(self.timeout[1]), "-H",
                   f"Range: bytes={start}-{end}", "-H", "Accept-Encoding: identity",
                   "-w", "\\nLUNASIGHT_CURL_META:%{http_code}:%{url_effective}:%{size_download}",
                   self.url]
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=self.timeout[1]+10)
                raw = p.stdout
                marker = b"\nLUNASIGHT_CURL_META:"
                pos = raw.rfind(marker)
                meta = raw[pos+len(marker):].decode("utf-8", "replace").strip() if pos >= 0 else ""
                body = raw[:pos] if pos >= 0 else b""
                parts = meta.split(":", 2)
                status = int(parts[0]) if parts and parts[0].isdigit() else None
                effective = parts[1] if len(parts)>1 else None
                size = int(parts[2]) if len(parts)>2 and parts[2].isdigit() else len(body)
                header_blob = body
                # -D - writes headers before body; locate last header terminator.
                split = header_blob.rfind(b"\r\n\r\n")
                headers_text = header_blob[:split].decode("latin1", "replace") if split >= 0 else ""
                payload = header_blob[split+4:] if split >= 0 else header_blob
                result = self._validate(client, start, end, status, effective, headers_text, payload)
                result["curl_exit_code"] = p.returncode
                result["curl_reported_download_bytes"] = size
                if p.returncode:
                    result["curl_stderr"] = p.stderr.decode("utf-8", "replace")[-2000:]
                return result
            except Exception as exc:
                return {"client": "curl", "status": "ERROR", "error": str(exc)}
        try:
            response = self.session.get(self.url, headers=headers, stream=False,
                                        allow_redirects=True, timeout=self.timeout)
            header_lines = "\n".join(f"{k}: {v}" for k,v in response.headers.items())
            result = self._validate(client, start, end, response.status_code, response.url,
                                    header_lines, response.content)
            if include_body and result.get("pass"):
                result["_body"] = response.content
            history_entry = {k: v for k, v in result.items() if k != "_body"}
            history_entry.update({"requested_start": start, "requested_end": end})
            self.history.append(history_entry)
            return result
        except requests.RequestException as exc:
            failure = {"client": client, "status": "REQUEST_ERROR", "error": str(exc),
                       "requested_start": start, "requested_end": end}
            self.history.append(failure)
            return failure

    def _validate(self, client, start, end, status, final_url, header_text, body):
        hdr = {}
        for line in header_text.splitlines():
            if ":" in line:
                k,v=line.split(":",1); hdr[k.strip().casefold()]=v.strip()
        cr=hdr.get("content-range","")
        expected=end-start+1
        result={"client":client,"http_status":status,"final_url":final_url,
                "final_host":urlparse(final_url or "").netloc,
                "content_range":cr,"content_length":hdr.get("content-length"),
                "content_type":hdr.get("content-type"),
                "content_encoding":hdr.get("content-encoding"),
                "received_bytes":len(body),"expected_bytes":expected}
        result["pass"] = (status==206 and cr.startswith(f"bytes {start}-{end}/")
                          and len(body)==expected
                          and "text/html" not in (hdr.get("content-type") or "").casefold()
                          and not body.lstrip().lower().startswith((b"<html",b"<!doctype html")))
        if status != 206: result["reason"]="expected HTTP 206"
        elif not cr.startswith(f"bytes {start}-{end}/"): result["reason"]="Content-Range mismatch"
        elif len(body)!=expected: result["reason"]="body length mismatch"
        elif not result["pass"]: result["reason"]="HTML/error payload"
        return result


def read_exact(reader: RangeReader, offset: int, size: int,
               chunk_size: int = TIFF_READ_CHUNK_SIZE) -> bytes:
    if size <= 0:
        raise ValueError("TIFF structure read size must be positive")
    if chunk_size <= 0:
        raise ValueError("TIFF structure chunk size must be positive")
    chunks = []
    consumed = 0
    while consumed < size:
        current_size = min(chunk_size, size - consumed)
        start = offset + consumed
        end = start + current_size - 1
        result = reader.get(start, end, include_body=True)
        if not result.get("pass"):
            raise RuntimeError(
                f"Cannot read TIFF structure chunk at {start}+{current_size}: {result}"
            )
        body = result.pop("_body", None)
        if not isinstance(body, bytes) or len(body) != current_size:
            raise RuntimeError(
                f"Validated TIFF response did not retain {current_size} bytes at {start}"
            )
        chunks.append(body)
        consumed += current_size
    return b"".join(chunks)


def parse_tiff_tile_tables(reader: RangeReader, chunk_size: int = TIFF_READ_CHUNK_SIZE) -> dict:
    header=read_exact(reader,0,16,chunk_size)
    endian_mark=header[:2]
    if endian_mark==b"II": endian="<"
    elif endian_mark==b"MM": endian=">"
    else: raise RuntimeError("Invalid TIFF byte-order marker")
    magic=struct.unpack(endian+"H",header[2:4])[0]
    if magic==42:
        big=False; first=struct.unpack(endian+"I",header[4:8])[0]
        count_fmt="H"; entry_size=12; next_size=4; inline_size=4; offset_fmt="I"
    elif magic==43:
        big=True
        offsize,reserved=struct.unpack(endian+"HH",header[4:8])
        if offsize!=8 or reserved!=0: raise RuntimeError("Unsupported BigTIFF header")
        first=struct.unpack(endian+"Q",header[8:16])[0]
        count_fmt="Q"; entry_size=20; next_size=8; inline_size=8; offset_fmt="Q"
    else: raise RuntimeError(f"Unsupported TIFF magic {magic}")
    directories=[]; ifd=first; visited=set()
    type_sizes={1:1,2:1,3:2,4:4,5:8,6:1,7:1,8:2,9:4,10:8,11:4,12:8,16:8,17:8,18:8}
    for page in range(64):
        if not ifd or ifd in visited: break
        visited.add(ifd)
        count_size=struct.calcsize(count_fmt)
        count=struct.unpack(endian+count_fmt,read_exact(reader,ifd,count_size,chunk_size))[0]
        if count>100000: raise RuntimeError(f"Unreasonable TIFF IFD entry count: {count}")
        raw=read_exact(reader,ifd+count_size,count*entry_size+next_size,chunk_size)
        tags={}
        for i in range(count):
            e=raw[i*entry_size:(i+1)*entry_size]
            if big:
                tag,typ,n=struct.unpack(endian+"HHQ",e[:12]); value_field=e[12:20]
            else:
                tag,typ,n=struct.unpack(endian+"HHI",e[:8]); value_field=e[8:12]
            if tag not in (256,257,322,323,324,325) or typ not in type_sizes: continue
            total=n*type_sizes[typ]
            if total<=inline_size: payload=value_field[:total]
            else:
                pos=struct.unpack(endian+offset_fmt,value_field)[0]
                payload=read_exact(reader,pos,total,chunk_size)
            if typ in (3,8): fmt="H" if typ==3 else "h"
            elif typ in (4,9): fmt="I" if typ==4 else "i"
            elif typ in (16,17,18): fmt="Q" if typ in (16,18) else "q"
            elif typ in (1,6,7): fmt="B" if typ!=6 else "b"
            else: continue
            values=list(struct.unpack(endian+fmt*n,payload)) if n else []
            tags[tag]=values[0] if len(values)==1 else values
        def arr(tag):
            v=tags.get(tag,[])
            return v if isinstance(v,list) else ([v] if v!=[] else [])
        offsets,counts=arr(324),arr(325)
        if offsets or counts:
            if len(offsets)!=len(counts): raise RuntimeError("TileOffsets/TileByteCounts length mismatch")
            directories.append({"ifd_offset":ifd,"width":tags.get(256),"height":tags.get(257),
                "tile_width":tags.get(322),"tile_height":tags.get(323),
                "tile_count":len(offsets),"tile_offsets":offsets,"tile_byte_counts":counts})
        next_pos=ifd+count_size+count*entry_size
        ifd=struct.unpack(endian+("Q" if big else "I"),
                          read_exact(reader,next_pos,next_size,chunk_size))[0]
    if not directories: raise RuntimeError("No tiled TIFF directories with tags 324/325 were found")
    return {"byte_order":endian_mark.decode(),"bigtiff":big,"directories":directories}


def gdal_probe(url: str, directory: dict, tile_index: int) -> dict:
    try:
        from osgeo import gdal
        gdal.UseExceptions()
        ds=gdal.Open("/vsicurl/"+url,gdal.GA_ReadOnly)
        if ds is None: raise RuntimeError("GDAL Open returned None")
        band=ds.GetRasterBand(1)
        bx,by=band.GetBlockSize()
        cols=math.ceil(ds.RasterXSize/bx)
        row,col=divmod(tile_index,cols)
        if row*by>=ds.RasterYSize: raise RuntimeError("Tile index outside GDAL raster block grid")
        arr=band.ReadAsArray(col*bx,row*by,1,1)
        return {"status":"PASS","raster_size":[ds.RasterXSize,ds.RasterYSize],
                "block_size":[bx,by],"tile_row":row,"tile_col":col,
                "sample_value":float(arr[0,0])}
    except Exception as exc:
        return {"status":"FAIL","error":str(exc)}


def parse_range(value: str) -> tuple[int,int]:
    a,b=value.split("-",1); start,end=int(a),int(b)
    if start<0 or end<start: raise argparse.ArgumentTypeError("range must be START-END")
    return start,end


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources",default="official_sources.json")
    p.add_argument("--product",default="ldem_87s_5mpp.tif")
    p.add_argument("--range",action="append",type=parse_range,default=[],
                   help="Observed failing inclusive byte range START-END; repeatable")
    p.add_argument("--output",default="cog_range_failure_diagnostics.json")
    p.add_argument("--max-tiles",type=int,default=8,
                   help="Maximum TIFF tiles sampled per IFD (0 disables tile probes)")
    p.add_argument("--chunk-size",type=int,default=TIFF_READ_CHUNK_SIZE,
                   help="Maximum bytes per TIFF metadata Range request")
    a=p.parse_args()
    output=Path(a.output)
    report={
        "product":a.product,
        "scope":"targeted HTTP/TIFF/GDAL diagnostics; no full download",
        "status":"STARTED",
        "last_successful_stage":None,
        "failed_stage":None,
        "error":None,
        "failed_request":None,
        "request_history":[],
        "tiff_structure":None,
        "observed_ranges":[],
        "tile_probes":[],
        "summary":None
    }
    reader=None
    exit_code=0
    try:
        sources=json.loads(Path(a.sources).read_text(encoding="utf-8"))
        entry=next((v for k,v in sources.items() if k.casefold()==a.product.casefold()),None)
        if not entry:
            raise RuntimeError(f"Product not found in source manifest: {a.product}")
        url=entry["download_url"]
        report["source_url"]=url
        reader=RangeReader(url)
        report["failed_stage"]="tiff_structure"
        report["tiff_structure"]=parse_tiff_tile_tables(reader, chunk_size=a.chunk_size)
        report["last_successful_stage"]="tiff_structure"
        report["failed_stage"]="observed_ranges"
        for start,end in a.range:
            report["observed_ranges"].append({"range":[start,end],
              "clients":[reader.get(start,end,"requests"),reader.get(start,end,"curl")]})
        report["last_successful_stage"]="observed_ranges"
        report["failed_stage"]="tile_probes"
        if a.max_tiles:
            for di,d in enumerate(report["tiff_structure"]["directories"]):
                n=min(a.max_tiles,d["tile_count"])
                for ti in range(n):
                    start=d["tile_offsets"][ti]; end=start+d["tile_byte_counts"][ti]-1
                    report["tile_probes"].append({"ifd_index":di,"tile_index":ti,"range":[start,end],
                      "requests":reader.get(start,end,"requests"),
                      "curl":reader.get(start,end,"curl"),
                      "gdal":gdal_probe(url,d,ti)})
        report["last_successful_stage"]="tile_probes"
        report["failed_stage"]=None
        report["status"]="COMPLETED"
    except Exception as exc:
        report["status"]="PARTIAL_FAILURE"
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
        if reader is not None:
            report["failed_request"] = next(
                (item for item in reversed(reader.history)
                 if item.get("pass") is False or item.get("status") == "REQUEST_ERROR"),
                None
            )
        exit_code=2
    finally:
        if reader is not None:
            report["request_history"]=reader.history
        report["summary"]={
          "status":report["status"],
          "last_successful_stage":report["last_successful_stage"],
          "failed_stage":report["failed_stage"],
          "failed_request":report["failed_request"],
          "request_count":len(report["request_history"]),
          "observed_range_count":len(report["observed_ranges"]),
          "tile_probe_count":len(report["tile_probes"]),
          "requests_pass":sum(x.get("pass",False) for group in report["observed_ranges"] for x in group["clients"])+sum(x[k].get("pass",False) for x in report["tile_probes"] for k in ("requests","curl")),
          "gdal_tile_pass":sum(x["gdal"].get("status")=="PASS" for x in report["tile_probes"]),
          "note":"Transport evidence only; not TIFF integrity or scientific acceptance."
        }
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))
    print(f"Report: {output}")
    return exit_code

if __name__=="__main__":
    try: sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}",file=sys.stderr); sys.exit(2)
