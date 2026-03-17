from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "read_feishu_wiki.py"
MODULE_SPEC = importlib.util.spec_from_file_location("read_feishu_wiki", SCRIPT_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
spec = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(spec)


def test_extract_wiki_token_from_url() -> None:
    url = "https://h52xu4gwob.feishu.cn/wiki/FwG2wbljSiQrtPkTt8RcLAbxnvd?from=from_copylink"
    assert spec.extract_wiki_token(url) == "FwG2wbljSiQrtPkTt8RcLAbxnvd"


def test_extract_wiki_token_from_token() -> None:
    assert spec.extract_wiki_token("FwG2wbljSiQrtPkTt8RcLAbxnvd") == "FwG2wbljSiQrtPkTt8RcLAbxnvd"
