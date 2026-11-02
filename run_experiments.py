import argparse

from experiments.runner import run_suite

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Run paired IoT mesh routing scenarios")
    parser.add_argument("--trials",type=int,default=5)
    parser.add_argument("--packets",type=int,default=100)
    parser.add_argument("--seed",type=int,default=17)
    parser.add_argument("--nodes",type=int,default=6)
    parser.add_argument("--output",default="results/python")
    args=parser.parse_args()
    raw,agg=run_suite(trials=args.trials,packets=args.packets,seed=args.seed,
                      node_count=args.nodes,output_dir=args.output)
    print(f"Wrote {len(raw)} trial rows to {args.output}/trial_results.csv")
    print(f"Wrote {len(agg)} aggregate rows to {args.output}/aggregate_results.csv")
    print(agg.to_string(index=False))
