"""Cli entry point."""

import argparse
import datetime
import io
import logging
import os
import pathlib
import sys
import time
import traceback
from typing import Dict, List, Optional, Set

from abletoolz import __version__
from abletoolz.ableton_set import AbletonSet
from abletoolz.misc import BACKUP_DIR, CB, B, C, ElementNotFound, M, R, Y
from abletoolz.sample_databaser import create_db

logger = logging.getLogger(__name__)


def get_pathlib_objects(sets: List[str]) -> List[pathlib.Path]:
    """Get all ableton sets to parse.

    Args:
        sets: path or paths to directories and set files.

    Returns:
        list of pathlib.Paths with all ableton sets to parse, excluding backup directories.
    """
    paths: List[pathlib.Path] = []
    for src in sets:
        path = pathlib.Path(src)
        if path.is_dir():
            files = list(path.rglob("*.als")) + list(path.rglob("*.alc"))
            # Hacky but Path.rglob doesn't have options for filtering.
            files_to_process = []
            for file in files:
                if all(x not in file.parts[:-1] for x in ["Backup", "backup", BACKUP_DIR]) and not file.stem.startswith(
                    ("._")
                ):
                    files_to_process.append(file)
            paths.extend(files_to_process)
        elif path.is_file():
            paths.append(path)
    return paths


def is_valid_dir_path(path: str) -> str:
    """Check if the path is a valid.

    Mainly for windows, which uses backslashes instead and this causes problems for parsing command line arguments since
    backslash is used for escaping.
    """
    if sys.platform.startswith("win") and '"' in path:
        raise ValueError(
            f"{R}Windows paths must not end in backslash: \n'C:\\somepath\\'(BAD)\n'C:\\somepath' "
            f"(GOOD)\nThis is due to a bug in how Windows handles backslashes before quotes."
        )
    return path


def _add_sets_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "sets",
        nargs="+",
        help="Set(s) or directory(ies). All sub folders in directories are parsed for sets. NOTE: On WINDOWS remove "
        "the trailing backslash when processing folders! This is due to how windows and python interact with "
        "backslashes, which are normally escape characters.",
    )


def _add_save_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        default=False,
        help="Saves file after parsing. This is only put here as a safety check, to make sure you know "
        "what you are doing! The original file is always renamed to "
        f"set_directory/{BACKUP_DIR}/set_name_xx.als, where xx will automatically increase to "
        "to avoid overwriting files.",
    )


def _add_verbose_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Adds extra verbosity.",
    )


def _add_index_samples_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "index-samples",
        help="Create/update sample database for fast lookups when fixing broken sample paths.",
    )
    p.add_argument(
        "samples",
        nargs="+",
        help="Directories to scan for samples.",
    )
    _add_verbose_arg(p)


def _add_list_tracks_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("list-tracks", help="List track information for Ableton sets.")
    _add_sets_arg(p)
    _add_verbose_arg(p)


def _add_list_samples_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("list-samples", help="Check relative and absolute sample paths and verify they exist.")
    _add_sets_arg(p)
    _add_verbose_arg(p)


def _add_list_plugins_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "list-plugins",
        help="Check plugin VST paths and verify they exist. VST directories discovered across sets are accumulated "
        "to aid searching for missing plugins.",
    )
    _add_sets_arg(p)
    _add_verbose_arg(p)


def _add_unzip_xml_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "unzip-xml",
        help="Dump the uncompressed set XML to set_name.xml in the same directory. Useful for understanding set "
        "structure. Previous XML files are moved to the abletoolz_backup folder.",
    )
    _add_sets_arg(p)
    _add_verbose_arg(p)


def _add_samples_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("samples", help="Fix missing sample references.")
    _add_sets_arg(p)
    fix_group = p.add_mutually_exclusive_group(required=True)
    fix_group.add_argument(
        "--fix-absolute",
        action="store_true",
        default=False,
        help="Find missing samples and fix broken references. Does not copy samples into project folder. "
        "Run 'abletoolz db' on folders first to create your database.",
    )
    fix_group.add_argument(
        "--fix-collect",
        action="store_true",
        default=False,
        help="Collect and save missing samples into the set's project folder, the same as collect and save in "
        "Ableton. Run 'abletoolz db' on folders first to create your database.",
    )
    p.add_argument(
        "--only-missing",
        action="store_true",
        default=False,
        help="Suppress all output for sets that have no missing samples.",
    )
    _add_save_arg(p)
    _add_verbose_arg(p)


def _add_tracks_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("tracks", help="Modify track layout and appearance.")
    _add_sets_arg(p)
    fold_group = p.add_mutually_exclusive_group()
    fold_group.add_argument(
        "--fold",
        action="store_true",
        default=False,
        help="Fold all tracks/automation lanes in arrangement.",
    )
    fold_group.add_argument(
        "--unfold",
        action="store_true",
        default=False,
        help="Unfold all tracks/automation lanes in arrangement.",
    )
    p.add_argument("--heights", type=int, help="Set arrangement track heights.")
    p.add_argument("--widths", type=int, help="Set clip view track widths.")
    p.add_argument(
        "--gradient",
        action="store_true",
        default=False,
        help="Generate a random gradient over the tracks and color them. Ableton has a very limited set of available "
        "colors, so the results are limited, but you still can get some decent results. This uses the CIE2000 "
        "algorithm which helps create a gradient more natural to the human eye.",
    )
    _add_save_arg(p)
    _add_verbose_arg(p)


def _add_routing_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("routing", help="Set audio output routing.")
    _add_sets_arg(p)
    p.add_argument(
        "--master-out",
        type=int,
        help="Number to set Master audio output tracks to. Set to 1 for stereo 1/2, 2 for 3/4, etc.",
    )
    p.add_argument(
        "--cue-out",
        type=int,
        help="Set Cue audio output tracks. Same numbering as --master-out.",
    )
    _add_save_arg(p)
    _add_verbose_arg(p)


def _add_rename_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("rename", help="Rename set files on save.")
    _add_sets_arg(p)
    p.add_argument(
        "--bars-bpm",
        action="store_true",
        default=False,
        help="Append furthest bar length and BPM to filename. "
        "For example, my_set.als --> my_set_32bars_90.00bpm.als. Requires -s/--save.",
    )
    p.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Prepend Ableton version to set filename. Requires -s/--save.",
    )
    _add_save_arg(p)
    _add_verbose_arg(p)


def parse_arguments() -> argparse.Namespace:
    """Get command line arguments."""
    parser = argparse.ArgumentParser(description=f"abletoolz {__version__}", add_help=True)
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    _add_index_samples_subcommand(subparsers)
    _add_list_tracks_subcommand(subparsers)
    _add_list_samples_subcommand(subparsers)
    _add_list_plugins_subcommand(subparsers)
    _add_unzip_xml_subcommand(subparsers)
    _add_samples_subcommand(subparsers)
    _add_tracks_subcommand(subparsers)
    _add_routing_subcommand(subparsers)
    _add_rename_subcommand(subparsers)

    return parser.parse_args()


def _load_set(pathlib_obj: pathlib.Path) -> Optional[AbletonSet]:
    """Parse and initialize an Ableton set, returning None on parse failure."""
    logger.info("%sParsing: %s", C, pathlib_obj)
    ableton_set = AbletonSet(pathlib_obj)
    if not ableton_set.parse():
        return None
    ableton_set.load_version()
    logger.info("%sSet name: %s, %sBPM: %s", C, pathlib_obj.stem, B, ableton_set.get_bpm())
    ableton_set.find_project_root_folder()
    ableton_set.find_furthest_bar()
    ableton_set.estimate_length()
    return ableton_set


def _get_sets(sets: List[str]) -> List[pathlib.Path]:
    """Resolve set paths, logging an error and returning an empty list if none found."""
    paths = get_pathlib_objects(sets)
    if not paths:
        logger.info("%sError, no sets to process!", R)
    return paths


def _log_separator() -> None:
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 80
    logger.info("%s\n\n%s\n\n", M, "^" * width)


def _log_summary(start_time: float, count: int) -> None:
    logger.info("%sTook %s to process %s set(s)", CB, datetime.timedelta(seconds=time.time() - start_time), count)


def run_index_samples(args: argparse.Namespace) -> int:
    create_db.create_or_update_db(args.samples)
    return 0


def run_list_tracks(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue

            ableton_set.load_tracks()
            ableton_set.print_tracks()
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


def run_list_samples(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue

            ableton_set.list_samples()
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


def run_list_plugins(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    accumulated_vst_dirs: Set[pathlib.Path] = set()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue

            accumulated_vst_dirs |= ableton_set.list_plugins()
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    if accumulated_vst_dirs:
        logger.info("%sAll VST directories found:", CB)
        for vst_dir in sorted(accumulated_vst_dirs):
            logger.info("  %s%s", M, vst_dir)
    else:
        logger.info("%sNo VST directories found.", Y)
    return 0


def run_unzip_xml(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue

            ableton_set.save_xml()
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


def run_samples(args: argparse.Namespace) -> int:
    logger.info("%sLoading db...", M)
    db = create_db.load_db()
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    sets_with_missing = 0
    for path in paths:
        if args.only_missing:
            log_buffer = io.StringIO()
            buffer_handler = logging.StreamHandler(log_buffer)
            buffer_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = [buffer_handler]
            try:
                ableton_set = _load_set(path)
                missing = ableton_set.fix_samples(db, collect_and_save=args.fix_collect) if ableton_set else -1
            except ElementNotFound:
                missing = -1
            root_logger.handlers = original_handlers
            if missing != 0:
                sets_with_missing += 1
                sys.stdout.write(log_buffer.getvalue())
                if args.save and missing > 0:
                    ableton_set.save_set()
                _log_separator()
        else:
            try:
                ableton_set = _load_set(path)
                if ableton_set is None:
                    _log_separator()
                    continue
                missing = ableton_set.fix_samples(db, collect_and_save=args.fix_collect)
                if missing > 0:
                    sets_with_missing += 1
                if args.save:
                    ableton_set.save_set()
                else:
                    logger.info("%sNo changes saved, use -s/--save option to write changes to file.", Y)
            except ElementNotFound:
                logger.info(traceback.format_exc())
            _log_separator()
    logger.info(
        "%sTook %s to process %s set(s), %s with missing samples",
        CB,
        datetime.timedelta(seconds=time.time() - start),
        len(paths),
        sets_with_missing,
    )
    return 0


def run_tracks(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue
            if args.fold:
                ableton_set.fold_tracks()
            elif args.unfold:
                ableton_set.unfold_tracks()
            if args.heights:
                ableton_set.set_track_heights(args.heights)
            if args.widths:
                ableton_set.set_track_widths(args.widths)
            if args.gradient:
                ableton_set.gradient_tracks()
            if args.save:
                ableton_set.save_set()
            else:
                logger.info("%sNo changes saved, use -s/--save option to write changes to file.", Y)
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


def run_routing(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue
            if args.master_out:
                ableton_set.set_audio_output(args.master_out, element_string="MasterTrack")
            if args.cue_out:
                ableton_set.set_audio_output(args.cue_out, element_string="PreHearTrack")
            if args.save:
                ableton_set.save_set()
            else:
                logger.info("%sNo changes saved, use -s/--save option to write changes to file.", Y)
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


def run_rename(args: argparse.Namespace) -> int:
    paths = _get_sets(args.sets)
    if not paths:
        return -1
    start = time.time()
    for path in paths:
        try:
            ableton_set = _load_set(path)
            if ableton_set is None:
                _log_separator()
                continue
            if args.save:
                ableton_set.save_set(append_bars_bpm=args.bars_bpm, prepend_version=args.version)
            else:
                logger.info("%sNo changes saved, use -s/--save option to write changes to file.", Y)
        except ElementNotFound:
            logger.info(traceback.format_exc())
        _log_separator()
    _log_summary(start, len(paths))
    return 0


_COMMAND_HANDLERS = {
    "index-samples": run_index_samples,
    "list-tracks": run_list_tracks,
    "list-samples": run_list_samples,
    "list-plugins": run_list_plugins,
    "unzip-xml": run_unzip_xml,
    "samples": run_samples,
    "tracks": run_tracks,
    "routing": run_routing,
    "rename": run_rename,
}


def process(args: argparse.Namespace) -> int:
    return _COMMAND_HANDLERS[args.command](args)


def main() -> None:
    """Entry point to cli."""
    args = parse_arguments()

    logging.getLogger("colormath").setLevel(logging.WARNING)
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        datefmt="%H:%M:%S",
    )
    sys.exit(process(args))


if __name__ == "__main__":
    main()