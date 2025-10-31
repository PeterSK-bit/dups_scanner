import os
import hashlib
import argparse
import sqlite3
import logging
import sys
from dataclasses import dataclass

EXIT_UNEXPECTED = 1
EXIT_FILE_ERROR = 2
EXIT_DB_ERROR = 3

class FileScanner:
    @staticmethod
    def scan(path: str, recursive: bool = True) -> list:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        scanned_files = []

        for file_name in os.listdir(path):
            full_path = os.path.join(path, file_name)
            if os.path.isdir(full_path):
                if recursive:
                    scanned_files.extend(FileScanner.scan(full_path))
            else:
                scanned_files.append(full_path)
        
        return scanned_files
    

class FileHasher:
    def __init__(self, algorithm: str = "md5"):
        if algorithm.lower() in ("md5", "sha1", "sha256"):
           self.algorithm = algorithm.lower()
        else:
            logging.warning("Invalid hashing algorithm type %s, defaulting to md5", algorithm)
            self.algorithm = "md5"
    
    def quick_hash(self, file_path: str, hashing_chunk_size: int = 1_048_576) -> str | None:
        """
        Hashes chunk of file in **file_path** provided by loading chunk of size specified with **hashing_chunk_size**.
        **Returns** hash of specified type in form of **str**.
        """

        hasher = hashlib.new(self.algorithm)
        try:
            with open(file_path, "rb") as f:
                hasher.update(f.read(hashing_chunk_size))
        except PermissionError:
            logging.warning("Permission denied for %s, excluding file from list", file_path)
            return None
        except Exception as e:
            logging.warning("Unexpected error while reading %s: %s", file_path, e)
            return None

        return hasher.hexdigest()
    
    def full_hash(self, file_path: str, chunk_size: int = 1_048_576) -> str:
        """
        Hashes whole file in **file_path** provided by loading chunks of size specified with **chunk_size** until none left.
        **Returns** hash of specified type in form of **str**.
        """

        hasher = hashlib.new(self.algorithm)

        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        
        return hasher.hexdigest()



class Database:
    def __init__(self, connection: sqlite3.Connection):
        self.con = connection
        self.cur = connection.cursor()
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_path TEXT PRIMARY KEY,
                hash TEXT, 
                file_size INTEGER, 
                source INTEGER CHECK(source IN (0,1)));
        """)

        self.con.commit()

    def insert(self, files: list[tuple[str, str, int, bool]]) -> None:
        self.cur.executemany(
            "INSERT OR IGNORE INTO files (file_path, hash, file_size, source) VALUES (?, ?, ?, ?)",
            files
        )
        self.con.commit()
    
    def find_dupes(self) -> list[tuple[str, str]]:
        self.cur.execute("""
            SELECT
                s.file_path AS source_path,
                t.file_path AS target_path
            FROM files s
            JOIN files t
            ON s.hash = t.hash
            AND s.file_size = t.file_size
            WHERE s.source = 1
            AND t.source = 0;

        """)
        return self.cur.fetchall()

    def count(self) -> int:
        return self.cur.execute("SELECT COUNT(*) FROM files").fetchone()[0]



@dataclass
class Config:
    source: str
    target: str
    hashing_algo: str
    hashing_mode: str
    delete: bool
    quiet: bool



class Controller:
    def __init__(self, config: Config) -> None: 
        self.source_dir = config.source
        self.target_dir = config.target
        self.hashing_algorithm = config.hashing_algo
        self.hashing_mode = config.hashing_mode
        self.delete = config.delete

    def _hash_files(self, file_list, hasher_func, source_flag):
        results = []
        for path in file_list:
            hash_val = hasher_func(path)
            if not hash_val:
                continue
            try:
                size = os.path.getsize(path)
            except OSError as e:
                logging.warning("Cannot get size of %s: %s", path, e)
                continue
            results.append((path, hash_val, size, source_flag))
        return results


    def run(self):
        logging.info("Starting duplicate scan")
        
        try:
            source_files = FileScanner.scan(self.source_dir)
            target_files = FileScanner.scan(self.target_dir)
            logging.info("Found %d files in source dir and %d files in target dir", len(source_files), len(target_files))
        except FileNotFoundError as e:
            logging.critical("Directory error: %s", e)
            sys.exit(EXIT_FILE_ERROR)
        except Exception as e:
            logging.critical("Unexpected error: %s", e)
            sys.exit(EXIT_UNEXPECTED)

        hasher = FileHasher(self.hashing_algorithm)
        hf = hasher.quick_hash if self.hashing_mode == "quick" else hasher.full_hash

        hashed_source_files = self._hash_files(source_files, hf, True)
        hashed_target_files = self._hash_files(target_files, hf, False)


        connection = sqlite3.connect(":memory:")
        db = Database(connection)
        
        try:
            db.insert(hashed_source_files)
            db.insert(hashed_target_files)

            files_count = db.count()

            logging.info("Inserted %d records into memory DB", files_count)
        except Exception as e:
            logging.critical("Insertion into DB was unsuccessful: %s", e)
            sys.exit(EXIT_DB_ERROR)

        try:
            duplicates = db.find_dupes()
        except Exception as e:
            logging.critical("Exececution of DB query was unsuccessful: %s", e)
            sys.exit(EXIT_DB_ERROR)

        for source_path, target_path in duplicates:
            if self.delete or input(f"[INFO]\tDuplicate: {source_path} <-> {target_path}\n[INPUT]\tDelete second file? (y/N): ").lower() == "y":
                try:
                    os.remove(target_path)
                except Exception as e:
                    logging.error("Failed to delete %s: %s", target_path, e)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and handle duplicate files between two directories.")
    parser.add_argument("--source", "-s", required=True, help="Source dir path")
    parser.add_argument("--target", "-t", required=True, help="Target dir path")
    parser.add_argument("--hashing_algo", "-a", choices=["md5", "sha1", "sha256"], default="md5", help="Hashing algorithm")
    parser.add_argument("--hashing_mode", "-m", choices=["full", "quick"], default="quick", help="Hashing full file or first MiB")
    parser.add_argument("--delete", "-d", action="store_true", help="Automatically deletes duplicates from target (no prompt)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Runs with only essencial logs.")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.CRITICAL if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )

    config = Config(**vars(args))

    app = Controller(config)
    app.run()