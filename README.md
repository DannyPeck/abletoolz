![Abletoolz](https://github.com/elixirbeats/abletoolz/raw/master/doc/gradient.png)
# Abletoolz

Abletoolz is a Python command line tool to edit, fix and analyze Ableton sets. Primarily the purpose is to automate
things that aren't available and make your life easier.
It can:
- Run on one set, or an entire directory of sets. So you can fix/analyze etc everything with one command.
- Color all your tracks/clips with random color gradients.
- Create a sample database of all your sample folders, which can then be used to automatically fix any broken samples in your ableton sets.
- Set all your Master/Cue outputs to a specific output, so if you buy a new audio interface you can fix all your master outs to point to 7/8 in one go.
- Validate all plugins in a set are installed. MacOS VST3s currently do not work for this.
- Fold/Unfold all tracks, and/or set track height and widths.
- Prepend the set version name to the beginning of the file.
- Append the number of bars of the track, and the bpm to the end of the file.
- Dump the XML of the set, in case you want to dissect how they are structured or contribute to this project : )


It also:
- Moves your original set files to a backup folder before writing any changes, so you are never at risk of losing anything.
- Supports both Windows and MacOS created sets.
- Works on Ableton 8.2+ sets (not every command works with older versions though).
- Preserves the original set modification time.

Future plans:
- Figure out way to verify AU plugins on MacOs.
- Analyze audio clips and color them based on a Serato like gradient (red for bass, turquoise for hi end etc...)
- Build plugin parsers, that can read in the plugin saved buffer and attempt fixes or other things. For instance, a sampler that has a broken filepath could automatically be fixed.
- Figure out how ableton calculates CRC's for samples and use it to make perfect sample fixing. The current algorithm has a very low probability of being wrong, but this would guarantee each result is correct.
- Attempt to detect key based on non drum track midi notes.


## Installation
Minimum python required: 3.10

(https://www.python.org/downloads/)

Open a command line shell and make sure you installed Python 3.10+ correctly:
```
python -V  # Should give you a version
```
Once you verify you have python 3.10+, install with pip:
```
pip install abletoolz
```
This will install abletoolz as a command in your command line. (Create an issue if you run into any errors!)


## Usage

```
abletoolz <command> [options]
```

`-h` / `--help` — Print usage for any command.

`-v` / `--verbose` — Adds extra verbosity for some commands.

Commands that take Ableton sets accept individual `.als`/`.alc` files or directories. Directories are searched recursively and backup folders are automatically skipped.

NOTE: On Windows, do NOT include a trailing backslash inside quotes:

`abletoolz list-tracks "D:\somefolder\"` # BAD

`abletoolz list-tracks "D:\somefolder"` # GOOD

---

### `index-samples` — Build sample database

```
abletoolz index-samples <dirs...>
```

Scans directories for audio samples and builds a local database used for automatic sample fixing.
Run this on all folders that could contain samples. The database is stored in your home directory.

```
abletoolz index-samples ~/Music/Samples ~/Music/Sets
```
![Database](https://github.com/elixirbeats/abletoolz/raw/master/doc/db_example.png)

---

### `list-tracks` — List track information

```
abletoolz list-tracks <sets...> [-v]
```

Loads and prints all track information for each set.

```
abletoolz list-tracks "D:\all_sets\some_set.als"
```
![List tracks](https://github.com/elixirbeats/abletoolz/raw/master/doc/list_tracks.png)

---

### `list-samples` — Check sample paths

```
abletoolz list-samples <sets...> [-v]
```

Checks relative and absolute sample paths and verifies each file exists. Ableton will load a sample as long as one of the two paths is valid. Use `-v` to show found samples alongside missing ones.

```
abletoolz list-samples "D:\all_sets"
```
![Check samples](https://github.com/elixirbeats/abletoolz/raw/master/doc/check_samples.png)

---

### `list-plugins` — Check plugin paths

```
abletoolz list-plugins <sets...> [-v]
```

Checks plugin VST paths and verifies they exist. A summary of all unique VST directories found across all
processed sets is printed at the end.

**Note**: When loading a set, if Ableton finds the same plugin name in a different path it will automatically fix broken paths the next time you save. This command attempts to find missing VSTs and suggest an updated path. Mac Audio Units/AU are not stored with paths — Mac OS is not supported for this yet.

```
abletoolz list-plugins "D:\all_sets"
```
![Check plugins](https://github.com/elixirbeats/abletoolz/raw/master/doc/plugins_check.png)

---

### `unzip-xml` — Dump set XML

```
abletoolz unzip-xml <sets...> [-v]
```

Dumps the uncompressed set XML to `set_name.xml` in the same directory as the set. Useful for understanding set structure or contributing to this project. You can edit the XML, rename it from `.xml` to `.als`, and Ableton will load it. If run multiple times, the previous XML file is moved to the `abletoolz_backup` folder.

```
abletoolz unzip-xml "D:\all_sets\some_set.als"
```

---

### `samples` — Fix missing sample references

```
abletoolz samples <sets...> (--fix-collect | --fix-absolute) [--only-missing] [-s] [-v]
```

Requires a sample database built with `abletoolz index-samples` first. Use `-s`/`--save` to write changes to disk.

**`--fix-collect`** — For each missing sample, find a match in the database (by name, file size, and modification date) and copy it into the set's project folder. Same as Collect and Save in Ableton.

**`--fix-absolute`** — Same as `--fix-collect` but fixes the path in place without copying the sample.
Note: on macOS 10/9 sets this can sometimes behave unexpectedly — prefer `--fix-collect` for those.

```
abletoolz samples "D:\all_sets" --fix-collect -s
```
![Fixing sample references](https://github.com/elixirbeats/abletoolz/raw/master/doc/sample_fix.png)

**`--only-missing`** — Suppress all output for sets that have no missing samples, reducing noise when processing large collections.

---

### `tracks` — Modify track layout and appearance

```
abletoolz tracks <sets...> [options] [-s] [-v]
```

All options modify sets in memory only unless you include `-s`/`--save`.

**`--fold`** / **`--unfold`** — Fold or unfold all tracks and automation lanes in arrangement view.

**`--heights N`** — Set arrangement track heights for all tracks, including groups and automation lanes.
Values depend on your screen resolution — experiment on a test set first. On a typical setup:
Min 17, Default 68, Max 425.

**`--widths N`** — Set clip view track widths for all tracks. On a typical setup: Min 17, Default 24, Max 264.

**`--gradient`** — Generate a random gradient across all tracks using the CIE2000 algorithm. Results are limited to Ableton's 70 available colors, but you can get some nice results!

```
abletoolz tracks "D:\all_sets\myset.als" --unfold --heights 68 --widths 24 -s
```
![Gradient](https://github.com/elixirbeats/abletoolz/raw/master/doc/gradient_2.png)

---

### `routing` — Set audio output routing

```
abletoolz routing <sets...> [--master-out N] [--cue-out N] [-s] [-v]
```

**`--master-out N`** — Set Master audio output. 1 = stereo 1/2, 2 = stereo 3/4, etc.

**`--cue-out N`** — Set Cue audio output. Same numbering as `--master-out`.

```
abletoolz routing "D:\all_sets" --master-out 1 --cue-out 2 -s
```

---

### `rename` — Rename set files on save

```
abletoolz rename <sets...> [--bars-bpm] [--version] -s [-v]
```

Requires `-s`/`--save` to take effect.

**`--bars-bpm`** — Appends the longest clip or furthest arrangement bar length and BPM to the filename.
`myset.als` → `myset_32bars_90.00bpm.als`. Running this multiple times updates the appended section in place — the filename won't keep growing.

**`--version`** — Prepends the Ableton version used to create the set to the filename.

```
abletoolz rename "D:\all_sets\myset.als" --bars-bpm -s
```
![Append bars bpm](https://github.com/elixirbeats/abletoolz/raw/master/doc/append_bars_bpm.png)

---

## Save behavior

When you use `-s`/`--save`, the original file is always moved to a backup directory first:

`${SET_FOLDER}/abletoolz_backup/set_name__1.als`

If that file already exists, the number automatically increments (`__2.als`, `__3.als`, etc.) so previous versions are never overwritten. Clean up this folder periodically if you run save operations frequently.

***Disclaimer*** Before using edit commands with save, experiment on a set you don't care about first and then open it in Ableton to verify the changes are what you expect. The backup system ensures you can always recover your original file, but please allow the script to finish processing before interrupting it.