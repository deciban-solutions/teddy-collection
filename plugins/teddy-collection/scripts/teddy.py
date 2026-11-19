#!/usr/bin/env python3
"""teddy.py: subcommand dispatcher for the teddy-collection plug-in.

Run as `python3 -I scripts/teddy.py <subcommand>`. To add a subcommand, write a
`register_<name>(sub)` function and append it to REGISTRARS; nothing else changes.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from teddycoll import (coding, dataset, frames, freeze, importer, infer, ingest, links, pages,  # noqa: E402
                       paths, publish, setupcheck, specs, taxonomy)


def _cmd_paths(args):
    print(json.dumps({"data_home": str(paths.data_home()),
                      "runs": str(paths.data_home() / "runs")}))
    return 0


def register_paths(sub):
    p = sub.add_parser("paths", help="print the data home and runs folder as JSON")
    p.set_defaults(func=_cmd_paths)


def _cmd_dataset_add(args):
    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    ds = dataset.load()
    prior = specs.prior_values(exclude_run=Path(args.records).resolve().parent, ds=ds)
    spec_errors = specs.unknown_errors(records.get("watches"), prior, "records.json")
    for v in records.get("videos", []):
        dataset.add_video(ds, v)
    for a in records.get("appearances", []):
        dataset.add_appearance(ds, a)
    for w in records.get("watches", []):
        dataset.upsert_watch(ds, w)
    errors = spec_errors + dataset.validate(ds)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        print("dataset-add refused; nothing written", file=sys.stderr)
        return 1
    dataset.save(ds)
    print(json.dumps({"videos": len(ds["videos"]), "appearances": len(ds["appearances"]),
                      "watches": len(ds["watches"])}))
    return 0


def register_dataset_add(sub):
    p = sub.add_parser("dataset-add", help="validate and merge a run's records.json into the dataset")
    p.add_argument("records", help="path to <run>/records.json")
    p.set_defaults(func=_cmd_dataset_add)


def _cmd_ingest(args):
    try:
        ids = [ingest.video_id(u) for u in args.urls]  # validate everything before touching disk
        parts = tuple(p.strip() for p in args.parts.split(",") if p.strip())
        unknown = set(parts) - set(ingest.PARTS)
        if unknown or not parts:
            raise ValueError(f"--parts takes a comma list of {list(ingest.PARTS)}; got {args.parts!r}")
        run = Path(args.run) if args.run else paths.new_run(ids)
        result = {}
        for u, vid in zip(args.urls, ids):
            result[vid] = ingest.run_ingest(u, run, any_channel=args.any_channel, parts=parts)
    except (ValueError, ingest.MetadataUnavailable) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"run": str(run), "videos": result}, indent=2))
    return 0


def register_ingest(sub):
    p = sub.add_parser("ingest", help="fetch transcript, metadata, comments and video for URLs")
    p.add_argument("urls", nargs="+")
    p.add_argument("--run", help="run directory (default: a new one under runs/)")
    p.add_argument("--any-channel", action="store_true", help="allow channels other than Teddy Baldassarre")
    p.add_argument("--parts", default=",".join(ingest.PARTS),
                   help="comma list of parts to fetch besides metadata (default: all): "
                        "'transcript' first to classify cheaply, then 'comments,video' with --run")
    p.set_defaults(func=_cmd_ingest)


def _cmd_discard_run(args):
    runs = (paths.data_home() / "runs").resolve()
    target = Path(args.run).expanduser()
    real = target.resolve()
    if target.is_symlink() or real.parent != runs or not real.is_dir():
        print(f"error: {args.run} is not a run folder under {runs}; nothing removed", file=sys.stderr)
        return 2
    import shutil
    size = sum(f.stat().st_size for f in real.rglob("*") if f.is_file())
    shutil.rmtree(real)
    print(json.dumps({"removed": str(real), "bytes": size}))
    return 0


def register_discard_run(sub):
    p = sub.add_parser("discard-run", help="delete one run folder under runs/ (a run the user stopped)")
    p.add_argument("run", help="path to <data home>/runs/<run>")
    p.set_defaults(func=_cmd_discard_run)


def _cmd_frames(args):
    try:
        if args.action == "sheet":
            res = [str(p) for p in frames.contact_sheet(
                args.video, args.start, args.end, args.every, args.out)]
        elif args.action == "still":
            res = str(frames.still(args.video, args.at, args.out))
        elif args.action == "crop":
            res = str(frames.crop(args.img, tuple(args.box), args.out))
        else:
            res = str(frames.resize(args.img, args.long_edge, args.quality))
    except (frames.FfmpegError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res))
    return 0


def register_frames(sub):
    p = sub.add_parser("frames", help="contact sheets, stills, crops and resizes (needs ffmpeg)")
    fs = p.add_subparsers(dest="action", required=True)
    s = fs.add_parser("sheet", help="4x3 contact sheets with timestamps")
    s.add_argument("video"); s.add_argument("--start", default="0"); s.add_argument("--end", required=True)
    s.add_argument("--every", type=float, default=1.0, help="seconds between frames")
    s.add_argument("--out", required=True, help="output prefix; writes <out>_01.jpg ...")
    t = fs.add_parser("still", help="one frame as JPEG")
    t.add_argument("video"); t.add_argument("--at", required=True); t.add_argument("--out", required=True)
    c = fs.add_parser("crop", help="crop to X Y W H")
    c.add_argument("img"); c.add_argument("--box", type=int, nargs=4, required=True,
                                          metavar=("X", "Y", "W", "H"))
    c.add_argument("--out", required=True)
    r = fs.add_parser("resize", help="shrink in place to a long edge (never upscales)")
    r.add_argument("img"); r.add_argument("--long-edge", type=int, default=900)
    r.add_argument("--quality", type=int, default=82)
    p.set_defaults(func=_cmd_frames)


def _cmd_verify_links(args):
    f = Path(args.records)
    records = json.loads(f.read_text(encoding="utf-8"))
    only = set(args.only or [])
    unknown = sorted(only - {w.get("id") for w in records.get("watches", [])})
    if unknown:
        print(f"error: --only names watches not in {f}: {', '.join(unknown)}", file=sys.stderr)
        return 2
    failed, blocked, checked, skip_hosts = [], {}, 0, {}
    for i, w in enumerate(records.get("watches", [])):
        if only and w.get("id") not in only:
            continue
        checked += 1
        records["watches"][i] = w = links.verify_watch(w, skip_hosts=skip_hosts)
        if not links.passes(w):
            statuses = links.unread(w)
            if statuses:
                blocked[w.get("id", f"#{i}")] = statuses
            else:
                failed.append(w.get("id", f"#{i}"))
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)
    print(json.dumps({"watches": checked, "no_matching_source": failed,
                      "unreadable": list(blocked), "skipped_hosts": skip_hosts}))
    for host, code in skip_hosts.items():
        print(f"note: {host} answered {code}; its later sources in this run were not fetched "
              "(marked unreadable)", file=sys.stderr)
    for wid in failed:
        print(f"error: {wid}: no source matched", file=sys.stderr)
    by_id = {w.get("id"): w for w in records.get("watches", [])}
    for wid, statuses in blocked.items():
        codes = ", ".join(str(c) for c in statuses)
        if len(statuses) == len(by_id.get(wid, {}).get("sources", [])):
            msg = f"no source could be read ({codes}), unread"
        else:
            msg = f"no source matched, and {len(statuses)} could not be read ({codes}), unread"
        print(f"error: {wid}: {msg}; try the next rung for this watch", file=sys.stderr)
    return 1 if failed or blocked else 0


def register_verify_links(sub):
    p = sub.add_parser("verify-links", help="check each watch's source links; exit 1 if any watch has "
                                            "no match (read and absent) or no readable source")
    p.add_argument("records", help="path to <run>/records.json (updated in place)")
    p.add_argument("--only", nargs="+", metavar="WATCH_ID",
                   help="check only these watches; the others' rows are left as they are")
    p.set_defaults(func=_cmd_verify_links)


def _merge_numbers(run, key, value):
    f = Path(run) / "numbers.json"
    nums = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    nums[key] = value
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _review_verdicts(run, video_ids=None):
    """[{watch, stance, quote}] for the dataset's `reviewed` appearances with a verdict in this
    run's videos (default: the videos in <run>/records.json)."""
    if not video_ids:
        rf = Path(run) / "records.json"
        records = json.loads(rf.read_text(encoding="utf-8")) if rf.is_file() else {}
        video_ids = [v.get("id") for v in records.get("videos") or []]
    ds = dataset.load()
    names = {w.get("id"): " ".join(x for x in (w.get("brand"), w.get("model")) if x) or w.get("id")
             for w in ds["watches"]}
    out = []
    for a in ds["appearances"]:
        v = a.get("verdict")
        if a.get("video_id") in set(video_ids) and a.get("role") == "reviewed" and isinstance(v, dict):
            out.append({"watch": names.get(a.get("watch_id"), a.get("watch_id")),
                        "stance": v.get("stance"), "quote": v.get("quote")})
    return out


def _cmd_coding(args):
    run = Path(args.run)
    if args.action == "prepare":
        subjects = coding.normalize_subjects(json.loads(Path(args.subjects).read_text(encoding="utf-8")))
        comments = json.loads(Path(args.comments).read_text(encoding="utf-8"))
        vtype, source = args.type, "flag"
        tf = run.parent / "type.json"
        if vtype is None and tf.is_file():
            vtype, source = json.loads(tf.read_text(encoding="utf-8")).get("type"), "type.json"
        if vtype not in coding.TYPES:
            why = f"{tf} names type {vtype!r}" if source == "type.json" else f"no {tf}"
            print(f"warning: {why}; the brief uses the contest stance fields "
                  "(pass --type, or write type.json first)", file=sys.stderr)
            vtype, source = "contest", "fallback"
        verdicts = _review_verdicts(run.parent, args.videos) if vtype == "review" else None
        res = coding.prepare(comments, subjects, args.keyword, run, chunk=args.chunk,
                             audit_n=args.audit_n, seed=args.seed, vtype=vtype, verdicts=verdicts)
        res["type_source"] = source
        if vtype == "review":
            res["verdicts_in_brief"] = len(verdicts or [])
            if not verdicts:
                print("warning: no reviewed watch with a verdict in the dataset for this run's "
                      "videos; the brief says the verdict was not recorded", file=sys.stderr)
        if source == "fallback":
            _merge_numbers(run.parent, "coding_prepare", res)
    elif args.action == "agreement":
        res = coding.agreement(coding._read_jsonl(args.primary), coding._read_jsonl(args.audit))
        _merge_numbers(run, "coding_agreement", res)
        if res.get("no_overlap"):
            print("warning: primary and audit share no comment ids; kappa is undefined", file=sys.stderr)
    else:
        rows = [r for f in args.coded for r in coding._read_jsonl(f)]
        likes = {}
        if args.comments:
            likes = {c["id"]: c.get("like_count") or 0
                     for c in json.loads(Path(args.comments).read_text(encoding="utf-8"))}
        subjects = list(json.loads(Path(args.subjects).read_text(encoding="utf-8"))) if args.subjects else None
        res = coding.aggregate(rows, likes, subjects)
        _merge_numbers(run, "viewers", res)
    print(json.dumps(res, indent=2))
    return 0


def register_coding(sub):
    p = sub.add_parser("coding", help="comment coding: prepare chunks, agreement (kappa), aggregate")
    cs = p.add_subparsers(dest="action", required=True)
    a = cs.add_parser("prepare", help="filter comments, write chunks, audit sample and BRIEF.md")
    a.add_argument("--run", required=True); a.add_argument("--comments", required=True,
                                                           help="comments.json from ingest")
    a.add_argument("--subjects", required=True, help="JSON {key: [aliases]}")
    a.add_argument("--keyword", action="append", default=[])
    a.add_argument("--chunk", type=int, default=300); a.add_argument("--audit-n", type=int, default=90)
    a.add_argument("--seed", type=int, required=True)
    a.add_argument("--type", choices=coding.TYPES,
                   help="video type for the brief's stance fields (default: <run>/../type.json, else "
                        "contest, with a warning)")
    a.add_argument("--videos", nargs="+", metavar="VIDEO_ID",
                   help="review: whose reviewed-watch verdicts go in the brief (default: the videos "
                        "in <run>/../records.json)")
    g = cs.add_parser("agreement", help="Cohen's kappa between primary and audit coding")
    g.add_argument("--run", required=True); g.add_argument("--primary", required=True)
    g.add_argument("--audit", required=True)
    m = cs.add_parser("aggregate", help="aggregate coded comments into numbers.json viewers.*")
    m.add_argument("--run", required=True); m.add_argument("--coded", nargs="+", required=True)
    m.add_argument("--comments", help="comments.json, for like weights")
    m.add_argument("--subjects", help="subjects JSON, to fix the subject set")
    p.set_defaults(func=_cmd_coding)


def _cmd_taxonomy(args):
    try:
        a = args.action
        if a == "list":
            out = taxonomy.list_versions(args.arg)
        elif a == "get":
            out = taxonomy.get(args.arg)
        elif a == "resolve":
            out = taxonomy.resolve(args.arg)
        elif a == "branch":
            additions = json.loads(Path(args.additions).read_text(encoding="utf-8"))
            out = {"id": taxonomy.branch(args.arg, additions, args.reason)}
        elif a == "score":
            if len(args.rest) != 2:
                raise ValueError("score needs <category-or-file> <records.json> <watch id>")
            src = Path(args.arg)
            if src.is_file():
                t = json.loads(src.read_text(encoding="utf-8"))
            else:
                t = taxonomy.get(args.arg) if ":" in args.arg else taxonomy.resolve(args.arg)
            records = json.loads(Path(args.rest[0]).read_text(encoding="utf-8"))
            w = {x.get("id"): x for x in records.get("watches", [])}.get(args.rest[1])
            if w is None:
                raise KeyError(f"no watch {args.rest[1]!r} in {args.rest[0]}")
            out = {"taxonomy": t.get("id"), "watch": args.rest[1], "marks": taxonomy.score(t, w),
                   "partial": taxonomy.partial_rules(t)}
        elif a == "check":
            t = taxonomy.get(args.arg) if ":" in args.arg else taxonomy.resolve(args.arg)
            errs = taxonomy.validate(t)
            if not errs:
                errs = taxonomy.run_checks(t)
            for e in errs:
                print(f"error: {e}", file=sys.stderr)
            print(json.dumps({"id": t["id"], "errors": len(errs)}))
            return 1 if errs else 0
        else:
            missing = [f for f, v in (("--checks", args.checks), ("--category", args.category),
                                      ("--version", args.version)) if not v]
            if not args.arg or missing:
                print("error: import-fr needs <spec.json> and " + ", ".join(missing or ["<spec.json>"]),
                      file=sys.stderr)
                return 2
            if args.out:
                dest = Path(args.out).resolve()
                want = f"{args.category}@{args.version}.json"
                if dest.parent == Path(taxonomy.SHIPPED_DIR).resolve() and dest.name != want:
                    print(f"refused: a shipped file's name must match its id: {want}, not {dest.name}",
                          file=sys.stderr)
                    return 2
            try:
                out = taxonomy.import_fr(Path(args.arg), Path(args.checks), category=args.category,
                                         version=args.version,
                                         ratification_json=Path(args.ratification) if args.ratification else None)
            except taxonomy.ImportRefused as e:
                for r in e.reasons:
                    print(f"refused: {r}", file=sys.stderr)
                return 2
            except (TypeError, AttributeError) as e:  # backstop: a malformed input not yet named
                print(f"error: malformed compile input ({type(e).__name__}: {e})", file=sys.stderr)
                return 1
            if args.out:
                Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    except (KeyError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


def register_taxonomy(sub):
    p = sub.add_parser("taxonomy", help="list|get|resolve|branch|check|score|import-fr")
    p.add_argument("action", choices=["list", "get", "resolve", "branch", "check", "score", "import-fr"])
    p.add_argument("arg", nargs="?", help="category, version id, or spec path (per action); "
                   "score: category, version id or taxonomy file")
    p.add_argument("rest", nargs="*", help="score: <records.json> <watch id>")
    p.add_argument("--additions", help="branch: JSON file of additions")
    p.add_argument("--reason", help="branch: why")
    p.add_argument("--checks", help="import-fr: the compile's plug-in sidecar (layers, rules, planted cases)")
    p.add_argument("--ratification", help="import-fr: the compile's ratification record, if any")
    p.add_argument("--category", help="import-fr: the taxonomy category, for example gmt")
    p.add_argument("--version", help="import-fr: the shipped version number")
    p.add_argument("--out", help="import-fr: also write the taxonomy to this file")
    p.set_defaults(func=_cmd_taxonomy)


def _cmd_infer(args):
    try:
        criteria = json.loads(Path(args.criteria).read_text(encoding="utf-8"))
        target = json.loads(Path(args.ranking).read_text(encoding="utf-8"))
        missing = [k for k, v in criteria.items() if any(p not in v for p in target)]
        if missing:
            raise ValueError(f"criteria missing subjects from the ranking: {missing[:5]}")
        res = infer.run(criteria, target, max_len=args.max_len)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    run = Path(args.run) if args.run else Path(args.criteria).resolve().parent
    run.mkdir(parents=True, exist_ok=True)
    (run / "infer.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    _merge_numbers(run, "infer", res)
    print(json.dumps(res, indent=2))
    return 0


def register_infer(sub):
    p = sub.add_parser("infer", help="infer which criteria reproduce a ranking; writes infer.json")
    p.add_argument("criteria", help="JSON {criterion: {subject: value}}, higher = better")
    p.add_argument("ranking", help="JSON list of subjects, best first")
    p.add_argument("--run", help="run directory for infer.json and numbers.json (default: criteria's folder)")
    p.add_argument("--max-len", type=int, default=3)
    p.set_defaults(func=_cmd_infer)


def _print_build(build):
    manifest = json.loads((Path(build) / "manifest.json").read_text(encoding="utf-8"))
    print(json.dumps({"build": str(build), **manifest}, indent=2, ensure_ascii=False))
    for m in manifest.get("missing_photos", []):
        print(f"warning: photo not found: {m}", file=sys.stderr)
    for wid in manifest.get("unchecked_photos", []):
        print(f"warning: photo not checked by eye: {wid} (open it, confirm it shows this watch, "
              'then set "checked": true on the photo and rerun dataset-add)', file=sys.stderr)
    for k in manifest.get("missing_fragments", []):
        print(f"warning: no fragment for page {k}; it shows a 'not produced' notice", file=sys.stderr)


def _cmd_build(args):
    try:
        if args.command == "build-child":
            build = pages.build_child(Path(args.run), args.videos, args.type, {})
        else:
            build = pages.build_parent()
    except (KeyError, ValueError, TypeError, OSError, frames.FfmpegError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    _print_build(build)
    return 0


def _cmd_subject_check(args):
    try:
        unmatched = pages.subject_check(Path(args.run), args.videos)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"unmatched": unmatched}))
    for k in unmatched:
        print(f"error: subject {k}: no watch recorded for this run's videos, and no peer, matches it",
              file=sys.stderr)
    return 1 if unmatched else 0


def register_subject_check(sub):
    p = sub.add_parser("subject-check", help="exit 1 naming coding subjects (<run>/coding/subjects.json) "
                                             "with no recorded watch or peer")
    p.add_argument("run")
    p.add_argument("--videos", nargs="+", help="the run's video ids (default: the videos in <run>/records.json)")
    p.set_defaults(func=_cmd_subject_check)


def register_build(sub):
    p = sub.add_parser("build-child", help="assemble a video analysis (child build) into <run>/build/ from the dataset, "
                                           "<run>/numbers.json and <run>/fragments/")
    p.add_argument("run")
    p.add_argument("--type", required=True, choices=sorted(pages.TYPE_PAGES))
    p.add_argument("--videos", nargs="+", required=True, help="video ids in the set")
    p.set_defaults(func=_cmd_build)
    q = sub.add_parser("build-parent", help="assemble the parent collection into <data home>/parent/build/")
    q.set_defaults(func=_cmd_build)


def _cmd_freeze(args):
    try:
        if args.action == "record":
            print(json.dumps(freeze.record(Path(args.build)), indent=2))
        elif args.action == "verify":
            changed = freeze.verify(Path(args.build), json.loads(Path(args.hashes).read_text(encoding="utf-8")))
            if changed:
                print("changed views: " + ", ".join(changed), file=sys.stderr)
                return 1
        elif args.action == "banner":
            freeze.set_banner(Path(args.build), Path(args.file).read_text(encoding="utf-8"))
        else:
            freeze.set_today(Path(args.build), Path(args.file).read_text(encoding="utf-8"), args.view)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def _cmd_check_new(args):
    try:
        seen = {i: publish.registry_find(i) for i in args.ids}
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for i, c in seen.items():
        if c:
            print(f"already registered: {i} -> {c.get('url')}", file=sys.stderr)
    return 3 if any(seen.values()) and not args.rebuild else 0


def _cmd_publish_prepare(args):
    build = Path(args.build).resolve()
    files = publish.files_map(build)
    print(json.dumps({"file_path": str(build / "index.html"), "files": files,
                      "root": str(build), "relative_files": sorted(files)}, indent=2))


def _cmd_series_candidates(args):
    try:
        records = json.loads(Path(args.records).read_text(encoding="utf-8"))
        out = [c for v in records.get("videos", []) for c in publish.series_candidates(v)]
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _cmd_registry(args):
    try:
        if args.action == "find":
            c = publish.registry_find(args.video_id)
            print(json.dumps(c, indent=2, ensure_ascii=False))
            return 0 if c else 1
        build = Path(args.build)
        hashes = (json.loads(Path(args.hashes).read_text(encoding="utf-8")) if args.hashes
                  else freeze.record(build))
        manifest = json.loads((build / "manifest.json").read_text(encoding="utf-8"))
        tax = Path(args.taxonomy) if args.taxonomy else build.parent / "taxonomy.json"
        taxonomy_info = json.loads(tax.read_text(encoding="utf-8")) if tax.is_file() else None
        entry = publish.registry_add(args.kind, args.video_ids or manifest.get("video_ids", []), args.url,
                                     build, hashes, type=manifest.get("type"), taxonomy=taxonomy_info)
        print(json.dumps(entry, indent=2, ensure_ascii=False))
    except (ValueError, KeyError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def _cmd_export_local(args):
    try:
        print(publish.export_local(Path(args.build), Path(args.dest)))
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def register_publish(sub):
    f = sub.add_parser("freeze", help="record, verify or annotate a frozen build")
    fs = f.add_subparsers(dest="action", required=True)
    for name, hlp in (("record", "print the per-view hashes JSON"),
                      ("verify", "exit 1 listing views changed since the recorded hashes"),
                      ("banner", "set the banner slot of every view from an HTML file"),
                      ("today", "set the today slot of one view or all from an HTML file")):
        q = fs.add_parser(name, help=hlp)
        q.add_argument("build")
        if name == "verify":
            q.add_argument("hashes")
        if name == "today":
            q.add_argument("view", help="view id or 'all'")
        if name in ("banner", "today"):
            q.add_argument("file")
    f.set_defaults(func=_cmd_freeze)
    c = sub.add_parser("check-new", help="exit 3 if any video id is already registered")
    c.add_argument("ids", nargs="+")
    c.add_argument("--rebuild", action="store_true", help="allow re-running registered videos")
    c.set_defaults(func=_cmd_check_new)
    p = sub.add_parser("publish-prepare", help="print {file_path, files, root, relative_files} JSON "
                                               "for the Artifact tool")
    p.add_argument("build")
    p.set_defaults(func=_cmd_publish_prepare)
    s = sub.add_parser("series-candidates", help="earlier registered videos in the same series "
                                                 "(same title pattern, different year) as a run's videos")
    s.add_argument("records", help="path to <run>/records.json")
    s.set_defaults(func=_cmd_series_candidates)
    r = sub.add_parser("registry", help="add to or query the publish registry")
    rs = r.add_subparsers(dest="action", required=True)
    a = rs.add_parser("add")
    a.add_argument("kind", choices=["parent", "child"])
    a.add_argument("build")
    a.add_argument("--url", required=True)
    a.add_argument("--video-ids", nargs="+", help="default: the build manifest's video ids")
    a.add_argument("--hashes", help="hashes JSON file (default: recorded from the build)")
    a.add_argument("--taxonomy", help="taxonomy JSON (default: <run>/taxonomy.json if present)")
    g = rs.add_parser("find")
    g.add_argument("video_id")
    r.set_defaults(func=_cmd_registry)
    e = sub.add_parser("export-local", help="copy a build to a standalone folder that opens in a browser")
    e.add_argument("build")
    e.add_argument("dest")
    e.set_defaults(func=_cmd_export_local)


def _cmd_setup_check(args):
    results = setupcheck.check()
    print(json.dumps(results, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


def register_setup_check(sub):
    p = sub.add_parser("setup-check", help="check dependencies; JSON list, exit 1 if any is missing")
    p.set_defaults(func=_cmd_setup_check)


def _cmd_import_example(args):
    try:
        res = importer.import_example(args.name, args.url)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if res.get("notice"):
        print(f"notice: {res['notice']}", file=sys.stderr)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def register_import_example(sub):
    p = sub.add_parser("import-example", help="load a shipped example collection into your dataset "
                                              "and register it as a video analysis")
    p.add_argument("name", help="example name, for example two-watch-challenge")
    p.add_argument("--url", help="where you published the example's page (default: no link)")
    p.set_defaults(func=_cmd_import_example)


# Append-only: later tasks add their register_* function here.
REGISTRARS = [register_paths, register_dataset_add, register_ingest, register_discard_run, register_frames,
              register_verify_links, register_coding, register_taxonomy, register_infer,
              register_build, register_publish, register_setup_check, register_import_example,
              register_subject_check]


def build_parser():
    parser = argparse.ArgumentParser(prog="teddy.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for register in REGISTRARS:
        register(sub)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
