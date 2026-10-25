"""Reproduce the AnyVisLoc benchmark baseline (Ye et al., CVPR Findings 2026) with the
authors' released code (github.com/UAV-AVL/Benchmark) on the released dataset.

The paper's Sections 5.1-5.4 use a 10% subset of the UAV images; the subset itself is not
published, so we take every 10th sample of every scene (sorted by file name; deterministic).
Disk is tight, so each scene is extracted from its zip (reference JSON, aerial map + DSM,
the sampled NPZ files), evaluated, and deleted before the next one.

Usage:
  python anyvisloc_run.py --matcher Roma            # CAMP + RoMa + top-5 re-rank (paper baseline)
  python anyvisloc_run.py --matcher SP_LG           # CAMP + SuperPoint/LightGlue
  python anyvisloc_run.py --summarise
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ZIPS = Path(os.environ.get("AVL_ZIPS", r"D:/proje/uav_vloc_datasets/AnyVisLoc"))
BENCH = Path(os.environ.get("AVL_BENCH", r"D:/proje/repro_ext/anyvisloc_bench"))
WORK = Path(os.environ.get("AVL_WORK", r"D:/proje/repro_ext/avl_data"))
OUT = Path(__file__).resolve().parent / "results" / "anyvisloc"


def extract_scene(scene, every, mode):
    z = zipfile.ZipFile(ZIPS / f"{scene}.zip")
    names = z.namelist()
    npz = sorted(n for n in names if n.endswith(".npz") and Path(n).stem[-4:].isdigit())
    keep = npz[::every]
    maps = [n for n in names if n.endswith("_reference.json") or n.endswith(f"{mode}_map.png")
            or n.endswith(f"{mode}_dsm.npy")]
    for n in maps + keep:
        dest = WORK / n
        if n.endswith("_map.png") and dest.with_suffix(".npy").exists():
            continue
        if not dest.exists():
            z.extract(n, WORK)
        if n.endswith("_map.png"):
            # decode once to a raw .npy that the patched loader memory-maps, then drop the PNG
            import cv2
            import numpy as np
            cv2.setNumThreads(1)
            img = cv2.imread(str(dest), cv2.IMREAD_COLOR)
            np.save(dest.with_suffix(".npy"), img)
            del img
            dest.unlink()
            dest.touch()  # keep the path the reference JSON points to
    return len(npz), len(keep)


def run_scene(scene, a):
    yaml = OUT / f"cfg_{a.matcher}.yaml"
    yaml.write_text(
        "RETRIEVAL_METHODS:\n- CAMP\nMATCHING_METHODS:\n- {}\nPNP_METHODS:\n- P3P\n"
        "RETRIEVAL_COVER: 50\nRETRIEVAL_TOPN: 5\nRETRIEVAL_IMG: /1_Retrieval.jpg\n"
        "RETRIEVAL_IMG_NUM: 5\nRETRIEVAL_FEATURE_NORM: true\nBATCH_SIZE: 32\n".format(a.matcher))
    save = OUT / f"{a.matcher}_{a.mode}" / scene
    cmd = [sys.executable, "run_avl.py", "--dataset_root", str(WORK), "--yaml", str(yaml),
           "--save_dir", str(save), "--reference_mode", a.mode, "--pose_priori", "yp",
           "--strategy", a.strategy, "--PnP_method", "P3P", "--match_keypoints", "3000",
           "--retrieval_k", "5", "--success_thresholds", "1", "3", "5", "7", "10", "15", "20",
           "--scenes", scene, "--device", "cuda", "--no-visualize", "--skip_existing"]
    log = save.parent / f"{scene}.log"
    save.parent.mkdir(parents=True, exist_ok=True)
    # the stock code rotates the whole map per sample (up to ~4 GB); see LazyRotatedMap in
    # avl_utils.py -- identical output up to 1 grey level of interpolation rounding
    # fixed run tag + --skip_existing: a retry resumes the scene instead of starting over
    env = dict(os.environ, AVL_LAZY_ROTATE="1", AVL_RUN_TAG="run")
    with open(log, "a") as fh:
        rc = subprocess.call(cmd, cwd=BENCH, stdout=fh, stderr=subprocess.STDOUT, env=env)
    return rc


def latest_summary(scene, matcher, mode):
    runs = sorted((OUT / f"{matcher}_{mode}" / scene).glob(f"*/{mode}/summary.json"))
    return json.loads(runs[-1].read_text()) if runs else None


# Ye et al., arXiv:2503.10692, aerial reference, CAMP + RoMa + top-N re-ranking
PAPER = {"Table 6, full dataset": {"R@1": 61.6, "A@5m": 74.1, "A@10m": 87.7, "A@20m": 94.2},
         "10% subset (Sec. 5.1-5.4)": {"R@1": None, "A@5m": 74.6, "A@10m": 87.6, "A@20m": 94.2}}


def summarise(a):
    rows, per_scene = [], {}
    for scene in a.scenes:
        runs = sorted((OUT / f"{a.matcher}_{a.mode}" / scene).glob(f"*/{a.mode}"))
        if not runs:
            continue
        # the flushed .json lists (rewritten by each attempt), not the appended .jsonl logs
        ok = json.loads((runs[-1] / "all_results.json").read_text()) if (runs[-1] / "all_results.json").exists() else []
        bad = json.loads((runs[-1] / "failed.json").read_text()) if (runs[-1] / "failed.json").exists() else []
        rs = [{"err": r["pred_error_m"] if r.get("pnp_success") else float("inf"),
               "rank": r.get("retrieval_gt_rank"), "recall_k": r.get("recall_at_k")} for r in ok]
        rs += [{"err": float("inf"), "rank": None, "recall_k": None, "exception": True} for _ in bad]
        per_scene[scene] = metrics(rs)
        rows += rs
    # the paper averages over images; scene-mean is also reported because scene sizes differ 10x
    scene_mean = {k: round(sum(v[k] for v in per_scene.values()) / len(per_scene), 1)
                  for k in ("A@5m", "A@10m", "A@20m", "R@1")} if per_scene else {}
    res = {"matcher": a.matcher, "mode": a.mode, "scenes": len(per_scene),
           "overall_image_weighted": metrics(rows), "scene_mean": scene_mean,
           "paper": PAPER, "per_scene": per_scene}
    (OUT / f"summary_{a.matcher}_{a.mode}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "per_scene"}, indent=1))


def metrics(rs):
    n = len(rs)
    if n == 0:
        return {}
    acc = {f"A@{t}m": round(100 * sum(r["err"] <= t for r in rs) / n, 1) for t in (1, 3, 5, 10, 20)}
    return {"n": n, **acc,
            "R@1": round(100 * sum(r["rank"] == 1 for r in rs) / n, 1),
            "R@5": round(100 * sum(r["rank"] is not None and r["rank"] <= 5 for r in rs) / n, 1),
            "exceptions": sum(1 for r in rs if r.get("exception"))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matcher", default="Roma")
    p.add_argument("--mode", default="aerial")
    p.add_argument("--strategy", default="Topn_opt")
    p.add_argument("--every", type=int, default=10)
    p.add_argument("--scenes", nargs="*", default=[f"Scene_{i:02d}" for i in range(1, 25)])
    p.add_argument("--keep", action="store_true", help="do not delete extracted scene data")
    p.add_argument("--summarise", action="store_true")
    p.add_argument("--attempts", type=int, default=5)
    a = p.parse_args()
    if a.summarise:
        return summarise(a)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "subset_manifest.json"
    man = json.loads(manifest.read_text()) if manifest.exists() else {}
    for scene in a.scenes:
        done = OUT / f"{a.matcher}_{a.mode}" / f"{scene}.done"
        if done.exists():
            continue
        n_all, n_keep = extract_scene(scene, a.every, a.mode)
        man[scene] = {"n_images": n_all, "n_sampled": n_keep, "every": a.every}
        manifest.write_text(json.dumps(man, indent=1))
        # the host runs close to its memory commit limit; an allocation failure either kills the
        # process or fails single samples, so the scene is resumed until it completes cleanly
        for attempt in range(1, a.attempts + 1):
            rc = run_scene(scene, a)
            sm = latest_summary(scene, a.matcher, a.mode) or {}
            n_exc = sm.get("num_exception_failed_rows")
            print(scene, n_all, n_keep, "attempt", attempt, "rc", rc, "exceptions", n_exc,
                  "A@5", sm.get("success_rate_5m"), flush=True)
            if rc == 0 and n_exc == 0:
                break
        if rc == 0 and n_exc == 0:
            done.write_text("ok")
        if not a.keep:
            shutil.rmtree(WORK / scene, ignore_errors=True)


if __name__ == "__main__":
    main()
