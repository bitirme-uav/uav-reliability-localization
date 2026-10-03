"""M10 call-rate sweep / E11 kosu ureteci. Komut listesini yazar; calistirma
`xargs -P` ile paralel yapilir. Her kosu kendi ozet dosyasina yazar."""
import argparse
import itertools

from splits import TEST_SEQUENCES, VAL_SEQUENCES

ap = argparse.ArgumentParser()
ap.add_argument("--split", choices=["val", "test"], required=True)
ap.add_argument("--kind", choices=["nav", "reacq"], required=True)
ap.add_argument("--seeds", default="0")
args = ap.parse_args()
seqs = VAL_SEQUENCES if args.split == "val" else TEST_SEQUENCES
seeds = [int(s) for s in args.seeds.split(",")]
extra = " --allow-test" if args.split == "test" else ""
py = "../venv/bin/python"
outdir = f"../outputs/sweep_{args.split}"

if args.kind == "nav":
    for seq, ci, drift, filt, seed in itertools.product(seqs, (5, 10, 20, 40), ("moderate", "severe"),
                                                        ("matched", "misspecified"), seeds):
        tag = f"{seq}_{drift}_{filt}_ci{ci}_s{seed}"
        print(f"{py} run_nav_sim.py --sequence {seq} --drift {drift} --filter {filt} --call-interval {ci} "
              f"--seed {seed} --max-frames 1200 --out {outdir}/fix/{tag}.jsonl --summary-out {outdir}/sum/{tag}.jsonl{extra} "
              f"> {outdir}/log/{tag}.log 2>&1")
else:
    for seq, sc, seed in itertools.product(seqs, ("A", "B"), seeds):
        tag = f"{seq}_{sc}_s{seed}"
        print(f"{py} run_reacquire.py --sequence {seq} --scenario {sc} --seed {seed} --max-frames 1200 "
              f"--summary-out {outdir}/reacq/{tag}.jsonl{extra} > {outdir}/log/reacq_{tag}.log 2>&1")
