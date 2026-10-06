"""beatcrate's command line."""
import argparse
import json
import sys
from datetime import date

from . import auth, ingest, profile, webkit
from .app import jobs, server
from .client import Client


def _client():
    # The token lasts 10 minutes: always a fresh one, never the one in session.json.
    # If it expires midway, the client asks for another one once.
    return Client(auth.get_token(), renew=auth.get_token)


# Commands that read the Beatport session need WebKit's window loop, which has to own the main thread:
# they run inside webkit.run.
def cmd_login(_):
    webkit.run(auth.login)
    return 0


def cmd_ingest(_):
    webkit.run(_ingest)
    return 0


def _ingest():
    lib = ingest.build_library(_client())
    ingest.write_library(lib)
    prof = profile.build_profile(lib, date.today())
    profile.write_profile(prof)
    print(f"Library: {len(lib['tracks'])} tracks. "
          f"Profile: {len(prof['labels'])} labels, {len(prof['artists'])} artists.")


def cmd_generate(_):
    path = webkit.run(lambda: jobs.generate("cli"))
    crate = json.loads(path.read_text())
    short = " (short)" if crate["short"] else ""
    print(f"Selection {crate['id']}: {len(crate['tracks'])} tracks{short} "
          f"out of {crate['candidates_seen']} candidates.\n  {path}")
    return 0


def cmd_app(_):
    server.run_app()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="beatcrate", description="Beatport new releases picked for your taste")
    subs = p.add_subparsers(dest="cmd")
    for name, fn, help_text in (
        ("login", cmd_login, "sign in to Beatport in a beatcrate window"),
        ("ingest", cmd_ingest, "read playlists and purchases and build the profile"),
        ("generate", cmd_generate, "make a new selection of the last 31 days"),
        ("app", cmd_app, "open the app in its window"),
    ):
        sp = subs.add_parser(name, help=help_text)
        sp.set_defaults(func=fn)
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_usage(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
