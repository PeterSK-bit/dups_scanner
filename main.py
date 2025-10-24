import os
import hashlib
import argparse
import sqlite3
import logging

# bullmq?

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
                    scanned_files += FileScanner.scan(full_path)
            else:
                scanned_files.append(full_path)
        
        return scanned_files
    

class FileHasher:
    def __init__(self, algorithm: str = "md5"):
        if algorithm.lower() in ("md5", "sha1", "sha256"):
           self.algorithm = algorithm.lower()
        else:
            print("INFO: Invalid hashing algorithm type, defaulting to md5")
            self.algorithm = "md5"
    
    def quick_hash(self, file_path: str, hashing_chunk_size: int = 1_048_576) -> str:
        """
        Hashes chunk of file in **file_path** provided by loading chunk of size specified with **hashing_chunk_size**.
        **Returns** hash of specified type in form of **str**.
        """

        hasher = hashlib.new(self.algorithm)

        with open(file_path, "rb") as f:
            hasher.update(f.read(hashing_chunk_size))
        
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

    def insert(self, files: list[str, str, int, bool]) -> None:
        self.cur.executemany(
            "INSERT INTO files (file_path, hash, file_size, source) VALUES (?, ?, ?, ?)",
            files
        )
        self.con.commit()
    
    def find_dupes(self) -> list[(str, str)]:
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



class Controller:
    def __init__(self, source_dir: str, target_dir: str, hashing_algorithm: str = "md5", hash_mode = "quick", delete: bool = False) -> None:
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.hashing_algorithm = hashing_algorithm
        self.hash_mode = hash_mode
        self.delete = delete

    def run(self):
        try:
            source_files = FileScanner.scan(self.source_dir)
            target_files = FileScanner.scan(self.target_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return
        except Exception as e:
            print(f"Unexpected error: {e}")
            return

        hasher = FileHasher(self.hashing_algorithm)
        hf = hasher.quick_hash if self.hash_mode == "quick" else hasher.full_hash

        hashed_source_files = [(path, hf(path), os.path.getsize(path), True) for path in source_files]
        hashed_target_files = [(path, hf(path), os.path.getsize(path), False) for path in target_files]

        connection = sqlite3.connect(":memory:")
        db = Database(connection)
        db.insert(hashed_source_files)
        db.insert(hashed_target_files)

        duplicates = db.find_dupes()

        for source_path, target_path in duplicates:
            print(f"Duplicate: {source_path} <-> {target_path}")
            if self.delete or input("Delete second file? (y/N): ").lower() == "y":
                os.remove(target_path)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and handle duplicate files between two directories.")
    parser.add_argument("--source", "-s", required=True, help="Source dir path")
    parser.add_argument("--target", "-t", required=True, help="Target dir path")
    parser.add_argument("--algo", "-a", choices=["md5", "sha1", "sha256"], default="md5", help="Hashing algorithm")
    parser.add_argument("--hash_mode", "-m", choices=["full", "quick"], default="quick", help="Hashing full file or first MiB")
    parser.add_argument("--delete", "-d", action="store_true", help="Automatically deletes duplicates from target (no prompt)")

    args = parser.parse_args()

    app = Controller(args.source, args.target, args.algo, args.hash_mode, args.delete)
    app.run()