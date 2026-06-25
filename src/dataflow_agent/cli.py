from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .constants import find_workbook
from .defaults import default_build_output, default_check_output, default_merge_output, infer_env_version
from .graph_builder import build_graph
from .merge import merge_dcps
from .normalizer import normalize_workbook
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
from .port_index import write_service_port_index
from .schema import load_schema
from .xlsx_reader import read_workbook


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
    drilldown_parser.add_argument("--depth", type=int, default=1, help="Relationship traversal depth; default is 1")
    drilldown_parser.add_argument("--direction", choices=["upstream", "downstream", "both"], default="both", help="Traversal direction; default is both")
    drilldown_parser.add_argument("--theme", choices=["auto", "light", "dark", "security"], default="auto", help="Diagram theme; default is auto")
    drilldown_parser.add_argument("--risk-focus", action="store_true", help="Keep the service context but emphasize non-final or elevated-risk relationships")

    port_parser = subparsers.add_parser("query-port", help="Query ports, dependencies, firewall, and monitoring for one service")
    port_parser.add_argument("--input", required=True, help="DCP directory or workbook path")
    port_parser.add_argument("--service-id", required=True, help="Service_ID to query")
    port_parser.add_argument("--env", help="Environment name; defaults to 00_Metadata.Environment")
    port_parser.add_argument("--version", help="Package version; defaults to 00_Metadata.Version")
    port_parser.add_argument("--output", help="Output JSON file; defaults to <DCP>/dist/service_ports_<Service_ID>.json")

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
        shutil.copy2(merge_result.merged_dcp / "conflict_diff.json", state.paths.reports_dir / "conflict_diff.json")
        shutil.copy2(merge_result.merged_dcp / "conflict_diff.xlsx", state.paths.reports_dir / "conflict_diff.xlsx")
        if merge_result.conflict_count:
            shutil.copy2(merge_result.merged_dcp / "DRAFT_CONFLICTS.md", state.paths.reports_dir / "DRAFT_CONFLICTS.md")
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
        outputs = run_service_drilldown(
            state,
            args.service_id,
            output_root,
            depth=args.depth,
            direction=args.direction,
            theme=args.theme,
            risk_focus=args.risk_focus,
        )
        _print_summary(state)
        print(f"Service drilldown: {args.service_id}")
        for output in outputs:
            print(f"Drilldown artifact: {output}")
        return 0

    if args.command == "query-port":
        input_dir = Path(args.input).resolve()
        output_path = Path(args.output).resolve() if args.output else default_build_output(input_dir) / f"service_ports_{args.service_id}.json"
        schema = load_schema()
        workbook = normalize_workbook(read_workbook(find_workbook(input_dir), schema), schema)
        graph = build_graph(workbook)
        index = write_service_port_index(workbook, args.service_id, output_path, graph)
        print(f"Service port index: {output_path}")
        print(f"Listen ports: {', '.join(index['listen_ports']) if index['listen_ports'] else 'N/A'}")
        print(f"Inbound dependencies: {len(index['inbound_dependencies'])}")
        print(f"Outbound dependencies: {len(index['outbound_dependencies'])}")
        print(f"Firewall rules: {len(index['firewall_rules'])}")
        print(f"Monitoring rows: {len(index['monitoring'])}")
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
