# DupeFinder

A simple command-line tool to detect and optionally delete duplicate files between two directories.  
Duplicates are detected by comparing file size and hash (MD5, SHA1, or SHA256).

---

## Features

- Scans two directories recursively or non-recursively  
- Supports `md5`, `sha1`, and `sha256` hashing algorithms  
- Optional quick mode (hash only first MiB of each file)  
- Stores scan results in an in-memory SQLite database  
- Logs all activity with structured logging levels with option of quiet mode
- Optional automatic deletion of detected duplicates  

---

## Usage

```bash
python dupefinder.py --source <SOURCE_DIR> --target <TARGET_DIR> [options]
```

## Options
| Argument      | Short | Description                                       | Default      |
| ------------- | ----- | ------------------------------------------------- | ------------ |
| `--source`    | `-s`  | Source directory path                             | **required** |
| `--target`    | `-t`  | Target directory path                             | **required** |
| `--algo`      | `-a`  | Hash algorithm: `md5`, `sha1`, `sha256`           | `md5`        |
| `--hash_mode` | `-m`  | Hashing mode: `quick` (first MiB) or `full`       | `quick`      |
| `--delete`    | `-d`  | Automatically delete duplicates (no confirmation) | disabled     |
| `--quiet`     | `-q`  | Keeps console clean with only most essencial info | disabled     |

## Logging

By default, all logs are printed to stdout.
You can modify logging.basicConfig if you want to log into a file.

| Level      | Meaning                                                  |
| ---------- | -------------------------------------------------------- |
| `DEBUG`    | Skipped or ignored files (verbose info)                  |
| `INFO`     | Normal program flow and found duplicates                 |
| `WARNING`  | Recoverable file access errors (permission issues, etc.) |
| `CRITICAL` | Fatal errors that terminate execution                    |

## Exit Codes

| Code | Meaning                                     |
| ---- | ------------------------------------------- |
| `0`  | Successful execution                        |
| `1`  | Unexpected runtime error                    |
| `2`  | Source or target directory not found        |
| `3`  | Database operation failed (insert or query) |

## Example

### Input
```bash
python dupefinder.py -s ./photos/source -t ./photos/backup --algo sha1 --hash_mode full
```

### Output
```bash
2025-10-24 13:45:18 [INFO] Starting duplicate scan
2025-10-24 13:45:18 [INFO] Found 122 files in source dir and 208 files in target dir
2025-10-24 13:45:19 [INFO]  Duplicate: [source_path] <-> [target_path]
[INPUT] Delete second file? (y/N): 
```

## License

MIT License. Free for personal and commercial use.