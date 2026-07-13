"""
Deploy the generated Mapt Daily website to Hostinger via FTP.

Credentials come from environment variables (set as GitHub Secrets — never
hardcode them):
  FTP_HOST   e.g. 82.198.228.56
  FTP_USER   e.g. u877644153.mapt.cloud
  FTP_PASS   (the FTP password)
  FTP_DIR    remote web root for daily.mapt.cloud (default: public_html/daily)

Only website files are uploaded; podcast audio + RSS stay on GitHub Pages.

Usage:
  python deploy_ftp.py            # upload
  python deploy_ftp.py --probe    # just connect and list remote dirs
"""

import os
import sys
import ftplib

HOST = os.environ.get("FTP_HOST", "")
USER = os.environ.get("FTP_USER", "")
PASS = os.environ.get("FTP_PASS", "")
RDIR = os.environ.get("FTP_DIR", "daily")   # relative to the FTP login home (/public_html)

# What to publish (files + directories), relative to the repo root.
FILES = ["index.html", "mapt.html", "vita.html", "about.html", "privacy.html",
         "sitemap.xml", "robots.txt", "llms.txt", "subscribe.php",
         "f2cd6c0eed254e85cb117777e649e630.txt"]   # IndexNow key file (fresh key)
DIRS  = ["static", "blog", "podcasts", "assets"]


def connect() -> ftplib.FTP:
    ftp = ftplib.FTP()
    ftp.connect(HOST, 21, timeout=90)
    ftp.login(USER, PASS)
    ftp.set_pasv(True)
    ftp.home = ftp.pwd()   # login directory (e.g. /public_html); paths are relative to this
    return ftp


def ensure_dir(ftp: ftplib.FTP, path: str) -> None:
    """cd into path (relative to the login home), creating segments as needed."""
    ftp.cwd(ftp.home)
    for seg in [s for s in path.split("/") if s]:
        try:
            ftp.cwd(seg)
        except ftplib.error_perm:
            ftp.mkd(seg)
            ftp.cwd(seg)


def upload_file(ftp: ftplib.FTP, local: str, remote_dir: str) -> None:
    ensure_dir(ftp, remote_dir)
    with open(local, "rb") as f:
        ftp.storbinary(f"STOR {os.path.basename(local)}", f)


def upload_tree(ftp: ftplib.FTP, local_dir: str, remote_base: str) -> int:
    count = 0
    for root, _dirs, files in os.walk(local_dir):
        rel = os.path.relpath(root, local_dir).replace("\\", "/")
        remote_dir = remote_base if rel == "." else f"{remote_base}/{rel}"
        for fn in files:
            upload_file(ftp, os.path.join(root, fn), remote_dir)
            count += 1
    return count


def probe():
    ftp = connect()
    print("Connected. Welcome:", ftp.getwelcome())
    print("CWD on login:", ftp.pwd())
    print("Top-level listing:")
    ftp.retrlines("LIST")
    for d in ("public_html", "domains"):
        try:
            ftp.cwd("/")
            ftp.cwd(d)
            print(f"\n--- /{d} ---")
            ftp.retrlines("LIST")
        except ftplib.error_perm as e:
            print(f"(no /{d}: {e})")
    ftp.quit()


def main():
    if not (HOST and USER and PASS):
        print("ERROR: set FTP_HOST, FTP_USER, FTP_PASS")
        sys.exit(1)
    if "--probe" in sys.argv:
        probe()
        return

    ftp = connect()
    print(f"Connected to {HOST} as {USER}; deploying to /{RDIR}")
    total = 0
    for fn in FILES:
        if os.path.exists(fn):
            upload_file(ftp, fn, RDIR)
            total += 1
    for d in DIRS:
        if os.path.isdir(d):
            n = upload_tree(ftp, d, f"{RDIR}/{d}")
            print(f"  {d}/  ->  {n} files")
            total += n
    ftp.quit()
    print(f"Deploy complete: {total} files uploaded to /{RDIR}")


if __name__ == "__main__":
    main()
