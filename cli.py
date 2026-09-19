"""Command-line interface. Run from the project root: python cli.py <command> ..."""
import argparse
import json
from datetime import datetime

from config import IST
from core import risk, traceability as tr
from db import schema, seed


def main():
    p = argparse.ArgumentParser(description="Food Traceability Graph CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-schema")
    sp = sub.add_parser("seed")
    sp.add_argument("--keep", action="store_true", help="do not clear existing data")
    rst = sub.add_parser("reset")
    rst.add_argument("--migrate", action="store_true", default=False, help="also run ps_migrate after seeding")
    sub.add_parser("migrate")
    imp = sub.add_parser("impact"); imp.add_argument("batch_id"); imp.add_argument("--window", action="store_true")
    fl = sub.add_parser("flag"); fl.add_argument("batch_id")
    fl.add_argument("status", choices=["YELLOW", "RED", "GREEN"])
    fl.add_argument("--reason", required=True)
    fl.add_argument("--at", help="contamination datetime YYYY-MM-DD HH:MM (IST), required for YELLOW")
    rep = sub.add_parser("report"); rep.add_argument("batch_id"); rep.add_argument("--out")
    rev = sub.add_parser("reverse")
    rev.add_argument("--customer"); rev.add_argument("--order"); rev.add_argument("--dish")
    sup = sub.add_parser("supplier"); sup.add_argument("supplier_id")
    sub.add_parser("export-csv")

    args = p.parse_args()

    if args.cmd == "init-schema":
        schema.init_schema(); print("Schema initialised.")
    elif args.cmd == "seed":
        stats = seed.seed(clear=not args.keep)
        print(json.dumps(stats, indent=2))
    elif args.cmd == "migrate":
        import ps_migrate
        ps_migrate.run_migration()
        print("Migration complete.")
    elif args.cmd == "reset":
        schema.init_schema()
        stats = seed.seed(clear=True)
        print(json.dumps(stats, indent=2))
        print("Graph reset and demo data seeded.")
        if args.migrate:
            import ps_migrate
            ps_migrate.run_migration()
            print("Migration applied.")
    elif args.cmd == "impact":
        report = tr.impact_report(args.batch_id, apply_window=True if args.window else None)
        print(json.dumps(report, indent=2, default=str))
    elif args.cmd == "flag":
        cd = datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=IST) if args.at else None
        b = risk.flag_batch(args.batch_id, args.status, args.reason, actor="cli", contamination_date=cd)
        print(f"{args.batch_id} -> {b['status']}")
    elif args.cmd == "report":
        report = tr.recall_report(args.batch_id)
        out = json.dumps(report, indent=2)
        if args.out:
            with open(args.out, "w") as f:
                f.write(out)
            print(f"Report written to {args.out}")
        else:
            print(out)
    elif args.cmd == "reverse":
        print(json.dumps(tr.reverse_trace(customer_id=args.customer, order_id=args.order,
                                          dish_id=args.dish), indent=2, default=str))
    elif args.cmd == "supplier":
        print(json.dumps(tr.supplier_intelligence(args.supplier_id), indent=2, default=str))
    elif args.cmd == "export-csv":
        from scripts.export_dataset_csv import main as run_export
        run_export()


if __name__ == "__main__":
    main()
