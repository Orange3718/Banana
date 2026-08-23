#!/usr/bin/env python3
"""Download the Apple-Silicon thumbnail model with resumable retries."""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT=Path('/Users/orange/AtemoyaModels')
TARGET=ROOT/'coreml-stable-diffusion-v1-5'
STATUS=ROOT/'media-model-status.json'
MODEL='apple/coreml-stable-diffusion-v1-5'
ROOT.mkdir(parents=True,exist_ok=True)
def write(status,detail=''):
    STATUS.write_text(json.dumps({'model':MODEL,'status':status,'detail':detail,'updated_at':datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2))
try:
    if (TARGET/'model_index.json').exists(): write('ready','thumbnail model files present')
    else:
        write('downloading','resumable Hugging Face download')
        snapshot_download(MODEL,local_dir=str(TARGET),ignore_patterns=['*.md','*.txt','*.jpg','*.png'],max_workers=2)
        write('ready','download complete')
except Exception as e:
    write('retrying',str(e)[:500])
    raise
