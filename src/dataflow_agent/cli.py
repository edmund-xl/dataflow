from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .defaults import default_build_output, default_check_output, default_merge_output, infer_env_version
from .merge import merge_dcps
from .pipeline import (
    load_state,
    run_all,
    run_build,
    run_check,
    run_normalize,
    run_package,
    run_render,
    run_report,
    run_risk,
    run_service_drilldown,
    run_validate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dataflow-agent", description="Dataflow Project Dataflow Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Self-check for one DCP")
    check_parser.add_argument("input", help="DCP directory or workbook path")
    check_parser.add_argument("--env", help="Environment name; defaults to 00_Metadata.Environment")
    check_parser.add_argument("--version", help="Package version; defaults to 00_Metadata.Version")
    check_parser.add_argument("--output", help="Output directory; defaults to <DCP>/agent_check")

    merge_parser = subparsers.add_parser("merge", help="Merge multiple DCPs and build a final package")
    merge_parser.add_argument("inputs", nargs="+", help="DCP directories or workbook paths")
    merge_parser.add_argument("--env", help="Environment name; defaults to first DCP metadata")
    merge_parser.add_argument("--version", help="Package version; defaults to first DCP metadata")
    merge_parser.add_argument("--output", help="Output directory; defaults to ./dist")
    merge_parser.add_argument("--allow-conflicts", action="store_true", help="Build a draft package even when merge conflicts exist")

    build_quick_parser = subparsers.add_parser("quick-build", help="Script-friendly full package build")
    build_quick_parser.add_argument("input", help="DCP directory or workbook path")
    build_quick_parser.add_argument("--env", help="Environment name; defaults to 00_Metadata.Environment")
    build_quick_parser.add_argument("--version", help="Package version; defaults to 00_Metadata.Version")
    build_quick_parser.add_argument("--output", help="Output directory; defaults to <DCP>/dist")

    drilldown_parser = subparsers.add_parser("drilldown", help="Render a single-service drilldown diagram")
    drilldown_parser.add_argument("--input", required=True, help="DCP directory or workbook path")
    drilldown_parser.add_argument("--service-id", required=True, help="Service_ID to render")
    drilldown_parser.add_argument("--env", help="Environment name; defaults to 00_Metadata.Environment")
    drilldown_parser.add_argument("--version", help="Package version; defaults to 00_Metadata.Version")
    drilldown_parser.add_argument("--output", help="Output directory; defaults to <DCP>/dist/service_drilldown_<Service_ID>")

    for command in ["validate", "normalize", "build", "risk", "render", "report", "package", "run"]:
        _add_common(subparsers.add_parser(command))
    args = parser.parse_args(argv)

    if args.command == "check":
        input_dir = Path(args.input).resolve()
        inferred_env, inferred_version = infer_env_version(input_dir)
        env = args.env or inferred_env
        version = args.version or inferred_version
        output_root = Path(args.output).resolve() if args.output else default_check_output(input_dir)
        state = run_check(input_dir, output_root, env, version, clean_output=True)
        _print_summary(state)
        print(f"Check summary: {output_root / 'check_summary.md'}")
        print(f"Fix list: {output_root / 'fix_list.md'}")
        return 0

    if args.command == "quick-build":
        input_dir = Path(args.input).resolve()
        inferred_env, inferred_version = infer_env_version(input_dir)
        env = args.env or inferred_env
        version = args.version or inferred_version
        output_root = Path(args.output).resolve() if args.output else default_build_output(input_dir)
        state = run_all(input_dir, output_root, env, version, clean_output=True)
        _print_summary(state)
        return 0

    if args.command == "merge":
        inputs = [Path(item).resolve() for item in args.inputs]
        inferred_env, inferred_version = infer_env_version(inputs[0])
        env = args.env or inferred_env
        version = args.version or inferred_version
        output_root = Path(args.output).resolve() if args.output else default_merge_output()
        merge_result = merge_dcps(inputs, output_root, version)
        if merge_result.conflict_count and not args.allow_conflicts:
            print(f"Merge conflicts: {merge_result.conflict_count}", file=sys.stderr)
            print(f"Merge report: {merge_result.merged_dcp / 'merge_report.xlsx'}", file=sys.stderr)
            print("Resolve conflicts or rerun with --allow-conflicts to build a draft package.", file=sys.stderr)
            return 1
        state = run_all(merge_result.merged_dcp, output_root, env, version, clean_output=True)
        shutil.copy2(merge_result.merged_dcp / "merge_report.json", state.paths.reports_dir / "merge_report.json")
        shutil.copy2(merge_result.merged_dcp / "merge_report.xlsx", state.paths.reports_dir / "merge_report.xlsx")
        shutil.copy2(merge_result.merged_dcp / "merge_lineage.json", state.paths.reports_dir / "merge_lineage.json")
        if merge_result.conflict_count:
            (state.paths.reports_dir / "DRAFT_CONFLICTS.md").write_text(
                "# Draft Package\n\nThis package was generated with unresolved merge conflicts and must not be used for final acceptance.\n",
                encoding="utf-8",
            )
        run_package(state, env, version)
        _print_summary(state)
        print(f"Merged DCP: {merge_result.merged_dcp}")
        print(f"Merge report: {merge_result.merged_dcp / 'merge_report.xlsx'}")
        print(f"Merge duplicates: {merge_result.duplicate_count}")
        print(f"Merge conflicts: {merge_result.conflict_count}")
        return 0

    if args.command == "drilldown":
        input_dir = Path(args.input).resolve()
        inferred_env, inferred_version = infer_env_version(input_dir)
        env = args.env or inferred_env
        version = args.version or inferred_version
        output_root = Path(args.output).resolve() if args.output else default_build_output(input_dir) / f"service_drilldown_{args.service_id}"
        state = load_state(input_dir, output_root, env, version, clean_output=False)
        outputs = run_service_drilldown(state, args.service_id, output_root)
        _print_summary(state)
        print(f"Service drilldown: {args.service_id}")
        for output in outputs:
            print(f"Drilldown artifact: {output}")
        return 0

    input_dir = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    if args.command == "run":
        state = run_all(input_dir, output_root, args.env, args.version, clean_output=True)
        _print_summary(state)
        return 0

    state = load_state(input_dir, output_root, args.env, args.version, clean_output=False)
    if args.command == "validate":
        run_validate(state)
    elif args.command == "normalize":
        run_normalize(state)
    elif args.command == "build":
        run_normalize(state)
        run_build(state)
    elif args.command == "risk":
        run_normalize(state)
        run_build(state)
        run_risk(state)
    elif args.command == "render":
        run_normalize(state)
        run_build(state)
        run_render(state)
    elif args.command == "report":
        run_normalize(state)
        run_build(state)
        run_risk(state)
        run_report(state, args.env, args.version)
    elif args.command == "package":
        run_normalize(state)
        run_build(state)
        run_risk(state)
        run_render(state)
        run_report(state, args.env, args.version)
        run_package(state, args.env, args.version)
    _print_summary(state)
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="DCP directory or workbook path")
    parser.add_argument("--env", required=True, help="Environment name")
    parser.add_argument("--version", required=True, help="Package version")
    parser.add_argument("--output", required=True, help="Output directory")


def _print_summary(state) -> None:
    print(f"Workbook: {state.paths.workbook_path}")
    print(f"Package directory: {state.paths.package_dir}")
    print(f"Nodes: {len(state.graph.nodes)}")
    print(f"Edges: {len(state.graph.edges)}")
    print(f"Validation findings: {len(state.validation.findings)}")
    print(f"Risk findings: {len(state.risks)}")
    if state.zip_path:
        print(f"Zip: {state.zip_path}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
