"""Deployment-readiness checks: serverless (read-only deploy, writable temp), CORS from env, dependency parity."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _run(code: str, env: dict, tmp: Path) -> dict:
    full = {**os.environ, "TEMP": str(tmp), "TMP": str(tmp), "TMPDIR": str(tmp), "PYTHONIOENCODING": "utf-8", **env}
    for k in ("AEGIS_DB", "AEGIS_DATA_DIR", "AEGIS_CORS_ORIGINS", "AEGIS_CORS_ORIGIN_REGEX", "VERCEL"):
        if k not in env:
            full.pop(k, None)
    out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\n%s" % (str(BACKEND), code)],
                         capture_output=True, text=True, cwd=BACKEND, env=full, timeout=240)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _tree(p: Path) -> set:
    return {str(f.relative_to(p)) for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts}


def test_serverless_start_writes_only_to_the_temp_dir(tmp_path):
    """On Vercel (VERCEL=1) the deployment is read-only: DB is built in the temp dir, nothing is written under backend/data."""
    before = _tree(BACKEND / "data")
    res = _run("""
import json
from fastapi.testclient import TestClient
from app import config
from app.main import app
with TestClient(app) as c:                       # runs lifespan: ensure_db() + model load
    ok = [c.get(p).status_code for p in ("/api/health", "/api/companies", "/api/ml/card", "/api/plan?company_id=nike", "/api/data-sources")]
print(json.dumps(dict(db=str(config.DB_PATH), codes=ok)))
""", {"VERCEL": "1"}, tmp_path)
    assert res["codes"] == [200] * 5
    assert Path(res["db"]).parent == tmp_path and Path(res["db"]).exists()
    assert _tree(BACKEND / "data") == before        # no new files in the (read-only on Vercel) data directory


def test_model_artifact_problems_fall_back_to_in_memory_training(tmp_path):
    """A model artifact that cannot be loaded (e.g. other scikit-learn) must not take the API down."""
    data = tmp_path / "data"
    shutil.copytree(BACKEND / "data" / "processed", data / "processed")
    (data / "models").mkdir()
    (data / "models" / "conversion_model.joblib").write_bytes(b"not a pickle")
    (data / "models" / "model_card.json").write_text("{}")
    res = _run("""
import json
from app import ml
card = ml.card()
print(json.dumps(dict(name=card["name"], n=card["n_records"], features=len(card["features"]))))
""", {"AEGIS_DATA_DIR": str(data)}, tmp_path)
    assert res["name"] == "Conversion Propensity Model" and res["n"] > 0 and res["features"] == 4


def test_cors_is_environment_driven_and_never_wildcard(tmp_path):
    res = _run("""
import json
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
def allow(origin):
    r = c.options("/api/whatif", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    return r.headers.get("access-control-allow-origin")
print(json.dumps(dict(good=allow("https://aegis-ui.example.app"), preview=allow("https://aegis-ui-git-x.example.app"),
                      dev=allow("http://localhost:5173"), evil=allow("https://evil.example"))))
""", {"AEGIS_CORS_ORIGINS": "https://aegis-ui.example.app", "AEGIS_CORS_ORIGIN_REGEX": r"https://aegis-ui-.*\.example\.app"}, tmp_path)
    assert res["good"] == "https://aegis-ui.example.app"
    assert res["preview"] == "https://aegis-ui-git-x.example.app"
    assert res["evil"] is None and res["dev"] is None      # an explicit production list replaces the dev default
    default = _run("""
import json
from fastapi.testclient import TestClient
from app.main import app
r = TestClient(app).options("/api/whatif", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
print(json.dumps(dict(dev=r.headers.get("access-control-allow-origin"))))
""", {}, tmp_path)
    assert default["dev"] == "http://localhost:5173"          # local development still works with no configuration


def _names(lines):
    out = {}
    for ln in lines:
        ln = ln.strip().strip(",").strip('"')
        if ln and not ln.startswith(("#", "-r")) and re.match(r"[A-Za-z]", ln):
            out[re.split(r"[=<>\[]", ln)[0].lower()] = ln.replace(" ", "")
    return out


def test_vercel_pyproject_matches_requirements():
    """Vercel installs from pyproject.toml, Docker/dev from requirements.txt: they must not drift."""
    py = (BACKEND / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"dependencies = \[(.*?)\]\n", py, re.S).group(1).splitlines()
    assert _names(deps) == _names((BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines())
    assert 'entrypoint = "app.main:app"' in py
    from app.main import app    # the entrypoint Vercel loads must exist
    assert app.title


def test_no_machine_specific_paths_in_source():
    bad = re.compile(r"[A-Za-z]:[\/]Users[\/]|Downloads[\/]|/home/\w+/")
    for f in list((BACKEND / "app").glob("*.py")) + [BACKEND / "vercel.json", BACKEND / "pyproject.toml"]:
        assert not bad.search(f.read_text(encoding="utf-8")), f.name


def test_concurrent_first_requests_on_a_cold_instance_do_not_race(tmp_path):
    """Regression for the production 'Couldn't reach the API' on first load: the app fires several requests at once,
    and each used to rebuild/delete the not-yet-existing SQLite file while another was writing it (HTTP 500)."""
    res = _run("""
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)                              # no `with`: lifespan (startup DB build) deliberately NOT run
paths = ["/api/companies", "/api/brands", "/api/overview?company_id=nike", "/api/demo", "/api/plan?company_id=lv", "/api/data-sources"]
with ThreadPoolExecutor(8) as ex:
    codes = list(ex.map(lambda p: c.get(p).status_code, paths * 2))
print(json.dumps(dict(codes=codes)))
""", {"AEGIS_DB": str(tmp_path / "cold.db")}, tmp_path)
    assert res["codes"] == [200] * 12
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["cold.db"]     # no leftover temp build files
